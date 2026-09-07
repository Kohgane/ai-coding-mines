# Write APIs · How not to trust the response

Collected over six months against a platform commerce API. **This is not about one platform.** Any write API with an approval workflow, partial-update support, and status-as-string produces the same shapes.

One sentence:

> **No response is proof of success. Only re-fetch is.**

**Why this chapter bites non-ASCII users**
The APIs here are Korean marketplaces. Their status values, rejection reasons, and validation errors come back as Korean strings, not enum codes. Several entries below are about what happens when you match on those strings. If your API speaks English, substitute your own status vocabulary; the mechanism (prefix-sharing states, human-readable messages posing as machine values) is identical. The Korean strings are kept verbatim because they are the real data, each with a gloss.

---

## Five ways a success response lies

Hit all five in one day, so it became a table.

| Response | What actually happened |
|---|---|
| `200` + `code=ERROR` | Tried to modify a resource under review. **HTTP is 200.** |
| `200` + `rows=0` | Filtered on **an enum value that doesn't exist.** Not an error; an empty result. |
| `200` + `code=SUCCESS` + **no effect** | Partial update silently ignored. 26 minutes later, unchanged. |
| `200` + `code=SUCCESS` + warning | A warning attached, but **it actually applied.** Read the warning as failure and you retry healthy items. |
| `400 PRECONDITION_FAILED` | Simply **a path that doesn't exist.** Not a precondition violation. |

★ **There are at least three axes of success/failure:** HTTP status, `code` in the body, and **the actual value on re-fetch.** The first two can both pass while the third differs.

**Enforcement**

```python
def ok(code, resp):
    return code == 200 and isinstance(resp, dict) and resp.get("code") != "ERROR"
```

Without it, **~700 items spun for nothing.** All rejected, all recorded as success in the progress file.

**And this is still not enough.** Row 3 in the table passes `ok()`. After every write, **re-fetch the single record** and check the real value. If there's a change-history endpoint, that is even more reliable.

**The reverse direction: a success that looks like failure**
A write's success response carried `message` as the string `"[]"`. Not an empty array; **a truthy string that looks like one.** Code that judged errors with `if msg:` recorded items that had applied correctly as failures. Empty-value representations vary by type: `""`, `[]`, `"[]"`, `{}`, `null`. **Judge by content, not by presence.**
★ **A contaminated failure list invalidates every diagnosis built on it.** Those "failures" became the evidence for a wrong root cause; the real culprit was elsewhere. When one verdict function is wrong, throw away not just the batch result but every conclusion drawn from it.

**A sixth shape: the rejected list went unread**
A tracking-registration API returns `accepted` and `rejected` **as separate lists.** The wrapper ignored the rejected list and recorded every item as registered in the local DB. Items rejected because carrier auto-detection failed sat there untrackable. Count `accepted`, and alert when it is 0.
★ **And `accepted` isn't the end either.** Registration can succeed while tracking returns not-found. "Accepted" means registered, not tracked. **Success has one more layer.**

---

## Ignore the HTTP status and a 400 reads as "0 rows"

**Symptom**
Order query returned **0 rows.** Judged "nothing unshipped" and moved on. In reality **9 unfulfilled orders were sitting there**, 4 of them past deadline.

**Cause**
The query window was 40 days; the API's ceiling is **under 32 days.**

```
"endTime-startTime range should less than 32 day."
```

**It was HTTP 400.** But the code only counted the length of the `data` array, so `len([]) == 0` → "0 rows."

★ **Look only at the body and not the status code, and every 4xx turns into 0 rows.**

**Fix**
Check the status code first in the query wrapper, and on non-2xx **raise instead of returning 0.** A function that returns the same value for "0 rows" and "query failed" will always deceive its caller.

