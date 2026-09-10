# Python · DB · Data logic

Half of this chapter is one shape: **silent failure.** Failure that looks like success, or looks like a fact.

---

## Silent failure — when failure looks like success (the general case)

No exception, no log line. There was a day with five of these.

| What it said | What was true |
|---|---|
| CI green | Nothing actually ran |
| Search: 0 results | A 2KB bot-block page |
| Progress file: `ok:225` | It re-read the husk it had produced itself |
| `PUT 200 SUCCESS` | Value unchanged. Six weeks of no-ops |
| Function: "none found" | It was treating a tuple like a string |
| Cron exited 0 | The guard caught itself; the job never ran once |
| `registered: true, reason: null` | Zero images |
| Doc says "all deleted" | 68 left |

**Principle: look at the raw data before you rule**
- 0 results, "not found", success flags are **observations, not conclusions.** Look at how the observation was produced first.
- Read the **original fields**, not the summary or status string.
- Don't check whether it says "done"; **count how many came out.**
- **Check response size and type.** `len < threshold` or an unexpected type means failure.

**When only a traceback is left and even `"new: 0"` never prints, dead and empty look the same**
A notification batch died on a `KeyError` — bracket access (`rec['url']`) on one field of one record of external data. The log held a traceback and nothing else; the `"new: 0"` line a healthy run prints was missing too. **"No orders today" and "the batch is dead" produce the same log.**
- **Log one line at batch start and one at batch end.** Even `"new: 0"` has to appear, or death and absence are indistinguishable.
- **Treat every field of external data as optional.** Use `.get()`. Bracket access kills the whole run over a single record missing one key.

---

## "Absent" and "not found" are different facts

**Symptom**
A query returns 0 rows. Two readings branch here and they lead to **opposite conclusions.**

| Observation | Reading A (absent) | Reading B (failure) |
|---|---|---|
| Search: 0 | The thing doesn't exist | **Random bot block** |
| Mail: 0 | No new mail | **Caught by the SINCE / LIMIT filter** |
| Item not in catalog | Discontinued | **Didn't scrape enough pages** |
| Batch processed 0 | Nothing to do | **Target list came from a different source** |
| 0 characters of text | No body | **Body is nothing but image tags** |
| `products.json` 404 | No catalog | **Just not that platform** |
| Domain not found | No site | **You guessed the domain** |
| Aggregate says "no catalog" | Never collected | **Collected, but never registered in the mapping table** |

**How to tell them apart**
- **Look at the response size.** A 2KB response where 2KB can't be a valid answer is a failure.
- **Loosen the conditions one at a time.** Widen date, count, status, type, and see **whether the 0 survives.**
- **Cross-check via another route.**
- **Count the denominator.** In `0/N`, **if you don't know N you don't know what 0 means.**

**What it cost**
Three days for not making this distinction: four locales misjudged as "out of stock"; 12 emails judged as 0 (three times over); a batch with 0 targets; a "discontinued" verdict where the real story was a different domain.

**Blocking is random per request and per locale; a single query cannot judge**
The same query ran twice. Round one: only one locale succeeded (1.1MB). Round two: that locale was the only failure (2.2KB) and the others succeeded. It isn't a locale problem — it's **random per request.** Every "no source" verdict made from four locales returning 0 had to be re-checked.
- Before trusting a result, check **`len` against a threshold (under 50KB is a block) and the presence of a core marker** (the result-item tag).
- On failure, **retry with exponential backoff** (6/12/18s, four attempts).
- ★ **Don't try to win by retrying.** Image collection from the same source hit the same block and returned 0 images run after run. If a source that doesn't block exists (originals already registered in your own system), **pivot to it** and demote the blocked source to a fallback.

**Mail: 0, a crash, and missing IDs — three traps from one collector migration**

| Symptom | Cause | Fix |
|---|---|---|
| Order number not extracted | regex `{6,20}` — one vendor uses **5 digits** | Don't assume ID length. `{4,20}` |
| Crash | header charset `unknown-8bit` blows up the decoder | **Fallback chain**: utf-8 → cp949 → euc-kr → latin-1 |
| Mail: 0 | `SINCE 7 days` and "last 120 messages" hard-coded as defaults | Defaults live in **env vars** |

★ **ID length, charset, and query window are all facts about the other side.** An assumption baked into your code shows up as 0 rows or a dead run the moment they change — and 0 rows looks like normal.

**★★★ Interpreting a zero requires a control — and once writes are attached, give the verdict a third value**
A shipping-quote API returned **zero options** for one country. Read as "we can't ship there," it triggered **a routing change on 60 records.** Wrong — that store **computes shipping at checkout**, so this API returns **zero for every country you ask about.**

★★★ **Making the same call once more with a different input separates the two cases.**

| Observation | Meaning |
|---|---|
| zero for the target country, **others return options** | **genuinely unavailable** |
| **zero for every country** | **this store doesn't use this API → undecidable** |

★★★ **To interpret a zero you need an input you expect to be non-zero.** That is the control. Without one, **"my query is wrong" and "they don't use that feature" both look like `0`.**

**★★★ So the verdict has three values, not two**

```python
True   # confirmed (or there is a past record of it) → use the measured value
False  # the control responded and only this target is zero → genuinely unavailable
None   # the control was also all zeros → undecidable
```

★★★ **And `None` does not mean "defer," it means "do not write."** Leave the existing value exactly as it is and **do nothing.** In another classifier in this collection, `UNKNOWN` meant **retry** — but that was a read, and this is **a position that can overwrite existing data.**

★★ **A write-side abstention must be stronger than a read-side one. Not "don't read when you don't know" but "don't change when you don't know."**

★★★ This collection already holds three cases of **reading "not found" as "not there"** — a failed fetch as out-of-stock, a blocked search as zero results, a rate limit as high risk. **Those three stopped at a wrong verdict; this one changed the data.** ★ **Build the `None` path before you attach writes to a classifier.** The same bug costs something entirely different once a write hangs off it.

**★★ A record of actual outcomes beats any static check — don't add it to the score, intercept ahead of it**
That store had **an actual delivery record to that country.** The fix was to check the tracking history first and **skip the API verdict when it exists.**

★★★ **Ordering is the whole point.** The same signal was being used in an earlier scorer as **one `+1` line item** — and **adding your strongest evidence in the same unit as your weakest dissolves the strength.** The proof: in that scorer, **the highest-scoring subject turned out to be one we cannot actually transact with.**

★ **Static checks accumulate "probably"; a record states "it happened."** When you have the latter, there is no reason to consult the former — make it an **override**, not a line item.

**⚠️ ★★★ But an override must not outrank a blocklist**
That classifier kept its blocklist — counterparties that had already caused real losses — as **one of the penalty rules.** If the override "skips the static checks," it **skips the blocklist too.**

★★★ **A counterparty that transacted normally once and then turned fraudulent sails straight through.** The real loss case was "paid, never shipped" — and **if even one order had shipped normally before that, it would score as maximally trustworthy today.**

→ **Pin the precedence explicitly.**

```
① blocklist          — reject unconditionally
② prohibitions on a separate axis — score-independent (rights issues, etc.)
③ track-record override — only here do you skip
④ static score
```

★★ **An override is evidence of safety, not authority to lift a block.** ★★★ **A skip that doesn't say what it skips will skip the blocks too.**

**⚠️ ★★ And a track record is a fact about the past, not a guarantee about the present**
★ **Don't let a success from a year ago vouch for today.** Weigh the record's **recency**, and demote stale ones from override back to **line item.**

★ Implementing the override as **a large value inside the scoring system** (a 99 that dwarfs the threshold) is a good choice — it clears the threshold decisively while **still coming down if a penalty lands on it.** Putting ① and ② ahead of it makes that design safe.

**★★★ One more — a new classifier loses facts you paid dearly for**
The `None` (undecidable) list contained **a target already settled in the past.** For that one we had established that **"the policy claims availability but the country is absent from the actual list"**, after registering 32 items and pulling all of them. That expensive fact came back as **"unknown"** in the new classifier.

★★★ **`None` must mean "not looked at yet," never "looked at before and forgotten."** Since `None` means keep-existing-value there's no immediate damage, but **storing that `None` buries the earlier finding.**

★★ **Put manually confirmed values above the classifier** — one `manual_verdict` field. However sophisticated automatic scoring gets, **it cannot outrank a fact a human established by experiment.** Whenever you write a new classifier, first ask **where the previous conclusions were kept.**

