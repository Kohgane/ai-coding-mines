# Claude Code · AI Agents

Traps that appear when you delegate work to an agent. Most take the form of **what the agent reported doing differing from what is actually left behind.**

---

## `%USERPROFILE%` in a hook `command` is not expanded

**Symptom**
Registered a hook; at session start there is a quiet startup hook error. The hook never runs.

**Cause**
The hook `command` string doesn't go through shell environment-variable expansion. `%USERPROFILE%\...` is used as a literal path.

**Fix**
Bake in the **actual full path literal** at install time.

For the same reason, use absolute paths rather than env vars when registering scheduled tasks (schtasks). If the path contains non-ASCII characters, solve the encoding problem first.

**Why this bites non-ASCII users**
On Windows the user profile folder is named after the account, and on a Korean-locale machine that is frequently a Korean name. So "just hardcode the absolute path" hands you a path with Hangul in it, and that path now has to survive every boundary from chapter 01 (the hook config file, the shell that runs it, the script it launches). English-named accounts never hit the second problem.

---

## Web-session containers are disposable

**Symptom**
Files and settings created in the home directory of a web session all vanish.

**Cause**
A session opened in the browser is a throwaway cloud container. When the session rotates, it is gone for good.

**Fix**
Do local installs and local configuration **from the PC terminal.** Some UI features (spinners and the like) don't render in web/desktop at all, so verify in the terminal CLI.

---

## The session container rolls the repo back to an old commit

**Symptom**

```
HEAD        : d45e9008 (old commit)
origin/main : 7f08c3ba
48 commits behind
```

**Recurred four times** in a single thread.

**Why it's dangerous**
- Work without noticing and you **layer old code on top of already-merged fixes** (un-fixing them)
- **The whole test count is void.** Green is green for the old code.
- **It's silent.** No error.

**Detection**
- **Human eyes:** *a recently merged file or symbol is missing.* An import that should be there is gone (measured: `import re` vanished), the test count dropped sharply, a function you just wrote isn't there. That is an **immediate `git log --oneline -1`.**
- **Automatic:** a SessionStart hook reports `HEAD == origin/main` as the first line of every session. For environments without hooks, pin it as **step 1 of session start** in the project guidelines too.

**Rules**
- Before any work: `git fetch origin main` → confirm HEAD matches. Mismatch means resync before starting.
- **The hook detects and reports only. No auto-reset.** It would throw away uncommitted work.
- Report full-test results only when run **after resync, with HEAD pinned.**

**Caught in the act**
The hook caught the fourth occurrence. Uncommitted files were evacuated to the scratchpad, the repo resynced, the files restored. **Not adding auto-reset was the right call.**

---

## The container's output directory is not storage

**Symptom**
The session's artifact directory was **completely empty** (zero files). Build artifacts and a copy of the signing key disappeared together.

**Two lessons**
1. **Pull artifacts down locally the moment they are created.** The container is a cache, not storage.
2. ★ **Going from "it's not in the container" to "there's probably no backup either" was a guess, and it was wrong.** The local backup saved it. **Don't conclude beyond what you've measured.**

---

## Chat attachments don't guarantee delivery

**Symptom**
A file the agent sent as a chat attachment **never reached the human.** Twice (an extension zip, a design-mockup HTML).

**Rule (hardened)**
- **Every deliverable = a committed repo path + a PR link.** Chat attachments are auxiliary, not trusted.
- Binaries (zips, images, anything not in the repo) = **Releases** (tags) or artifacts → delivered as a URL
- **Mandatory phrase in the report:** "Where to look: PR#\<n\> · \<repo file path\>". Without it, treat it as undelivered.

---

## The agent token can push branches but tags get 403

**Symptom**
The agent's git proxy token pushes branches fine, but **creating a tag alone returns 403** (curl 22). Tag-triggered workflows (`on: push tags`) can't be fired.

**Fix**
Add **`workflow_dispatch` (with a version input)** to the workflow, and inside it run `gh release create <ver> --target <sha>` to create the tag and release on that commit. The agent only triggers the workflow run; a human presses the same button in the Actions UI.

★ **Any automation that needs a tag push is designed around this workaround from the start.**

---

## Green CI does not guarantee it actually works

**Three confirmed cases**
- CI ran `--collect-only`, so **23 failures were disguised as green** → sealed the execution gate behind an env var
- Suite green, live site crawling. Synchronous processing was hogging worker slots.
- Green, but the screen still showed old verdicts. The UI trusted stale stored values.

**Fix**
Green is a **necessary condition.** Verify live separately on real devices, real browsers, and instrumentation. Recompute verdicts **on read.**

**The reverse trap: a regression contract freezes a bug value**
In a contract test that compares re-runs against a captured baseline, **if the capture happened while the bug was live, the bug gets frozen.** Measured: baseline recorded `images: 1` (a gallery bug) → the fix took it 1 → 11 → the contract went red.

An intended fix has to **update the baseline with the re-extracted value.**
1. Regenerate only the affected fields
2. Demonstrate the remaining contract fields are unchanged
3. Say **"not freezing a bug, applying the corrected value"** in the commit message