**Same mechanism, from a public geodata API**
Raised a search-radius parameter to three times its ceiling (10,000 m). The API returned an error; the collector **exited normally with "0 documents."** Without reading the log it would have spun for hours.
★ **When a parameter has a ceiling, don't raise the value; add call sites.** Instead of growing one center's radius, **tile: the center plus four points around it,** then dedupe by title. There are two ways to widen coverage, and a ceiling leaves only the second.
★ **A collector never treats 0 rows as a normal result.** Log it as a warning. A real 0 costs a human one glance; a fake 0 has that warning as its only clue.

---

## Leave the query string out of the signature and 401 looks like "0 rows"

**Symptom**
List queries keep returning 0. Assumed auth was passing.

**Cause**
The HMAC signing string **omitted the query string.** The real response was `401 Invalid signature`.

★ **There's a reason the defect stayed hidden:** on endpoints that use no query string (the product API) the signature was correct. **It only broke on endpoints that use one.**

**What it cost**
Took the 0 as fact, made a verdict, and **that verdict delisted items that were selling** (restored).

**The clue (worth recording)**
**The admin dashboard showed revenue while the API returned 0.** That mismatch was the lead.

★ **Before doing anything irreversible on the basis of a 0, cross-check via another route.**

**Not every 0 is the same**
Another channel's query was also 0, and that one was **a real 0**, **confirmed by reading the raw response by eye.**
**A 0 that has been through verification and a 0 that hasn't are different values.**

---

## Partial updates are silently ignored

**Symptom**
`PATCH` or partial `PUT` with a body returns `200` + `SUCCESS`, and **the value doesn't change.**

**Blast radius**
The batch **changed nothing for six weeks.** The `ok:1500` in the progress file was *the length of the string we tried to send*, not *a stored result.* 90% of a 40-item sample was untouched, and that wasn't a batch failure; **it was the original from registration time, still sitting there.**

**How it was confirmed by controlling variables**
First suspect: payload structure. So **six structures** were tried (plain div / img / table / ul / with double quotes / whitespace preserved). **All failed.**
★ **Six variants with the same result means it isn't the structure.** You have to vary the variable to prove it isn't the cause.

**The confirmed path**
In approved state, **only a full PUT takes effect.**
1. Full PUT (no id, approval-request flag off) → **demoted to draft and the value lands**
2. Request approval → back to approved

⚠️ **This path creates one risk.** A full PUT passes **through a temporary not-for-sale state.** Run it in bulk and that many items go off sale simultaneously. **Split into small batches and re-fetch status after each to confirm the return.** Leaving items parked in draft is the real accident.

**A failed full PUT is not "nothing happened"**
A full PUT came back 400, but **the approval-request reset had already applied.** The rejected items were stuck in draft, which means off sale. **Write failure ≠ no change.** Re-fetch status after a failure response too.
Two more from the same batch:
- The success response's `message` came as the string `"[]"`, so `if msg:` logged success as failure. That is the reverse direction of "Five ways a success response lies" above.
- The batch changed one field, but **an unrelated attribute-enrichment function was bolted onto it.** That function generated values outside the allowed list and killed the whole batch. ★ **"While we're at it" is where the failure rate comes from. One batch changes one thing.**

**Safety net: sweep what is left in draft**
A job runs every 30 minutes, lists everything still in draft, re-requests approval, and **alerts when the count exceeds a threshold.** Splitting into small batches is prevention; this caps how long an accident leaves items off sale.

---

## Fire the follow-up call immediately and it's ignored

**Symptom**
Change value → immediately request approval. Approval doesn't stick, or sticks and then reverts.

**Cause**
The next call arrives before the write has landed. Chaining the two calls **failed 37 of 37** once.

**Fix**
- **Separate** the two calls
- **Wait 2, 4, 6, 8s and retry four times** + **re-fetch status** on every round
- Record final failures in the progress file under a distinct code so leftovers can be counted later

★ **A 200 means "the request was accepted," not "the next call can see it."**

---

## Some fields can only be set at creation

**Symptom**
Trying to fix a category code: partial PUT and full PUT both **return 200 and the value doesn't change.** Confirmed in **both** approved and draft state.