**★★ And aligning keys comes before matching**
The name/domain mismatch above happens **because each store picked the key that was right in its own context** — a human-read log uses brand names, a machine-scraped catalog uses domains. **Both are correct choices; the problem appears only when you join them.**

★★★ **An alias table is a remediation for past data, not a solution for future data.** Add a **shared key field on the writing side and populate it at write time.** Otherwise **match accuracy becomes permanent debt.**

**★★ Aside — two stores call the same entity by different names**
The order history used **brand names** (including local-language forms); the catalog used **domains.** **String matching will never connect them.** Keep an alias table as the source of truth and use first-word name matching **only as a fallback** — ★ invert that order and you reproduce this collection's **three consecutive mismatches from matching on names.**

**It was collected, and the aggregate still says "absent"**
Collect a catalog but never add it to the brand mapping table, and the aggregate reports "no catalog". The top 25 brands all showed ✘ when several were already sitting in the catalog. **Collection and mapping are separate jobs.** Registering in the mapping table right after collecting is part of collecting.

---

## Assume the return schema and you spin silently

**Symptom**
`h = get(...)`, then `in`, regex, and length checks on `h`, and **every single item comes back "not found."** No exception.

**Cause**
`get()` was returning a `(status, body)` **tuple**. `in` on a tuple is element equality, always False; `len()` is 2. Every line is syntactically valid, so nothing dies.

**Fix**
Unpack: `status, body = get(...)`. And **don't assume the return schema; print it once, then use it.**

**Verification**

```python
print(type(r), repr(r)[:200])
```

Same for progress files and aggregation inputs. `list(d.items())[:3]` to see the value schema first. An aggregation run on an assumed schema returns 0, and **0 gets misread as "no data."**

---

## A progress file that doesn't record the result makes post-hoc audit impossible

**Symptom**
`*_done.json` stores only `{id: true}`; **what was written is gone.** When bad output is discovered later, you can't count how many of the ~2,000 completed items are bad without hitting the API again.

**Fix**
Minimum three fields per done entry: `{id: {ts, len, src}}`. With the generated body length and the source, a full audit can be done locally.

**★★ A prefix-format value changes which operator is correct**

Putting a reason into the value is good — it records *why* something was handled that way.

```
done[x] = "ok:1234567890" / "skip:policy_excluded" / "manual:needs_review" / "fail2"
```

**Then the check must be `startswith`.**

```python
done_ok = str(v).startswith(("ok", "skip", "manual"))
```

★ **`!= "ok"` and `not in ("ok", "skip")` pass for every prefixed value.**
`"ok:1234567890" != "ok"` is **True** → **every completed item gets reprocessed.** No error, normal logs, and **the queue never drains.**

**Safer shape — separate the verdict from the detail**

```python
done[x] = {"state": "ok", "detail": "1234567890"}
```

Pack two things into one value and **every reader has to honour the parsing convention; one place gets it wrong and it leaks.**

**The same operator hazard, other direction**

| Value scheme | Wrong operator | Result |
|---|---|---|
| `"ok:123"` | `!= "ok"` | done read as not-done → **infinite reprocessing** |
| `draft` / `draft_pending` | `== "draft"` | the second one is **silently dropped** |

★ **When values share prefixes, both `==` and `!=` are dangerous.** One drops items, the other passes everything.
★ **Decide the value format and the check code together.** Change the format later and the check flips silently.

**★★ Not saving before `continue` throws the decision away**

If a loop **changes state in memory and then continues**, a crash or an interrupt before the next flush **erases the decision itself.** The next run sees the item as if for the first time.

★ **Save the moment you change state. Do not rely on a save at the end of the loop.**

This is one layer away from "record failures too" — there the record was never *conceived*; here it was **made and then never written.**

**Four shapes produce the identical symptom**

Four different ways to get the same progress file wrong. **All four were hit in one day.**

| | Shape | Symptom |
|---|---|---|
| 1 | Changed the value format, left the check | `"ok:123" != "ok"` passes → reprocess completed work |
| 2 | Compared with `==` | prefix-sharing values silently dropped |
| 3 | Marked `ok` from the response alone | no re-query → **the whole completion log is fiction** |
| 4 | Did not save before continuing | the decision vanishes → **infinite reprocessing** |

★ **None of the four raises an error, and all four leave the queue full.**
So **if you fix one and the symptom stays, read it as "there is another shape", not "it is not fixed".**

**The rule — you need all three**

1. **Check with `startswith`** — with prefixed values, `==` and `!=` are both wrong
2. **Save immediately** — the moment state changes
3. **Confirm completion by re-query** — the response is not evidence

★ **Miss any one and the queue stays full. And the symptom does not tell you which one you missed.**

**The trap you step on next: confusing "couldn't process" with "no longer needs processing"**
Don't record failures in `done` and you get an **infinite retry loop.** Classify "no longer needs doing" as unprocessed and the list never empties; the batch repeats the same work every 20 minutes (385KB of logs and counting).
→ **Record failures too, but as a distinct state from success.**

---

## `continue` in an early fallback stage kills every stage below it

**Symptom**
Four fallback stages stacked; ~100 items recorded as "no source." They were in fact recoverable.

**Cause**
Stage 1 (web search) fails → `done[id]="nourl"; continue`. Stages 2, 3, and 4 **never executed.**

**The point**
The failure reason in a progress file tells you **which stage exited,** not "every option was exhausted." Before you prescribe based on a failure code, check **where in the chain that code gets written.**

---

## A success response with "zero of the core output" is not success

**Symptom**
47 of 47 registrations: `registered: true`, `reason: null`. All successful. And **every one had zero images.** Nobody knew until a human looked at the result.

**Cause**
Assumed the shape of external data. Entries were `{name, sources:[{url, priority}...]}` but the code flattened with `v.get("url")`, so every URL was `None`. Empty URL, so collection never ran. Registration still succeeded.

**Fix**
- Success + `image_count == 0` → `warning`, and **surface it** in the top-line tally.
- **Never assume external data format.** Open one real record and check the keys.

**Rule**
Collection = images, registration = images, translation = translated text. **"Zero of the thing that must exist" is never allowed to pass quietly.**

**An empty record with only a price passed registration and went on sale**
The residue of a failed scrape — no body, no attributes — got a price attached, passed registration validation, and was found on sale. When an order comes in **there is nothing to purchase.** An unlinked source means "I don't know where to buy it"; this means **the product does not exist.**
Four indicators of an empty record (compared against a healthy one):
1. **A single image with a hash filename** — a healthy record has a vendor-code filename plus two or more model shots
2. **Every attribute blank**, empty body
3. An option that is a **placeholder string** ("see description")
4. **Disclosure form does not match the category** — a phone accessory carrying the auto-parts form

★ If registration validation checks "has a price" but not "has the core output", failed residue walks through the same door as a healthy record.

---

## A "done" record does not mean done

**Symptom**
~1,000 items logged `ok`; a sample of 40 was entirely unchanged. The only evidence for `ok` was `status_code == 200`.

**Fix**
When you record completion, **record what verified it**: `re-fetched N` / `re-fetched all` / `unverified`.
Unverified completion is written as **"executed"** and nothing more.

Enforce the success predicate as a function:

```python
def ok(code, resp):
    return code == 200 and isinstance(resp, dict) and resp.get("code") != "ERROR"
```

Without it, ~700 items spun for nothing. All rejected, all recorded as `put`.

**A contaminated done-list corrupts the denominator of the next job**
A correction batch recorded 2,608 items `ok` on nothing but `PUT 200 SUCCESS`. A full-verification sample: **60 of 60 unchanged.** Those 2,608 were counted as done and **excluded from the next round's "remaining" set** — the fiction didn't stay inside one batch; it poisoned the denominator of everything after it.

The enforced protocol:

```
write → wait → re-fetch → compare → ok only on match
```

- If re-fetching everything is expensive, **re-fetch a sample every round** and record the ratio alongside.
- If the sample is **entirely unchanged, stop immediately.** 60/60 was that signal.
- ★ **Never store response-based `ok` and re-fetch-based `ok` in the same field.** Once they mix you can no longer tell which completions were verified.

---

## A UI that trusts a stored verdict keeps the old state alive

**Symptom**
Data fixed; the screen still shows the old verdict (a failure badge, an old count).

