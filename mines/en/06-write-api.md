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

**Why this bites non-ASCII users**
"See description" fillers are a marketplace-specific idiom; on Korean platforms `상세설명 참조` was accepted for years and then blacklisted. If your market has an equivalent boilerplate phrase, expect the same policy flip, and expect it to hit only on re-write.

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
