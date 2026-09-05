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

**How to tell them apart**
- **Look at the response size.** A 2KB response where 2KB can't be a valid answer is a failure.
- **Loosen the conditions one at a time.** Widen date, count, status, type, and see **whether the 0 survives.**
- **Cross-check via another route.**
- **Count the denominator.** In `0/N`, **if you don't know N you don't know what 0 means.**

**What it cost**
Three days for not making this distinction: four locales misjudged as "out of stock"; 12 emails judged as 0 (three times over); a batch with 0 targets; a "discontinued" verdict where the real story was a different domain.

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

**Rules**
- **Never match on a single field without cross-checking.**
- **Eyeball a sample of every match result.** A plan with dozens of mismatches nearly passed because "the names looked right."
- Before creating a progress file, **check it isn't taken**: `grep -rn "filename" *.py`
- **If one record has two fields pointing at the same target, compare them.** They can disagree with no error.

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

**Unlinked beats mislinked.** Unlinked means "I don't know." Mislinked means **"I believe a wrong thing is known."**

**Why this bites non-ASCII users**
Fuzzy-matching libraries and their default thresholds are tuned on Latin-script data. Korean product names are short, dense, often written without spaces, and the same product appears with mixed Hangul / Latin / digits across sellers. Edit distance behaves differently on syllable blocks than on letters, so a threshold that is "safe" for English is loose for Korean. Calibrate on your own script; don't borrow the number.

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

## A prefix-format value changes which operator is correct

Putting a reason into the value is good — it records *why* something was handled that way.

```
done[x] = "ok:16371818883" / "skip:policy_excluded" / "manual:needs_review" / "fail2"
```

**Then the check must be `startswith`.**

```python
done_ok = str(v).startswith(("ok", "skip", "manual"))
```

★ **`!= "ok"` and `not in ("ok", "skip")` pass for every prefixed value.**
`"ok:16371818883" != "ok"` is **True** → **every completed item gets reprocessed.** No error, normal logs, and **the queue never drains.**

**Safer shape — separate the verdict from the detail**

```python
done[x] = {"state": "ok", "detail": "16371818883"}
```

Pack two things into one value and **every reader has to honour the parsing convention; one place gets it wrong and it leaks.**

**The same operator hazard, other direction**

| Value scheme | Wrong operator | Result |
|---|---|---|
| `"ok:123"` | `!= "ok"` | done read as not-done → **infinite reprocessing** |
| `draft` / `draft_pending` | `== "draft"` | the second one is **silently dropped** |

★ **When values share prefixes, both `==` and `!=` are dangerous.** One drops items, the other passes everything.
★ **Decide the value format and the check code together.** Change the format later and the check flips silently.

---

## Not saving before `continue` throws the decision away

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

The same thing happened with sample size — a defect rate of 36% at n=500 became 48% at n=1,900. **Small samples and front-loaded samples both err optimistic.**

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
B0734ZHGXK -> B0734ZHGXKAB -> ...R / RR / RRR
```

**Fix**
1. **Expand candidates** — original / suffix-stripped / prefix-stripped
2. Cross-check against a **lowercased, punctuation-stripped index**

75% matched after applying this (6,657 of 8,858).

★ **Some never match even with expansion** — they were minted under a different scheme entirely. **If you do not write the counterpart key at minting time, there is no recovering it later.**

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