**Fix**
**Recompute on read.** Stored values are a cache, not a source of truth. Recompute in **both** the list and the detail view.

---

## Reprocessing a display copy leaves contamination behind

**Symptom**
Re-translating an already-translated title defeats the boilerplate stripper and leaves residue.

**Fix**
Re-translation and recomputation **always start from the source** (`title_en`, not `title_ko`).

**The trap**
A `_ko` field often hides in the source fallback: `description or description_ko`. When the source is missing, you re-translate the display translation (Korean → Korean). Fixing one field is not enough; **check every sibling field's fallback for a display copy.**

**Why this bites non-ASCII users**
If your product runs in a non-English market, you carry two copies of every text field: the original (usually English) and the localized display copy. Any pipeline that "helpfully" falls back to whichever is present will eventually feed the localized copy back into the translator. English-only shops don't have this failure mode. You do.

---

## Two code paths computing the same value will diverge

**Symptom**
"It's right on the review screen, but the sent / saved value is 0 or empty."

**Cause**
The review screen (GET) and the actual send (POST) **each** called the same builder function. Only one injected the exchange-rate parameter. GET displayed a price in the hundreds of thousands of won; POST got `None` → `int(None or 0)` → **sent 0.**

**How to spot it**
- Is the same domain value (price, category, key) **built in more than one place?**
- The **difference in argument lists** between the two call sites is the size of the divergence.

**Fix**
1. Collapse into a **single-source helper**
2. Compute derived values **once and pass them through**
3. **Don't demote "unknown" to 0.** `int(x or 0)` turns "I don't know" into "zero" and sends it quietly.
4. A contract test that pins **displayed value == sent value.** Testing the two sides separately will never catch the split.

**Not only two code paths — the canonical system and a local copy diverge too**
The sourcing map's `krw` disagreed with the marketplace's actual listed price. The marketplace is canonical; the local map is a copy. **Compute margin from the copy and you get the wrong answer.** The split isn't limited to two code paths; "canonical system vs local copy" is the same shape.
In the same map, 618 of 6,541 records had both `usd` and `jpy` empty. A source can be linked and still be useless: **a record missing the price is equivalent to an unlinked record** as far as the margin check is concerned. Treat a missing required input the same way you treat a missing link.

**An upstream 0 turns a derived price negative**
One channel had products whose sale-price field was 0 (a temporary-failure status, among others). Pulled as-is and fed into a derived price for another channel — `cost − random` — the result is **a negative price.** The derivation formula assumes the upstream value is sane. **Put a lower-bound check right before the derivation.** A 0 is often not "a value" but "no value" wearing different clothes.

---

## Never read batch progress as an overall rate

**Symptom**
Watching the log during a batch, failures were **only 8**. "Almost done."

**Cause**
That was **the front of the batch only.** Sampling across offsets gave a completely different distribution.

| offset | success |
|---|---|
| 0-4,000 | **92-95%** |
| 6,000 | **44%** |
| 8,000 | **0%** |
| 9,400 | **84%** |

**The real figure was 68.3%.**

★★ **Sort order manufactures bias.** Sorted by creation date, **the front is the newest data and therefore the best maintained.** Estimating the whole from the front is always optimistic.

**Fix**
- **Sample across offsets** — not N from the front, but **N per band**
- Log **how far you got**, not just the failure count. `"8 failures"` without a denominator says nothing
- ★ **Look for bands at 0%.** An average hides them

The same thing happened with sample size. The survey was run three times and **all three were wrong in the same direction.**

| Sample | Defect rate |
|---|---|
| 500 | 36% |
| 1,900 | 48% |
| 4,900 | **69%** |

★★ **If an estimate keeps getting revised in one direction only, it has not converged yet.**
If it worsened every time you widened the sample and never once went the other way, **the current figure is still a lower bound.**
**Small samples and front-loaded samples both err optimistic.**

---

## Two metrics were naming the same set

**Symptom**
"Cost unknown" and "source unlinked" were counted as **separate problems, each getting its own fix.**

**Reality**
The 31.7% with no cost was **exactly the unlinked set.** No wonder adjusting the formula or the match threshold moved nothing — **there was nothing to compute from.**

★ **Different metric names do not mean different targets.** **Count the intersection once** and you are done.

---

## Key normalisation has two directions

Keys for the same thing drift apart in **two** ways. Fix one and the other stays.

| Direction | Cause | Symptom |
|---|---|---|
| **different to same key** | truncation cuts the distinguishing suffix | overwritten; **only the last survives** |
| **same to different key** | re-registration **appends a suffix** | the lookup **never matches at all** |

```
B0XXXXXXXX -> B0XXXXXXXXAB -> ...R / RR / RRR
```

**Fix**
1. **Expand candidates** — original / suffix-stripped / prefix-stripped
2. Cross-check against a **lowercased, punctuation-stripped index**

75% matched after applying this (6,657 of 8,858).

★ **Some never match even with expansion** — they were minted under a different scheme entirely. **If you do not write the counterpart key at minting time, there is no recovering it later.**

**The first direction in practice — the overwrite shows up as "unindexed"**
The external SKU is the source handle truncated to 38 characters, so variants collapse onto one key. `index[key] = id` keeps **only the last one; the rest are unindexed forever.** They didn't fail processing — **there was no slot for them in the index.**
- `key → id` is **1:N.** A dict that assumes 1:1 is the wrong structure → keep a separate `id → key` reverse index and let the forward side hold a list.
- Applied: unindexed 2,443 → 2,143. 300 items resolved without touching the data.

★ **If "unindexed: N" doesn't shrink round after round, suspect key collision, not processing failure.** A stalled metric can mean **"nowhere to land"**, not "the work didn't happen". The job exits clean every time; only the number refuses to move.

Truncation length differs per system:

| Where | Truncated at |
|---|---|
| Marketplace A, stored external SKU | **20 chars** |
| Local index key (source handle) | **38 chars** |
| Marketplace B, seller management code | **30-char limit** |

Knowing "it gets truncated" is not enough. **The cut-off length defines the collision set.** The same data cut at different points per channel collides differently on each.

**★★★ And the remedy is not to shorten but to reorder**
Option names truncated at 25 characters left **every option with the same name.**

```
"Standard (Single Passport) / Green"   ← first 25 chars identical
"Green / Standard"                    ← the distinguishing part moved up front
```

★★★ **Truncation always discards the tail. So put what distinguishes up front.** Before shortening the string or appending a hash, **look at the order** — reordering alone keeps **a name a human can still read.**

★ And the common convention points **exactly the wrong way.** Naming that leads with a shared prefix (spec name, brand, category) **reads well and truncates worst.** **Don't use the same naming scheme for fields cut at the front and fields cut at the back.**

**Key expansion must be applied at every lookup site**
Put the suffix/prefix expansion into five of six batches and the sixth **stays unmatched forever, on its own.** "The fix is decided" and "the fix is in every call site" are different facts. `grep` every call to the lookup and count them before calling it done.

---

## Two checks before you use a field as an identifier

**Before a field becomes a key:**

1. **Is it unique?** No collisions.
2. **Is it meant to identify?** Does the field **exist to point at the target?**

**Check ① without ②** and you'll key on a search field like tags.
**Check ② without ①** and a legitimate identifier will bite you through truncation or parent-sharing.

| Field used | What broke |
|---|---|
| External SKU field | **①** — stored truncated at 20 chars. Duplicates in the **40% range** |
| Indexing by product name | **①②** — state files mixed, an empty husk claimed the slot first |
| Product-name matching | **②** — three incidents in a row |
| Platform `tags` | **②** — long-tail search field. One tag misfiled a whole product line |
| Progress file name | **①** — another script used **the same name with a different format** → ~200 items lost |
| Category **name** | **②** — partial-match false positives. Fixed by pinning to leaf **ID** |
| Two fields on one record | **①** — the key and the URL pointed at **different targets** |
| Mail sender domain | **②** — it is the sending infrastructure's domain, so every store shares one value. **Second-stage check on the From display name** |

**Rules**
- **Never match on a single field without cross-checking.**
- **Eyeball a sample of every match result.** A plan with dozens of mismatches nearly passed because "the names looked right."
- Before creating a progress file, **check it isn't taken**: `grep -rn "filename" *.py`
- **If one record has two fields pointing at the same target, compare them.** They can disagree with no error.