**The lazy-import trap**
`try: from PIL import Image / except: return None` is the canonical pattern for collect-only CI safety, but **when the package is missing it silently disables instead of raising.** Any third-party import wrapped in a lazy import gets **a requirements check + an explicit contract.** "The tests pass so it's there" is not evidence: the tests run in the same container.

---

## A hypothesis without a control group was always wrong

**Case A** — after deploy, only the new route 404s. Five hypotheses (keystore, source maps, manifest, infra outage, lost commit) were **all assertions beyond the observed range**, and all wrong. The real cause was one line in the dependency list.

**Case B** — of three deployments, two return 503. Days spent on "the bundles differ." A three-way comparison showed the **three bundles were identical from the deployment's point of view**; the only difference was an unrelated feature. The real cause: **the affected version had never been registered in the console.**

★ **Get the working one in hand first and put it side by side.**
Every hypothesis formed without a working control was wrong. The comparison table only got built after two consecutive misdiagnoses, and the moment it existed the answer fell out.

---

## Agent reporting discipline

Two things kept collapsing.

**1. Completed work goes missing from the report** (3 times)
→ Force the first block of every report to be a **track status table** (hash / in progress / not started). No smearing things into "awaiting collection."

**2. The PR sits in draft awaiting approval and everything deadlocks** (3 times)
→ When the self-gate passes (CI checks + contract tests + capture), merge autonomously and immediately.

**3. No "done" without verification**
When you write "done," **write what verified it.** Unverified is written as "executed," nothing more.

---

## "There is no data" is a claim you have to earn

**What happened**
Looking for a worldwide signal, I **dug three times and concluded it does not exist for free. That was wrong.**

| Axis tried | Why it failed |
|---|---|
| Commercial rating body | 202, bot-blocked |
| Structured wiki properties | 1,222 rows, **Western-skewed** |
| OSM edit history | **polluted by bulk bot edits** |
| Wiki founding-year data | US 1,011 : KR 0 |

**Told to look somewhere else, the fourth attempt broke through.** A travel wiki's curated data hit 4/4 and covered Asia as well.

**Six axes to sweep before giving up**

1. **Official / regulatory** — governments, international bodies, certification authorities
2. **Open data** — OSM, Wikidata, Wikivoyage, Socrata, Geofabrik
3. **Community** — Reddit archives, HN Algolia, forums
4. **Local-language platforms** — ★ **the fact that *I* cannot read it does not mean the data is scattered**
5. **Non-commercial curation** — travel wikis, public broadcaster archives
6. **Inverse proxies** — no direct signal? find **the opposite of the opposite**

**Rules**

- ★ **"There is no data" may only be said after all six axes have been struck**
- When you do stop, **record what you tried and the measured numbers**
- **Blocked access** and **biased data** are different failures with different fixes

★ This is the human-scale version of *"absent" vs "not found"* — the same discipline applies to the **whole search**, not just one query. **"I tried three times" is not evidence of exhaustion.**

---

## Never make exploratory writes against live data

**The incident**
To find out which carrier code was correct, `TESTONLY000000` was written as the tracking number on a **real customer order**, trying **15 codes in sequence**.

One code **accepted it without any format validation.** The order transitioned to *shipped* and a **fake tracking number appeared on the customer's screen.** That platform has **no correction API** — it cannot be undone.

**★★ A test premised on "this will fail" is not a test, it is a write**

It felt like exploration because of the assumption **"it will be rejected anyway."** That assumption became **the basis for action without ever being verified.**

★ **A request sent expecting rejection is still a write when it is accepted.** Writes that feel like reads are the dangerous ones — **you send them without preparing to undo them.**

★★ **Expecting the receiving side to validate input is not a safeguard.** That endpoint didn't check the format. **Do not use someone else's defences as your own.**

**A read habit carried into writes**

"Don't trust the docs, pull the actual values" appears elsewhere in this collection. But that is **read-only advice.** Discovering a value by trying candidates one at a time works for queries and **does not work for writes.** Unknown values come from **documentation, metadata endpoints, or asking.**

**Rules**

1. **No exploratory writes against live data.** No exceptions
2. **Irreversible writes happen only after the value is confirmed**
3. ★ **"It won't work anyway" is not a reason to execute.** If you think it will fail, **don't send it**
4. If a trial is genuinely required, **create a disposable target**

★★ **Irreversible, externally visible, or user-facing** — if any one applies, it is a **no-exploration zone.** This order was all three.

**★★★ Aside — the same day, the same person broke their own rule**

Immediately beforehand, a **tracking-number format rule (carrier prefix, or 12+ digits) had been agreed and written into the code.** Then a value **failing that very rule** was entered by hand on a live order.

That same morning there had been an incident where **a validator had the defect it was meant to catch on its allow-list.**

★ **In both cases the rule was inside the code and the behaviour was outside it.** Putting a rule in the code and **being bound by that rule yourself** are different things.