**Confirmed case**
Dozens of items went through name and brand edits; category code was **unchanged on every one.** Outerwear was sitting in a phone-accessory category with **no way to fix it.**

**"There is no fix" is the fix**
Miscategorized means **delete and re-create.** And items under review or sanction can't be deleted either, so even that is off the table.

★ **Find out which values must be final at creation before you write the creation code.** Don't assume "we'll fix it later."

**Met the same property on another channel:** category ID immutable after creation (`NotChangable`). **When different channels impose the same constraint, it isn't coincidence; it's a property of the domain.**

**Sub-resources have a different unit**
A "stop sales" call on the parent item's path returns **404.** Stopping sales and changing stock work only on the **child resource (the option-level ID)**, never the parent. Before reading a 404 as "no such feature," **look for the child-resource path.** Which unit each operation binds to belongs on the same pre-coding checklist as the values that are final at creation.

---

## A field can be one-way

**Symptom**
Trying to clear a brand field back to empty: **400.**

```
"브랜드명은 제출 후 변경할 수 없습니다"
```
("Brand name cannot be changed after submission.")

Empty → value works. **Value → empty doesn't.**

★ **Put in the wrong value and it's permanent.** Don't write on the assumption you can undo.

**Side note: where I was wrong**
I recorded "an empty brand makes approval stall" and then **retracted it.** Empty passes. The real cause of the stall was the previous entry's **chained calls.** Correlation read as causation.

---

## A status field's name doesn't mean status

**Three at once.**

**1. Suspend sales and `statusName` stays `'승인완료'` (approved).**
Whether it's actually selling lives on a separate endpoint's `onSale` and stock count. Approval state and sales state are **different axes.**

**2. Deleted items still come back with `statusName='상품삭제'` (product deleted).**
★ **Don't judge deletion by presence.** Read "it's in the list, so it's alive" and you reprocess things already gone. Two batches repeated the same work every 20–30 minutes on this misread.

**3. Status strings share prefixes.**
`임시저장` (saved as draft) and `임시저장중` (saving as draft) **both exist as distinct strings.**

```python
if status == '임시저장':               # misses 임시저장중
if status.startswith('임시저장'):      # this is the one
```

★ **Before comparing status values with `==`, dump every value that actually exists.** Values not in the docs will show up.

**Why this bites non-ASCII users**
When statuses are human-readable strings in your own language rather than `IN_REVIEW`-style codes, the temptation is to treat them like codes. They aren't. They are prose, they get new variants without a changelog, and a suffix (`중`, roughly "-ing") turns one state into two. Enumerate them from live data, never from the docs.

---

## The list labelled "all statuses" was not all of them

**Symptom**
On an API where the list endpoint **requires a status filter**, records in one band never appear. They exist, but no combination of filters returns them.

**Cause**
One status was **missing from the filter list** — a short-lived intermediate band ("tracking number entered, not yet scanned by the carrier").

★ Worse: that list had been written down six months earlier as **"expanded to all statuses"**. It actually contained a similarly-named value (`NONE`) and omitted the real one (`NONE_TRACKING`). **Because it said "all", nobody checked it again.**

**Cost**
Orders in that band were **unfindable for two days.** They needed action.

**Fix**
- Take filter values from **the actual enum, not the documentation**
- ★ **The moment you write "all", the next person skips verification.** When you record a list, **record how you confirmed it**
- ★ **Beware statuses whose names read as empty.** `NONE_TRACKING` sounds like "no tracking" but means **"not yet scanned"**. When the name misleads about the nature, it gets dropped from lists

★★ **On a list API with a mandatory filter, a value you omitted is a record that does not exist.**
Suspect the filter before concluding "there are none".

**The other side is blocked too**
Records in that band are invisible to the query but **may already be fully processed.** Assume they are unprocessed and retry the write, and you get `INVALID_STATUS`. **Invisible and unprocessed are different things.**