**Prefix lookup on a truncated key: adopt only when unique**
The external SKU is cut at 20 characters, so the original key can't be found and you fall back to a prefix search. Within one brand's 300 items, 42 collided on the first 20 characters. **If two or more candidates match, give up** and hand off to the similarity fallback. Unlinked beats mislinked.
Measure link rate against a **fixed denominator** (what is registered). The map total keeps growing because other scripts keep adding to it; measured against the total, progress looks like nothing.

**Extension and declared MIME are not evidence of format**
PNG bytes uploaded with `image/jpeg` declared: upload 400. The filename and the declared type are labels a human attached; they fail check ②. **Judge the format by magic bytes**, convert to what the receiver accepts, then upload.

**Repair procedure when two fields on one record disagree**
46 of 1,928 records had a key and a URL pointing at different products — **a direct path to ordering the wrong item.**
1. **The side registered in a separate index is canonical** — if the key exists in the SKU index, trust the key.
2. **Regenerate the other side** (the URL) from the canonical one.
3. **Validate that both fields name the same target at insert time.** Cheaper than reconciling afterwards.

**The reverse of "different things, same name" — the same thing got two names**
`.job_seen` and `.jobs_seen` both existed. One plural `s` **split the processing history across two files**: what A recorded B didn't know, so B reprocessed; what B recorded A didn't know, so A never sent. No error. It isn't a typo — it **is a separate file.**
- State-file paths live in **one constant.** Never scatter them as string literals.
- **Two similar names are themselves the signal** — singular/plural, underscore or not, an abbreviation.

Exactly the mirror of the progress-file row above: that was different things sharing a name; this is one thing with two names. **Both come from not treating the name as a contract.**

---

## Name matching without a score causes incidents where money is involved

**Three in a row**

1. Searched by Korean product name, matched the wrong product → a different item was delivered
2. Variants matched to each other → recommended prices off by 5×
3. Similarity fallback at 0.80 matched sibling products → **an item priced around ₩100,000 got a target price around ₩900,000**

**Signal of mismatch**
★ **The same target value repeating 5+ times is a mismatch.** One value actually repeated 15 times.

**Fix**
- Threshold **0.92, with a 0.04 gap from the runner-up**
- **Duplicate-result warning** at completion
- Block auto-apply when **5+ duplicates or a swing over 200%**
- ID first; name is the **last resort**

**Warning: raise the threshold and the other side blows up**
Raising 0.80 → 0.92 to stop mismatches **exploded the unmatched count** (over half of 3,000 came back "cost unknown"). The real cause wasn't the threshold; it was that **there was no direct lookup path at all.** An indexed direct path comes before similarity matching.
★ If the direct-lookup index doesn't auto-include new registrations, switching to the direct path returns the same result. **Refresh the index before switching paths.**

**Unlinked beats mislinked.** Unlinked means "I don't know." Mislinked means **"I believe a wrong thing is known."**

**Why this bites non-ASCII users**
Fuzzy-matching libraries and their default thresholds are tuned on Latin-script data. Korean product names are short, dense, often written without spaces, and the same product appears with mixed Hangul / Latin / digits across sellers. Edit distance behaves differently on syllable blocks than on letters, so a threshold that is "safe" for English is loose for Korean. Calibrate on your own script; don't borrow the number.

**Partial matching feeding a metric shown on screen turns a wrong value into a wrong decision**
A shipping bot attached cost by partial name match, and a margin of `-101%` landed on screen as-is. Margin is a number a person acts on where they see it, so **a wrong value is a wrong decision.**
- Attach cost by **exact SKU match only.**
- ★ **If not found, show blank.** Fill in an approximation and you have put "believing a wrong thing is known" on the screen.

---

## Korean / CJK substring matching: short words swallow long ones

**Symptom**
A short Korean token registered as a filter swallows unrelated longer words.
`마블` (Marvel) ⊂ `마블링` (marbling) · `핑` ⊂ `쇼핑` (shopping) · `코브라` (cobra) ⊂ a toy product name.

**Cause (a real trade-off)**
- ASCII tokens can use **word-boundary matching** (kills `ping` in `shopping`, `lodge` in `dislodge`)
- Korean / CJK routinely concatenates without spaces (`몽클레르패딩`, "Moncler puffer" as one run), so word boundaries produce **misses** → you keep substring matching → **short tokens swallow long words.**

**Why this bites non-ASCII users**
`\b` is an ASCII-era idea. In Korean, Japanese, and Chinese the space is optional, and product listings drop it aggressively to save characters. There is no boundary for the regex engine to find. Every off-the-shelf keyword filter assumes there is one.

**Fix (exception list, not a rule change)**
Leave the boundary rule alone and add **true-positive protection exceptions**: if **every occurrence** of the term is inside an exception word's span, ignore it; if any occurrence is outside, it's a real hit. Concatenated true positives (`몽클레르패딩`) survive.
Adding an exception is one line in a list; the matching rule itself is untouched.

**In a first-match rule table, a generic pattern swallows compounds**
A rule table mapped item words in English product names to Korean category words. `pen → 만년필` (fountain pen) captured `Tactical Pen`, so a tactical pen became a fountain pen; `mount → 거치대` (holder) captured `Rail-mounted`, so a rail-mounted product became a holder. Same swallowing, other direction: above, a short token swallows a long word; here **a generic pattern swallows a compound.**
★ **Put specific patterns before generic ones.** In a first-match table, order *is* priority. Before adding a row, ask "which existing rows does this pattern swallow?"

**Why this bites non-ASCII users**
The table exists because the source names are English and the buyers search in Korean — a translation table is what turns a Latin-script listing into something a CJK search index will hit. Any shop localising into a CJK market runs a table like this, and the first-match trap ships with it.

---

## Delete the files, then run an orphan check against those files, and you wipe everything

**Symptom**
Deleted source files during disk cleanup, immediately ran an orphan check → **~16,000 attachment records in the DB flagged as orphans → deleted.**

**Fix**
Before a mass DELETE: **backup + re-examine the criterion.** The backup is what made recovery possible.

★ **If the criterion depends on a state I just changed, the check is void.**

---

## upsert rolls back workflow state

**Symptom**
"I definitely marked this as processed, and it's back in the list."

**Cause**
The collector's records carried `'status': 'new'`. The collector cron runs every six hours with a `merge-duplicates` upsert, and it **reset every status a human had changed back to the initial value.** Already-published items were resurrected as candidates. One more day and a duplicate publish would have gone out.

**Rules**
- **Strip workflow-state fields from collector records right before upsert** (`r.pop('status', None)`)
- **The consumer owns state, not the collector.** The collector writes facts only.

**How to recognize it**
"I marked it and it came back" → compare against the sync interval.

---

## Truncation that keeps the value from changing = infinite loop

**Symptom**
Process `Killed` (exit 137). **Looks like out-of-memory.**

**Cause**

```python
while cand in seen:
    cand = f"{cand} {i}"[:99]
```

If the name is **already 99 characters, truncation means the value never changes** → loops forever. Measured memory was 36MB. The cause was a **CPU-bound infinite loop.**

**Fix**
- **Always put a counter in the loop exit** (`_t < 20`)
- ★ **A length cap after an incrementing operation breaks monotonicity.** There is no longer any guarantee the value changes.

**Every** piece of code that uniquifies by appending a suffix (SKU, filename, item name) has this shape.

**Verification**
Don't assume `Killed` is memory. Measure with `ru_maxrss`.

---

## `curl -o` writes the 404 body to the file too

**Symptom**

```
SyntaxError: illegal target for annotation
```

An error with no visible cause. The downloaded `.py` file actually contained the string `404: Not Found`.

**Fix**

```bash
curl -fsSL -o out.py URL || echo "download failed"
```

`-f` doesn't create the file on failure. Verify immediately after download:

```bash
python3 -c "import ast; ast.parse(open('out.py').read()); print('OK')"
```

---

## A shared state file with no owner gets clobbered whole

**Symptom**
One JSON state file **read by 3+ processes and written by 2** (a 30-minute cron, a 16-minute cron, a manual batch). Any write that lands between another process's read and write erases everything in between.

**Fix (you need all three)**

1. `fcntl.flock`
2. **Reload after acquiring the lock.** The lock alone is not enough: write from a value read **before** the lock and the changes in between vanish.
3. Atomic replace with `os.replace`

★ **Same root as the progress-file name collision: a shared resource with no owner.**

There were days with zero loss. **Pure luck.**

---

## Match the Python version of the deployment target

**Symptom**
A script that runs locally dies on the server with `SyntaxError` — a **parse-time** failure, so not a single line executes.

**Cause**
Shared hosting and older servers commonly default to **3.9**. Your laptop is on 3.11-3.12.

| Syntax | Requires |
|---|---|
| `match` / `case` | 3.10+ |
| union type hints | 3.10+ |
| `tomllib` | 3.11+ |
| `itertools.batched` | 3.12+ |

**Fix**
- Run `python3 -V` **on the server first**
- ★ **Versions differ per execution site even inside one project** — the PaaS runtime and the SSH box being different is normal
- One parse pass at the lowest version catches it: `python3.9 -m py_compile *.py`

---

## The validator had the very shape it was meant to catch on its allow-list

**The incident**
An automation **wrote the wrong value into an external system.** Vendor A's order number went in as the tracking number for vendor B's order, and **the customer could no longer track their shipment.**

**First cause — a single matching key**
Matching was done **on vendor name alone.** With more than one open item for that vendor, it attaches to an arbitrary one.

**Second cause — this is the real one**
The regex written to *detect* bad values had **`^\d{10,14}$` registered as a "valid format".**
**That is exactly the shape of this incident** — a 10-digit order number sitting in the tracking field.

★★ **The signature of the defect was on the validator's allow-list.**
A rule added because "that's a normal format" let precisely that accident through.

**★★ It could not be undone**
At the time this was judged to mean **"there is no correction API"** — every guessed path (`/invoices/correction`, `/invoices/update`) returned 404.

**That judgement was wrong.** A correction path existed under a different name: the write is `.../invoices`, the correction is `.../updateInvoices`. The assumption was that **a verb would hang off the same noun**; it was **a separate verb path**. One search found it, and every affected record was fixed.

★★ **A 404 on a URL you guessed means "I don't know the path", not "the capability doesn't exist".** → see the dedicated entry below

⚠️ **Being recoverable does not make the incident lighter.** The wrong value was genuinely shown to the customer; the fix did not undo that, it **covered it.**

★ **For irreversible writes there is no defence but validation beforehand.** Do not design as though a corrective path will exist.

**Rules**

1. **When you write a validator, check whether the defect it exists to catch is on its allow-list**
2. ★ **Regression-test detection rules against real past incidents.** Feed in an error that actually happened and confirm it fires. If it doesn't, the rule may as well not exist
3. Values written outbound need **format validation *and* target matching.** Either alone is insufficient

**Aside — a defect that was harmless because it never landed**
This defect had **already been documented weeks earlier.** At the time the write never actually reached the downstream system, so there was no damage, and it was filed as "observed".
★★ **A defect that was harmless because it never landed has not been fixed.** It fires unchanged on the day the path opens.

**The original incident's four causes — every one was a plausible-looking value passing**

| Cause | Fix |
|---|---|
| Tracking regex `(\d{10,14})` **mistook an order number for a tracking number** | Drop the pure-digit pattern; accept **carrier-prefixed patterns only** |
| Substring `shipped` in `"getting your order ready to be shipped"` **judged as dispatched** | A separate "not yet" pattern; split order-received from shipped |
| An empty keyword **passed every filter** and wrote into the first order | No keyword → abort |
| Two or more orders from one vendor → **wrote into the first one** | Return AMBIG, stop auto-entry |

★ **A fix written in the notes and a fix applied at every call site are different facts.** When it recurred, ① and ④ turned out to be missing from that path. Count **every place that uses the value**, not the function you fixed.

**The mirror image — a correct property used as a violation metric is a false-positive generator**
Above, the defect was on the allow-list. This is the opposite. A checker for three tables used "scatter of text start-x" as its violation metric and reported all three as "alignment broken". In the right-aligned amount column the right edge was identical on every row; the scattered start was **nothing but differing digit counts.** In a centered column, badges of different widths scatter at both ends — **that is the definition of centered.** The disproof: after the "fix", not one measured value changed. The real culprit was a different column.

| Alignment | Must match | May scatter |
|---|---|---|
| Left | start (left) | end |
| Right | **end (right)** | **start** |
| Center | center | both ends |

★ **Before choosing a metric, answer "if this number is large, what is wrong?"** Without an answer, the number manufactures a misreading that looks like evidence — worse than a bare guess, because it has a figure attached.

---

## Derive the failure list from absence, not from failure records

**Situation**
A bulk registration batch hit a daily quota and **333 of 1,155 items were rejected.** A list of what failed is needed.

**The wrong way — parsing `FAIL` out of the result CSV**
★ **CSV column layouts differ between scripts.** Once several batches exist, column order, header names and delimiters drift apart, and **parsing breaks silently.** The failure list then comes back empty or wrong.

**The right way — subtract from the target system**
Take the full list you intended to send and subtract **what is now present in the target's completed list.**

★★ **A failure record depends on the format of whatever wrote it; absence is a fact about the target system.**

**Why this generalises**
- A failure record **only exists if that write succeeded.** If the process died mid-run, that span has no failure record at all
- Absence holds **regardless of what happened in between**
- ★ For the same reason, **"what is still missing" is a safer retry set than "how many succeeded"**

**Aside about the quota itself**
The quota counted **variants, not products.** Items with many options **burn through it far faster** — the same number of records drains it at a different rate. ★ **Check whether the limit's unit is the same unit you are counting in.**

---

## A 404 on a URL you guessed is not "the capability doesn't exist"

**The incident**
Looking for the path to correct a record, **two names were guessed** and tried.

```
POST .../invoices/correction   -> 404
POST .../invoices/update       -> 404
```

From that, the conclusion was **"this platform has no correction API; it is irreversible."** That conclusion drove **a plan for manual recovery**, went **into the documentation as "irreversible"**, and was reported to someone else as fact.

**It was wrong.** One search produced the real path.

```
POST .../orders/updateInvoices
```

★ The write is `.../invoices`; the correction is `.../updateInvoices`.
The assumption was that **a verb would hang off the same noun.** In reality it was **a separate verb path.** The whole judgement rested on believing the other side follows resource-tree REST conventions.

**★★ Rules**

1. **If you guessed the path, a 404 is not evidence.** Before concluding, ask **"did I invent this URL?"**
2. **"The capability doesn't exist" may be said only after docs, search and asking**
3. ★ **"Irreversible" is an unusually expensive verdict.** That one word produces **manual work, design changes, and apologies.** Search once more before saying it

**★★★ Aside — this rule was already written down**

Two days earlier, after a 404 on a different endpoint, this had been recorded:

> **Do not read a 404 as "no such capability". You have not found the path yet.**

**Two days later it was broken.** Three similar things happened that same week — a validator passed the defect it existed to catch, a format rule was agreed and then violated by hand, and here **a judgement rule was written down and not retrieved at the moment of judging.**

★★ **Writing a rule down and retrieving it at the moment of judgement are two different capabilities.**
Recording it is not enough; it has to sit **somewhere that fires automatically just before the judgement** — a checklist, a lint, a review question — to actually work.

---

## In a list of patterns, the order is the priority

**Symptom**
Several rules classify a string by shape. **The specific cases got swallowed by the general one.**

```
matches 2-9-2 shape  -> A     <- general pattern first
starts with 1Z       -> B
starts with LS       -> C
```

Both `1Z...` and `LS...US` match the general pattern first, so **everything classifies as A.** Rules B and C are **never reached.**

**Fix**

```
1Z, LS, 4PX  (specific prefixes)  <- first
2-9-2, N digits (general shapes)  <- after
```

★ **In a pattern list, the written order is not documentation order — it is execution priority. Treat ordering as design.**

**Second time**

The same shape had been hit before, in product classification: `mount` inside `Rail-mounted` matched "mount bracket", and `pen` inside `Tactical Pen` matched "fountain pen". A short general token placed first means **the longer specific token is unreachable.**

★ **The mistake repeated in a different domain after being learned once.** Every time you write a new rule list, check **"is the specific one above?"**

---

## "It was accepted" is not "it was correct" — fallback values that disable features

**Situation**
When you must send a value that isn't in the accepted list, a catch-all value that "takes anything" is tempting.

**The trap**
That catch-all may be **a value that turns a feature off.** Here it meant **"no tracking information"** — the request passes, but **the end user loses tracking entirely.** In that state the record also **cannot be corrected from the admin UI.**