**A list with a required filter shows only that parameter's value space**
On a list endpoint where the status filter is mandatory, **any value you can't enumerate is a band you will never see.** When you need everything, don't fix the list; **find a filter-free single-record path.** The single-record path returned regardless of status, and carried fields the list never had.
★ **Two paths built from the same segments are different resources.** `/{parent}/{id}/child` and `/{parent}/child/{id}` differ only in order; one takes an order ID, the other expects a different kind of ID and returns 400. Segment order is part of the identifier.

---

## A nonexistent enum is not an error; it's 0 rows

**Symptom**
Queried with a status filter, got 0. Read it as "no items in that status."

**Cause**
The filter value was **an enum that doesn't exist** (wrote `APPROVING`; the real value is `IN_REVIEW`). **No error.** `200` with an empty array.

**Fix**
Take filter values from **real data, not docs.** Fetch everything once and count the distinct values of that field. Done.

★ **Count the denominator.** In `0/N`, if you don't know N you don't know what 0 means.

---

## An empty response is not a state

**Symptom**
Single-record fetch returned an empty object `{}`. **Judged dozens of items as "sales suspended"** and **ran unnecessary resume calls on ~100.**

**Reality**
**All were selling normally.** The single-fetch path itself was `PRECONDITION_FAILED`; **the query never happened at all.**

★ **First confirm the query actually happened.** Don't read a state out of an empty response.

**Automation stepped on the same shape**
A stock-watch batch was **judging external fetch failures as "sold out."** When the source blocked us and returned empty, the item went straight onto the sold-out list.
→ Separated fetch failure from real state with a **`_srcfail` flag.** And when **fetch failures exceed twice the real sold-outs and there are 10+ of them**, raise a "verdict unreliable" warning.

★ **If there is no distinct value for "failed," failure will always disguise itself as some normal value.**

---

## Don't read 404 as "deleted"

**Symptom**
Items in the list return 404 on single fetch. More than half of a 30-item sample.

**Cause**
It meant **outside our ownership.** Created by another tool, invisible to our token. **Some returned 403**, and **a 403 in the mix settles it** (exists, no permission).

**Fix**
- Before a batch, **filter the list through the API**
- The list API's `status` **doesn't guarantee ownership**
- A list saved straight from a search response is **unverified** by definition

★ **404 isn't "doesn't exist." It's "not visible with these credentials."**

---

## Don't treat "gone from the list" as a state transition

**Symptom**
An item vanished from the active list, so **a cancellation notice went out.** It was still there, the cancel count was 0, and **it had already been fulfilled.** Cause: missed at query time, or **pagination incomplete.**

**Fix**
- Judge a state **only when a direct query for that state actually finds the item**
- If not found, **hold.** Absence is not evidence.
- Expand the verification query to **all states**

★ **The cost of a false positive is high.** This verdict triggers a cancellation request to an external party.

---

## Every batch reads its target list from a different source

**Symptom**
Built a filter file, wired it into the batch: **0 processed.**

**Cause**
The filter was built against file A; **the batch was reading file B.** Three lists that looked like they pointed at the same targets, three different counts.

| Batch | List source | Count |
|---|---|---|
| Batch A | Progress file | ~4,000 |
| Batch B | Live API query | 8,000 |
| (reference) | Separate collection | 8,000 |

**Fix**
**Build the filter file as an intersection with the batch's own list.** Separate target files per account and environment.

★ **On "0 processed," suspect a misaligned list before suspecting there is nothing to do.**

---

## A summary line is not a reason

**Symptom**
Rejection notice: **"담당자 검토 결과 반려되었습니다"** ("Rejected after reviewer assessment"). That is a **status line, not a reason.** The real reason is in the history endpoint's `comment`.

**What it cost**
Four items in the same product family → **judged it a category restriction** and set block flags on dozens of related items. The real reason for all of them was **image specifications.** **Reverted every one.**