★ **An API accepting a value does not mean the value is semantically right.**
★ **When choosing a fallback, look at what that value turns *off*, not what it turns on.**

**What was done instead**
Carriers missing from the list were **identified by tracking-number format and mapped to the closest real code.** The option that kept tracking alive was chosen.

---

## Keep derived estimates and source records in separate fields

**Symptom**
Cost was computed as `foreign price x rate x coefficient`. Compared against the actual payment record, it was off by **16%** (estimate 115,470 vs actual 99,000).

**Cause**
The coefficient is an average and the rate is from a different moment. **The estimate isn't wrong in itself — but a source record existed and was going unused.** The payment confirmation email had the real figure.

**Fix**
- **Create a dedicated field for measured values.** When present, it always wins
- ★ **An estimate is a stand-in for a missing source, not an equal.** Mixed into one field, you can no longer tell which you have
- Flag records judged from estimates alone. 16% is **enough to flip profit into loss**

★★ **The longer the estimation pipeline, the more quietly a single bad input skews it.** This one had three inputs (price, rate, coefficient) — and **the currency itself had been wrong** at one point.
## Shipping address parse comes back with the billing address inside it

**Symptom**
Shipping addresses are extracted from order emails, and a rule excludes "ships to our own address = self-purchase". The real shipping address is in another city, but **our own postcode is detected inside the shipping address** and the match is rejected.

**Cause**
The parser took **a fixed 300 characters** after the `Shipping address` header. In that mail format the `Billing address` block follows immediately. When the shipping address is short, 300 characters **swallow the whole billing block.** The billing address was our own, so the rule fired correctly on the wrong span. No error.

**Fix**
Cut the span at the **next header**, not at a length: from the start marker to the next marker (`Billing address`; failing that, the next blank line or section header). No fixed-length slicing.

```python
start = body.index("Shipping address")
end = body.find("Billing address", start)
ship = body[start:end if end != -1 else start + LIMIT]
```

**Verification**
If the extracted span **contains the next block's header string, the extraction failed.** `Billing` inside a shipping address means the cut is wrong.

★ **Extract a span by its end marker, not only its start.** A fixed length is an unfounded claim that the next block won't fit inside it.

---

## `can't adapt type 'UUID'` when passing a uuid parameter through psycopg2

**Symptom**

```
psycopg2.ProgrammingError: can't adapt type 'UUID'
```

An INSERT or SELECT that takes a `uuid.UUID` value, or a `uuid[]` list, dies, and the endpoint above it returns 500. The same query runs fine in a SQL client.

**Cause**
psycopg2 does **not adapt `uuid.UUID` out of the box.** Pass a string and it works; pass a UUID object and it fails. Arrays fail per element.

**Fix**
Register the adapter **once**, right after import.

```python
import psycopg2.extras
psycopg2.extras.register_uuid()
```

Once per process is enough. Calling it per connection is harmless but pointless.

**Verification**
Print the bound query with `mogrify` before sending it.

```python
cur.mogrify("SELECT %s, %s", (uuid.uuid4(), [uuid.uuid4()]))
# b"SELECT '...'::uuid, ARRAY['...'::uuid]"   <- registered
```

★ **Register adapters once, in one place, at import time.** A 500 that happens from some modules and not others means the registration is scattered.

---

## Every product from one store shows a loss: the price field was not in USD

**Symptom**
The `price` from a source catalog API was written straight in as cost. Every product from certain stores came out **at a loss**, and the margin check, repricing, and sourcing verdicts were all invalid at once.

**Cause**
The catalog's `price` is in **the store's display currency.** Not USD. A Swedish brand was in SEK (×133 won), a Taiwanese brand in TWD (×44.5), a Japanese brand in JPY (×9.3). Nothing in the response says which — `1400.00` could be 1,400 USD or 1,400 SEK, and the number alone can't tell you.

**The misdiagnosis**
The numbers were large, so the diagnosis was **"it's in cents"** — and 65 records from one store were divided by 100, then restored. That store was plain USD. **A healthy store got broken.**
**Two hypotheses — "cents" and "different currency" — produce the same number.** Looking at the number cannot distinguish them.

**Fix — how to tell**
1. **Compare the live product page's displayed price against the API `price`.** That is the deciding evidence.
2. Guess the currency from the brand's home country first — Swedish, suspect SEK.
3. The domain TLD is a clue but **not enough on its own** (plenty of European brands sit on `.com`).

The correction covered 939 records in two currencies plus 14 in JPY.

**Verification**
After conversion, check that the cost/price ratio falls in a sane range **per store.** A store that is entirely at a loss, or entirely at 90% margin, has the wrong currency.

★ **Before any irreversible bulk conversion, decide which hypothesis is true.** A value being present does not mean its unit is right.

**★★★ The same assumption has to be broken separately at every endpoint**
Six days later we **hit the identical trap on the cart-quote endpoint.** The catalog `price` had been fixed, but **the shipping-quote response was also in the store's display currency.** A Taiwanese store returned `378`; read as-is that is `$378`, and the real figure was **$11.72**.

★★★ **A fix in one place does not carry to the others.** "The store is in USD" has to be **un-assumed at every point that reads an amount.** → **`grep` every call site that receives a monetary value and add the currency check to each.** "The fix is decided" and "the fix is in every call site" are different facts.

★★ **And unit errors are caught by magnitude, not meaning.** Which currency `378` is cannot be told from the value — but **"$378 international shipping" is impossible** and you do know that. **Put a sanity ceiling on every path where a conversion happens, and treat anything above it as a misread unit.**

---

## A bad bulk conversion cannot be undone by inverting it — re-fetch from the source of truth

**Symptom**
Records wrongly divided by 100 were logged as "restored." Six days later, **103 records from a different store were still holding the wrong values.**

**Cause**
The restore covered **the store where the problem was first spotted**, not **the full range the bad conversion had touched.** ★★★ **If you don't know the scope a bulk conversion was applied to, you don't know the scope of the repair either.**

**★★★ And multiplying by 100 does not undo it**
It looks reversible. It isn't.

1. ★ **There is no record of which rows were converted** — you cannot target an inverse you cannot scope
2. ★ **Partial application** — only some rows were converted. Multiplying all of them **breaks the healthy ones** (the same mistake, again)
3. ★ **Other updates landed in between** — re-fetches and recalculations mean today's value is not the post-conversion value
4. ★ **Rounding loss** — divide then multiply and you do not get the original back

**Fix**
**Re-fetch everything from the source of truth, not from a backup.**

```python
row["twd"] = live[handle]      # rewrite, don't invert
```

★★ **When the source of truth lives in an external system, that is your best backup.** Your own backups mix timestamps; **the upstream API is the correct answer as of right now.** Don't repair the local copy — **discard it and re-pull.**

**★ Rules for bulk conversion**
1. **Write the target list to a file first.** It is your only means of repair
2. **Keep the pre-conversion value in a sibling field** (`twd_raw`) — more reliable than an inverse
3. ★★ **Verify "restored" by re-reading every record.** Count whether **the same mistake reached other targets** too

★★★ **A write we believed was reversible turned out not to be.** The judgment "this is recoverable" rested on **assuming we knew the blast radius** — and that assumption was wrong.

---

## `text-align: right` shows in getComputedStyle but the buttons don't move

**Symptom**
The button cluster in a table's action cell was off by 82px per row. `text-align: right` was set on the cell; `getComputedStyle` confirmed `right`. The button coordinates **did not change at all.**

```
cell computed:  text-align: right                                  <- looks applied
button x:       row0 [1475, 1558, 1674] · row1 [1393, 1518, 1634]  <- unchanged
```

**Cause**
The cell's children were `<div class="d-flex ...">`. `text-align` is a layout rule for **inline content**; inside a flex container, placement is decided by `justify-content`. `text-align` is **inherited but never applied.** `getComputedStyle` reports the inherited value honestly — it's just not the layout algorithm that consumes it. The check looked at **the wrong layer.**

**Fix**
`justify-content: flex-end` on the flex child. The buttons' right edge converged on a single value (`1892`).
If you don't know the structure, **set both** — `justify-content` / `align-items` for flex and grid, `text-align` for inline flow. They don't override each other.