★ **Items registered in the same batch share the same defect.** Simultaneous rejection across a product family can be coincidence.

**Once more: the history query decided it**
2 of several hundred rejected, right after a name-correction batch. **Easy to blame the correction.** History showed **the same rejection reason before the correction.**

★ **Don't attribute a symptom right after a change to that change. History decides.**

---

## Passing at creation time doesn't mean passing now

**Symptom**
An item registered without issue is **rejected with 400** on re-save.

**Cause**
The platform **tightened required-field validation** in the meantime. Existing data survives as-is, but **the moment you write it again it runs through current policy.**

**Specific rejection conditions**
- A required attribute empty, or an evasive filler like `'상세설명 참조'` ("see description") → rejected
- **Empty string also rejected.** There has to be a real value.
- Select-type fields only accept values **from the allowed list**
- **No duplicate item names.** Assign the same name in bulk and it's rejected. Uniquify with a suffix.

**Fix**
- **Don't remove the attribute.** Removing it turns into "required field missing." **Replace the value, don't delete.**
- Fetch allowed values **from the meta endpoint** and pick from there

★ **Rewriting old data in bulk isn't "editing"; it's "re-registration under current rules."** Forecast the pass rate accordingly.

**Caution: the opposite case exists**
Missing required values → "replace the value" is right, but **duplicate values had to be collapsed to one, not filled.** 15 of ~130 failures were this. **Don't apply one remedy to every item.**

**Block the source or the fix reproduces the defect**
While existing items were being corrected, **the registration pipeline was still injecting the placeholder phrase into every required attribute.** However many correction runs went out, new registrations recreated the same defect. Correcting existing items and blocking the source are separate jobs; do the second one first.
★ **The same phrase is allowed in one field and rejected in another.** The "see the detail page" placeholder passes in the disclosure fields and returns 400 in the attribute fields. Judge banned phrases per field.