**Verification**
Verify alignment fixes **by coordinates.** Measure button x, right edge, and column boundary with `getBoundingClientRect` and confirm they converge on the same value per row. A computed-value check answers "did the declaration arrive?"; only coordinates answer "did it do anything?"

★ **A computed value is a necessary condition, not a sufficient one.** When the place you check is not the place that does the work, computed values and green checks both lie.

---

## A value being present does not make it that field's value

**Symptom**
Structured metadata (json-ld) `description` was scraped as the product description. The location matches the schema and the type is a string, so **no validation catches it.** The actual content:

```
"Used to get facts about the stores policies..."
```

It was **chatbot guidance text.**

**★★ How to tell — put two records side by side**
★ **If two records carry the same string, it is not a per-record value; it is site-wide boilerplate.**
**One record on its own looks plausible.** The nature only shows up in comparison.

The same shape appeared elsewhere — generated bodies came out at **exactly the same length across many records**, which was the signal that the generator was re-reading its own output.

★ **Identical output across many records is itself a signal.** Schema validation will never catch this.

**Aside — instead of unblocking, remove the need**
Body text was blocked for a different reason per domain (JS rendering / no such route / boilerplate). Rather than unblocking each one, the path taken was **a layout that doesn't need body text** — on that channel, enough images carries a listing with short text.
★ **Unblocking something and making it unnecessary are different moves.** The second is often cheaper.

---

## One data shape carrying two meanings will be misread

**Situation**
A record's `sources` array had multiple entries — 1,107 records did.

While designing a new feature (bundled products), it was nearly read as **"multiple entries, so this must be a bundle."** It was in fact a list of **alternative suppliers.**

★★ **Reading it that way would have sent wrong purchase orders for 1,107 items.**

**Fix — split fields by meaning, not by shape**

```json
{"is_set": true,
 "set_items": [...],   // bundle components
 "sources":   [...]}   // alternative suppliers
```

Both are arrays, but **the names differ and different code consumes them.** Bundle handling only triggers when the flag is set *and* the dedicated field exists.

★ **Sharing the shape "many" does not make the meaning the same.**
★★ **Why add structure for a feature you aren't shipping** — adding it later means **reinterpreting 1,107 existing records, and that is exactly when the confusion happens.** Draw the distinction while the count is small.

---

## If the baseline for your subtraction is stale, the subtraction is wrong too

Earlier: **"derive the failure list from absence, not from failure records."** That holds. **But there is one more step in the order.**

**Symptom**
Deriving by absence produced **1,371 unprocessed items.** The real number was **170.**

**Cause**
The "completed" list used as the baseline was **a pre-refresh snapshot.** Everything just processed **counted as unprocessed.**

★★ **Deriving by absence assumes the baseline reflects the current state.**
Without refreshing it first, **the work you just did becomes work you never did.**

**Order**
```
1. Refresh the baseline list   <- the step that gets skipped
2. Diff against everything you intended to send
3. What is missing is unprocessed
```

★ Run a batch with the retry set inflated 8x and you **redo finished work while eating into a quota.**

---

## The reason for a `400` is on the exception object

**Symptom**
A message-sending API returned `400 Bad Request`. Suspecting the payload, escaping, length and special characters were all adjusted in turn. None of it mattered.

**Cause**
The reason was in the response body.

```
{"description": "Bad Request: PEER_FLOOD"}
```

It was a **per-sender rate limit for too many messages in a short window** — nothing to do with content. The code caught `HTTPError`, **took the status code, and discarded the body.**

★★ **The exception object carries the response.** One `e.read()` reveals it. Take only the status code and **the reason disappears entirely.**

**Diagnosis — same input, different sender**
The identical body **succeeded from a different sender.** That is the evidence for "not a content problem."
★ **Re-running with exactly one variable changed separates a content problem from a state problem.**

**Response — three stages**
1. A **fixed delay after each successful send**
2. On detecting the limit, **a longer wait and retry**
3. Still failing? **Send from a different sender**

★ Channels that had been **split by purpose became availability redundancy here.** Splitting creates alternate paths as a side effect — with one sender there is no stage 3.

**★★ Aside — the test consumed the production quota**
The limit was hit **by testing.** Repeatedly clearing the idempotency file (the "already handled" list) and re-running meant **sending the same notifications over and over.**

★★ **When testing something that consumes an external quota, "clear the processed list and run it again" multiplies your outbound volume.** That is a path where testing breaks production. Keep a separate dummy recipient that costs no quota.

---

## Raising one ceiling does nothing if another one is lower

**Situation**
A sellable-quantity field was hardcoded to **3** with no rationale behind it. Three sales meant out-of-stock, and out-of-stock kills visibility. **The system was suppressing itself.**

★ **A "3 for now" value became the ceiling while nobody looked at it again.** A placeholder with no rationale has no review trigger either.

**Why raising it changed nothing**
The same resource had a **separate per-order quantity cap**, also set to 3.

★★ **Where two ceilings apply, throughput is set by the lower one.** Raising one alone changes nothing.

**Habits**
- When raising a limit, **enumerate every other limit on the same flow**
- ★ Multiple limits often **count in different units** — one may be a total, another per-request
- When you write a placeholder, **write the review condition next to it.** Without one it becomes permanent

---

## Filter pass rates multiply — a near-zero result is not proof the data is thin

**Symptom**
An 8,000-item catalog went through the pipeline and **27 items** came out the far end. The obvious read was that the source was poor.

**Cause**
Several filters were ANDed together. **Pass rates do not add, they multiply.** Five conditions that each let 70% through leave you **0.7⁵ = 17%**. No single condition looks unreasonable; stacked, almost nothing survives.

**Fix**
Relaxing three conditions against measured evidence took it from **27 to 547 (20×)**. The source had been sufficient all along.

★★ **Do not read "too few results" as insufficient supply.** The supply may be fine and the sieve too fine. **A number near zero does not, by itself, tell you why.**

**★★ Without per-reason rejection counts, relaxing filters is guesswork**
A pipeline that only counts what passed cannot be diagnosed. **Record a reason on every rejection and aggregate by reason.** Measured per source, the top reason differed completely from one source to the next — price here, stock there, attachment count somewhere else.

★ **Tuning a global filter from intuition built on one source loosens the wrong condition.**

**★ Relax one condition at a time**
Because the rates multiply, **turning off a single condition moves the result by a multiple, not an increment.** Release several at once and you cannot tell which one did the work — and you open the gate wider than intended.

**How to verify**
Attach a `{reason: count}` aggregate at the end of the pipeline, then toggle conditions **one at a time** and record the pass count. If the model is right, each condition you disable multiplies the output rather than adding to it.

★ One side benefit: the moment the reason breakdown existed, it exposed **"already processed" sitting inside the rejection reasons.** A normal state mixed into a failure distribution **blurs the real bottleneck ratios.**

**★★ For the same reason, a metric with a prerequisite misleads you when read on its own**
One stage showed `0.1%` complete. It read as "nobody is doing that work" — but that stage only applies to items that cleared **the previous stage, which stood at 44%.** The `0.1%` has a denominator of 44%, and **no amount of work on that stage can exceed 44%.**

★★★ **Where a prerequisite exists, the earlier stage's rate is the later stage's ceiling.** Seeing a low number, suspect **"there is nothing eligible to work on"** before **"the work isn't happening."**

★ **And hanging a target on such a metric quietly changes what the target means** — a gate like `start advertising at 80% images` is, while the ceiling sits at 44%, **effectively a gate on the earlier stage.** **Whenever you gate on a metric, write down its ceiling next to it.**

---

## In a heuristic scorer, a failed fetch scores lowest — the failure is punished twice

**Symptom**
A scorer read pages and rated trustworthiness. Positive signals `+1`, risk signals `-2`. On a run, **three long-standing, entirely legitimate counterparties came back at `-4` — the highest risk band.**

**Cause**
Rate limiting meant **the pages were never read at all.** Yet the score landed at the negative floor rather than at zero. The asymmetry in the rules is why.

| | On a failed fetch |
|---|---|
| Positive rule (`has an email address`, `+1`) | unconfirmed → **0, neutral** |
| Risk rule (`has no email address`, `-2`) | **"absent" holds, so it fires** → **penalty** |

★★★ **Positive rules key off presence; risk rules key off absence.** So **one failed fetch forfeits the credit and triggers the penalty at the same time.** The single fact "we could not check the email" **loses +1 and takes -2 — a three-point swing.** With several signals it compounds.