**Abbreviate the meta and the constraints vanish**
The category meta gives each attribute a **unit, a list of usable units, and an input type.** The saved schema kept only name and required-flag. So a bare number like `"30"` went out without a unit and was rejected. **Preserve** unit and input type from the meta, **combine** the base unit onto bare numbers, and **block** units outside the usable list before the call (no list, no constraint; don't invent one).
★ **The clause after "or" in the error message was the culprit.** A hypothesis built on the first clause cost days. **Every clause in the message is a suspect.**

**Why this bites non-ASCII users**
"See description" fillers are a marketplace-specific idiom; on Korean platforms `상세설명 참조` was accepted for years and then blacklisted. If your market has an equivalent boilerplate phrase, expect the same policy flip, and expect it to hit only on re-write. And the flip is per field: the disclosure block still tolerates `상세페이지 참조` ("see the detail page") while the attribute block rejects it, so a banned-phrase list has to be keyed by field, not by marketplace.

---

## A fallback eats its own output

**Symptom**
Progress file says success (`ok:225`), but recent items are **all exactly 225 characters** long.

**Cause**
Stage 3 of the fallback was **"reuse existing data."** Stage 1 was always failing (the source had no such field at all), so stage 3 **re-read the husk it had made earlier and made another husk.**

**Fix**
**Block any fallback that uses its own output as source.** If the source is missing, leaving it as failed is the honest answer.

★ **A recorded length means nothing if the content is a self-copy; that is not output.**
★ **Identical output across many items is itself the signal.**

---

## Swap only the surface file of a bundle and the inside still points at the old identity

**Symptom**
Replaced the entry file (`index.html`) in a deployment bundle and shipped it. **The old name and old icon show up, and the CDN denies access.** The new screen never appears.

**Cause**
The bundle's internal shell bootstrap had **identity hardcoded.**

```
name              ← the shell uses this to locate its own asset paths → access denied
deploymentId      ← this is what summons the screen. Unchanged, the old version keeps loading
brand display name / colors / icon  ← old identity exposed in the header
```

**A bundle with only its surface file replaced can ship and still never show the new screen.** The code is in; the wiring isn't.

★ **"I swapped the file" and "that file is what actually gets loaded" are different things.**
When transplanting a template or donor bundle, **find and replace every identifier the internal bootstrap references.** If there is integrity metadata (sizes, hashes), recompute it too.

**Left unresolved**
If the platform reissues `deploymentId` at registration, this fix may still not work. **Set the next review as the litmus test; if it fails, abandon the transplant and move to the official build chain.** When you're not sure a fix works, **write down the verdict criterion and the retreat condition in advance.**

---

## PUT returns 200 SUCCESS but one field never changes

**Symptom**
The PUT that turns on the customs-clearance flag returns **200 `SUCCESS`.** Re-fetch, and the value is unchanged. Change the payload, change the state, same result. Every one of several thousand items was like this.

**Cause**
When the item's **delivery-method field** holds a particular value, the customs-clearance flag is **ignored.** Nothing is wrong with the flag itself; **another field decides its fate.** And the delivery-method field is fixed at creation: try to change it and you get 400.

"Some fields can only be set at creation" and "A field can be one-way" above are about a field that **won't change itself.** This one **won't change and blocks another.** New shape.

★ **Don't stare at the field that won't take. Find the higher-level setting that governs it.** You can look at the dead field all day and the cause won't appear, because the culprit is a different field.

**Second case: a "missing" 400 isn't asking for a value**
Registering a branded item returned 400: `"product identifier missing."` Filling in the identifier made it **keep getting rejected.**
**When the brand field has a value,** that validation fires; **leave the brand empty and the validation disappears.** "Missing" didn't mean "supply a value." It meant **"this combination is invalid."**

★ **The field an error message names is rarely the cause.** When you're blocked, don't only look for a value to fill in; **look for the field that triggers the validation and turn it off.** (Brand is one-way, so starting empty is the direction that keeps options open.)

**This is the opposite prescription from an entry above. Keep them apart.**
"Passing at creation time doesn't mean passing now" says **"replace the value, don't delete."** That case is a required attribute: remove it and you get a different error. This case has **a separate field that triggers the validation.** Different mechanism, opposite fix. **Don't apply one remedy to every 400.**

**Fix**
- The governed field can't be repaired, so **re-create the item with a valid combination.** Don't delete the original; deleting halves your exposure.
- In the creation code, **settle the governing field first.** It can't be changed later.

**Verification**
★ **Opening a sample of correctly registered items beats the docs.** The second case was answered not by reasoning but by **opening four items that were selling fine:** all three identifier attributes were empty strings. A payload that passes already exists in your own account. Get a working one and lay it side by side.
And **peel one layer and the one beneath appears.** After the 400s stopped, "normal processing resumed, ~2,500 items" went into the log. Hollow: the 400 was gone and the value still wasn't landing. A rejection disappearing and a value applying are different events.

---

## The watch queue is empty but the rejections exist

One queue watching an approval workflow produced three of these in three days. Each is silent: no exception, no log line, and **an item leaves observation.**

**① The card's title promises more than its source filter returns**
The dashboard card was titled "rejection watch," and its only source was the watch queue. That queue selects `submitted` and `unknown` and **structurally excludes `rejected`.** The card next to it showed "REJECTED: 2" while this one said "no rejections under watch." **The screen contradicted its own title.**
The queue was not widened (watch means "not yet judged," and widening blurs that). A **separate read function** feeds the card, which merges both and labels them apart.
★ **A card title is a contract.** When a filter narrows the meaning, **narrow the title or widen the source.** One of the two.

**② Status was judged from a side signal instead of the authoritative field**
The status verdict looked only at **whether a `comment` existed.** So a one-line memo that was not a rejection ("saved as draft," "reviewer assigned") set the item to `rejected` and **pushed it out of the queue.**
Two layers. A **fallback** returned the last comment whenever no rejection marker was present (the intent was "prevent silent omission"). And the verdict function, while already holding the authoritative state field, decided `"rejected" if comment else "unknown"` on the presence of text alone.
★ **"There is a reason" and "it is rejected" are different propositions.** A fallback meant to prevent silent omission turned non-rejections into rejections and produced a **quieter omission.** **A safety net promoted to a verdict is itself a defect.** Don't remove the fallback; narrow its job. The memo stays so a human can read it on screen; the status comes from the authoritative field only.
★ **Beware the half-fix.** Fixing the verdict alone is not a fix. If the queue's accepted-status list doesn't include the new unsettled state, the verdict is right and **the row still leaves the queue.** Verdict and queue list are two implementations of one idea, so bind them with a contract: the set of unsettled states is a subset of the states the queue accepts.
And the post-mortem didn't reach the bottom on the first pass. The first write-up said "this behavior is correct; the missing re-arm is the defect." That was wrong too. **Fix one layer and the next one shows.**

**③ The remedy never updates the observed status**
The resubmit function (re-request approval) sends the request to the marketplace and returns `{success: true}`. It **doesn't touch** the ledger's status. So apply the remedy to a row that has already left the queue (`rejected`): the request really goes out, the item really re-enters review, and the ledger still says `rejected`, so **the next sweep never looks at it.** Nobody checks the result.
**The harder you apply the remedy, the further out of observation the item goes.** That is the shape of this defect.
It is the reverse of chapter 02, "upsert rolls back workflow state." There a collector reset the status and erased a human's action; here an action leaves the status alone and kills the watch.
★ **An action that changes state must also change the observed state.** "The ledger records what the marketplace answered" is a sound principle, but *we asked again* is also a fact, and that fact decides whether the item is under observation.
- Re-arm the ledger to `submitted` **only on success.** Marking a failure as "back in review" is a fake number.
- Re-arm on **every resubmit path.** Four paths bottomed out in the same function; hook one and the other three keep cutting the chain.
- A retroactive re-arm button touches the ledger only, with no marketplace call. The next scan overwrites it with the real state, so it self-heals.

**Verification**
Print one line per sweep: `in queue N · graduated M · saved a · unknown b · approved c`. Unless you count how many items sit in which state, none of the three is visible. And there is an order: after fixing the verdict, a ledger that already says `rejected` won't be caught on the first sweep. **Re-arm first; it shows from the next sweep.** Miss that order and you get "I fixed it, so why isn't it there?"

---

## A PUT with no body gets 411 Length Required

**Symptom**
The approval request is **a PUT with nothing to send.** The response is `411 Length Required` with an **HTML** body (`<html><title>411 Length Required</title>`). Every other response from this API is JSON, so the first reading is "the relay is broken." It isn't.

**Cause**
Common HTTP clients **send no `Content-Length` header at all** when you give them no body. The gateway rejects a PUT without a length with 411. The HTML is the gateway's own error page, passed through the relay untouched. The relay didn't strip a body; **there was never a body to carry.**
★ **Having no body and not declaring a length are different things.** HTTP allows the first; the gateway refuses the second.

**Fix**
Don't invent a payload (`{}` is an arbitrary value too). **Send an empty body and declare length 0 explicitly.**

```python
body = b''
headers['Content-Length'] = '0'
```

(If the request signature covers only method, path, and date, changing the body leaves the signature alone; this fix doesn't touch auth.)

**There are two gates**
Fixing the client didn't finish it. The request leaves through a **fixed-IP relay**, so there is one more gate. The relay set curl's POSTFIELDS **conditionally** when the body was empty.

```php
if ($body !== null && $body !== '') curl_setopt($ch, CURLOPT_POSTFIELDS, $body);
```

It reads as defensive. "Why set an empty body?" That is the trap. **Setting an empty body is what declares length 0,** so here the condition is the defect. Always set it, even when empty, and discard the caller's `Content-Length` in favor of one recomputed from the actual bytes (a mismatch and the gateway cuts you off).
★ **Every hop adds a gate.** Fix your side and the relay can still drop it. The first fix's mock exercised only the direct leg and went green, which is why this was found late.

**Blast radius**
One 411 spread four layers deep: approval request never lands → item stays in draft → draft has no reason text, so the watch classifier files it as "unclassified" → the dashboard card can't show it (① in the previous entry). **Two days without appearing anywhere on screen.**

**Verification**
★ **The error moving to a different layer (411 → 401) is the evidence of repair.** After the relay deploy, the same call returned 401 instead of 411. 411 gone means curl attached a length; the remaining 401 belongs to the auth layer. The transport layer is finished, so you can move on to the next one. An error that moves is better than one that goes quiet. Then `success: true`, then the item entered the review queue: **each step is the evidence for the next.**

---

## A "duplicate option value" error was about IDs, not values — and errors come in layers

**Symptom**
Expanding options (variants) and sending a full PUT returned `400`:

> `duplicate option value`

It says **value**, so we looked at attribute values. Allowed lists, formatting, duplicate combinations. **Three fixes, three dead ends.**

**Cause**
Variants were being built by `deepcopy`ing one prototype — and **the copies carried the prototype's identifier field along with everything else.** Every variant went out **carrying the same ID.** What the platform called a "duplicate option value" was **the option identifier, not an attribute value.**

★★★ **`deepcopy` does not copy only "values." An identifier is a value too.** Prototype cloning is **an operation that manufactures sameness**, so the one field that must be unique quietly rides along.

★ **Make "clear the ID fields immediately after cloning" the rule.** "Each one fills its own in later" **fails silently the first time you miss one** — that record ships with the prototype's ID. Clearing makes a miss visible; overwriting makes a miss look normal.

★★ This is not a badly designed identifier. The field was correct and unique. **We broke the uniqueness by making copies.** Uniqueness usually breaks by **truncation** (a length limit collapsing distinct keys) or by **inheritance from a parent**; **cloning is the third path.**

**★★★ The noun in the message does not name the cause**
There is no guarantee the platform's word and your word mean the same thing. "Value" pulls you toward values — but that word belongs to **their schema's vocabulary.** The same shape shows up elsewhere in this collection: a "missing field" message was really about **the validation that field switches on**, not the field.

★ **An error string is location information, not cause information.** It says look near here; it does not say this is the culprit.

**★★★ Truncating logs at 100 characters keeps the answer off your screen**
**The full message contained the list of duplicated IDs.** The answer was inside the response the whole time; the log format was cutting it off.

★★ This collection already carries the rule **"treat every clause of the error text as a suspect."** We wrote it down and stepped on it again — last time by not reading past the `or`, this time because **the full text was never retained at all.**

★ **Writing down a rule and fixing the log format are different pieces of work.** → **Never truncate a failure response.** Summarize successes. Failures are rare, and rare is exactly what you can afford to log in full.

**★★★ The next layer — fixing one reveals the next**
Clearing the IDs produced a different error:

> `cannot delete an item that is on sale`

In a full PUT, **the list you send is the final state.** Sending a new list without the existing items reads as **a delete request.** Items on sale cannot be deleted, so the correct shape was **keep the original as the first item and append the variants after it.**

| Layer | Message | Actual cause |
|---|---|---|
| 1 | `duplicate option value` | cloning carried the identifier |
| 2 | `cannot delete an item that is on sale` | existing items must be retained |

★★ **The first error going away is not the same as being fixed.** A next layer appearing is the normal course. If no layer appears, **confirm by re-reading the resource** — which is the first sentence of this chapter.

**How to verify**
★ **One layer at a time, changing one hypothesis per retry.** Fix three places at once and you will not know which one peeled the layer. And assert identifier uniqueness on the payload right before sending: `len({x.id for x in items}) == len(items)`. That one line would have saved three wasted rounds.