★★★ **An event that should be neutral acts as a conviction.** And it fails in the most plausible-looking direction — a top-risk verdict looks like the scorer **did its job**, not like it **never read anything**.

**Fix**
**Carry a `fetched` flag and separate "could not check" from "not present."**

★ **When `fetched` is false, do not evaluate the penalty rules at all.** Not a zeroed score, not a neutral value — **withhold the verdict** and give it a **fourth outcome**: `UNKNOWN`. With only safe/caution/risk available, failure must leak into one of the three.

```python
if not fetched:
    return Verdict.UNKNOWN      # not a zero score. not a grade.
```

★ And **remove the cause too** — here, spacing the requests. Fixing the scorer and fixing the collector are separate jobs, and **you need both.**

**★★★ This was the third repeat**
Two others are already in this collection — **a failed fetch read as "out of stock"**, and **a blocked search read as "zero results."** Here a block was read as **"dangerous."**

★★★ **That is not coincidence. Scorers are usually built to look for evidence of normality — so failing to obtain evidence produces a negative verdict automatically.** Every time you write a new classifier, ask one question: **"what does this return when the input could not be read?"** Most classifiers never define that path, and an undefined path **falls to the worst grade.**

**How to verify**
★★ **Run the scorer with the network cut.** Every item should come back `UNKNOWN`. If even one comes back graded, that rule is penalizing absence. A single assertion catches it.

```python
assert all(v is Verdict.UNKNOWN for v in run_all(offline=True))
```

★ Also **check which way the false positives point.** A rule that treats size as a risk signal (`too many distinct suppliers`) will flag **every legitimately large** counterparty. Look at how both tails of the normal distribution land on your rules.

**★★★ And the signal itself may not be a signal — format validation is not attribution**

`+1 if an email address is present`, implemented as a regex, was awarding points to these:

| Address found | What it actually was |
|---|---|
| `back-in-stock@notifyboost.net` | injected by a **third-party app** |
| `support@storefront.com` | a **platform template default** |
| `example@mail.com` | a **placeholder** |

★★★ **"there is an email on the page" and "this business has an email" are different propositions.** A regex only checks shape. **Whether the value you found actually belongs to the subject is a separate check** — here: the domain must match, or the address must contain the brand name.

★★★ **Worse is the direction of the error.** All three appear **more often on the suspicious subjects.** The more a site was left as a stock template, the more likely the platform defaults and placeholders survive untouched. **So this rule hands bonus points to the least trustworthy subjects.** The false positives are not random — they point **backwards**.

★★ **When you design a signal, also ask "how easy is this to fake?"** Anything easy to forge or accidentally inherit **must not be a positive signal.** Use it only as a penalty, or attach an attribution check before it earns credit.

**★★ Set thresholds from normal samples**
The safe line was set at `3` to fit one malicious sample scoring `-7`. A long-standing legitimate counterparty then fetched successfully and still scored `0` — "caution." Not a fetch problem; **the threshold itself was wrong.**

★ **Look at the score distribution of your normal population before drawing the line.** A threshold fitted to a single bad case cuts the good ones. And you usually have exactly one failure case but **as many normal cases as you like** — calibrate from the side with enough material to see a distribution.

Measuring 10 legitimate subjects gave `1–7` (median 5); the one malicious sample scored `-6`. **A gap of 7.** Yet the threshold sat at `3` — **not the middle of the gap (-2.5) but well inside the normal distribution.** One legitimate subject fell below the line and another landed exactly on it.

**★★★ Even so, "the gap is 7, so it's stable" is not a claim you can make — there is one malicious sample**
Ten normal, one malicious. ★★★ **One point tells you nothing about a distribution.** The second bad actor could score `-1`. **"Calibrate from the normal side" being right does not mean you know the malicious side.**

★★ **So don't force a verdict on the region you have no data for — add a band.** Put a **`borderline — human check before proceeding`** band in the empty zone between the two distributions, and the classifier commits only where it has evidence and hands off where it doesn't. Same reasoning as `UNKNOWN` above: **don't attach a grade where you have no confidence.** Recalibrate once a few malicious samples have accumulated.

**★★★ The `fetched` flag belongs on the signal, not on the subject**
Once you drop the bonus and keep only **a weak penalty for absence**, that penalty becomes **entirely dependent on `fetched` being accurate.** And real collection is not all-or-nothing — **the main page loads but the contact page fails**, so `fetched=True` while that particular signal's evidence was never seen. → **penalty.** The bug you fixed comes back in partial-failure form.

★★ **Each signal must carry its own "did I actually read my evidence?"** — `fetched_email`, `fetched_address`. A single subject-level flag **rounds partial failure up to full success.**

**★★★ Removing a bias means re-deriving the thresholds — the correction shifts the scale, not the separation**
Re-measured after splitting the flag per signal:

| | Lowest normal | Malicious | Gap |
|---|---|---|---|
| Before | 1 | -6 | **7** |
| After | 2 | -5 | **7** |

★★★ **The gap is unchanged; both sides moved up together.** The unfair penalty applied **equally to legitimate and malicious subjects** — a failed fetch does not discriminate.

★★ **So removing the false positive did not improve discrimination.** What improved is **what the score means**: it now reflects only evidence actually read. ★★★ **But the threshold was fitted to the old scale — change the scoring and leave the threshold, and the threshold quietly comes to mean something else.** Touch the score computation, **always re-derive the threshold.**

**★★★ Never pin a threshold to the minimum**
After recalibration the safe line was set at `2` — and the lowest legitimate sample was **exactly 2.** The same shape as the previous round, where the minimum landed right on the line.

★★★ **The minimum is a statistic that keeps falling as the sample grows.** Ten legitimate samples bottoming out at 2 means **the eleventh could be 1**, not that **2 is the floor of normal.** Pin the line to the minimum and **it slides down every time you add data — that is an observation, not a threshold.**

★ **Use a quantile instead.** Find the 10th–20th percentile of the normal population and leave headroom below it.

★ And **bound the cost of being wrong with bands.** If falling below the line moves a subject one band down (a light extra check) rather than straight to a block, a slightly wrong threshold costs little. **The finer the bands, the less sensitive you are to threshold error.**

**★★★ Confirmed — growing the sample from 10 to 40 pushed the minimum back down**
The normal-population distribution, re-measured at 40 samples:

```
{1:1, 2:4, 3:5, 4:7, 5:10, 6:10, 7:3}   n=40
min 1 · p10 2 · p20 3 · median 5 · max 7
```

In the previous round, fixing the bias raised the minimum from `1` to `2`, and the safe line was pinned there. **Grow the sample and something else takes the 1 slot.** The predicted "the eleventh could be 1" **happened exactly as stated.**

★★★ **The minimum is an observation that keeps falling as the sample grows, not the floor of the distribution.** And at 40 samples that 1 is still **a single item** — so **you still cannot claim to know the floor.** The minimum is a statistic that never stabilizes, no matter how much data you add.

★ **A quantile removes the wobble.** Set the line at something like `p10 − 1` — **one step below a quantile** — and it barely moves as the sample grows.

**★★★ And rather than trying to get the threshold right, make being wrong cheap**
In that distribution the recommended line is `p10 − 1 = 1`, but the line actually in use is **one step stricter, `2`.** As a result **2.5% of the normal population (one item) falls below it.**

★★ That is acceptable because falling below means **a "light extra check" band, not a block.** The cost of a false positive is **bounded.** ★★★ **A bounded cost is more robust than an exact threshold** — design standing in for precision.

★ **Decide which way you want to be wrong before drawing the line.** Here, **the cost of double-checking a legitimate subject < the cost of letting a malicious one through**, so the line errs strict. Without that decision, a threshold is just a number.

**★★ Five checks before adding a signal**
1. **Forgeability** — can the subject simply create it at will?
2. **Accidental presence** — does it appear on its own via templates, third parties, placeholders?
3. **Attribution** — is there evidence the value **belongs to the subject**?
4. **Error direction** — when it's wrong, which way is it wrong?
5. **Meaning of absence** — does it distinguish not-seen from not-there?

★ **If 1 or 2 holds, never use it as a positive.** Without 3, use it only as a penalty. ★★ **If 4 points backwards the signal is worse than nothing** — **random false positives dilute as the sample grows; backwards ones get worse.** They barely move aggregate accuracy metrics and **fail exactly where failing matters most.**
