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

**Fourth confirmed case: the mock checks a path production never takes**
An external API error was fixed and reported as "reproduced, then passing" with a mock. But the mock was patched onto the **direct-call leg**, and production sends the same call through a **relay**. The branch is chosen by a single env var, and **the sandbox default is the quiet side (direct)**, so it went green. With the relay switched on and the same code run again: direct leg called 0 times, relay called once. **Production never once walks the path the test checked.** The call site is a single gateway, so reading the code does not tell you which leg runs.
1. **The test sets the branch env itself.** Rely on the default and you only ever test the quiet side
2. **Assert zero calls on the other leg**, making "the patch point is the production path" a contract
3. A path that forks on environment gets a contract **on both legs.** Cover one and the other is a blind spot

"I reproduced it" only holds once you say which code you reproduced. **Green on the wrong path is worse than no green**: it makes you believe it is fixed.

**The mirror of the green trap: the exoneration trap**
An icon looked broken in a captured screenshot. The agent ruled: "capture artifact. A file-based render just can't fetch the static-asset path; it's fine in the app." The mechanism was plausible and the conclusion was wrong: the same breakage turned up in a screenshot taken live.

An artifact verdict is a verdict that **ends the investigation.** Once a spot is filed under "not our problem," nobody looks at it again, so when the verdict is wrong the defect stays live. What went unseen gets seen eventually; **what got exonerated never gets searched for.** And a correct mechanism is **not evidence that it caused this breakage.** The burden sits on the expensive side, and a live check was replaced with an explanation.
- Before calling it an artifact, **show it renders correctly live.** If you can't, say only "may be a capture-environment difference; needs live confirmation." That is not an exoneration
- Ask **where a screenshot came from** first. If it is live, the artifact hypothesis is out before it starts
- Even without a repro, **a repair that removes the dependency is possible.** Inlining the external file reference rules out 404, CSP, and deploy omissions in one move. You can remove the risk without knowing the cause

★ **"Not our problem" is the most expensive conclusion, so it demands the most expensive evidence.** The green trap makes you skip verification; the exoneration trap makes you stop investigating. The more a verdict halts investigation, the heavier its evidence has to be. Even without a repro, the dependency-removing repair (inlining) is still available.

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

One code **accepted it without any format validation.** The order transitioned to *shipped* and a **fake tracking number appeared on the customer's screen.**

(It was judged at the time to be **irreversible for lack of a correction API** — that judgement was **wrong**; the guessed paths 404'd but a correction path existed under another name. See the dedicated entry below. ★ The point stands: **that was not known at the moment of writing.** "It turned out to be reversible" is an after-the-fact discovery, not a basis for acting.)

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

---

## Setting vanished on every device after a "local cleanup" git rm

**Symptom**
An agent ran `git rm` on an editor's settings directory, "cleaning up local settings." From the next pull, **the setting (a graph-view colour palette, say) was gone on every device.**

**Cause**
The file was a **deliberately tracked shared setting**, whitelisted through a `!` exception in `.gitignore`. The rest of the directory was untracked, so the one whitelisted file went unnoticed, and the folk rule "editor settings are local" justified the `git rm`. Deleting a tracked file travels with the commit. It is not a local cleanup, it is **a delete on every machine.**

**Fix**
Check tracking intent before deleting.
- `git ls-files <path>`: any output means it is tracked
- `git check-ignore -v <path>`: a matching `!` rule means someone explicitly decided to track it

A whitelisted file does not get deleted. To change the value, edit the file and commit. The rest of the directory's untracked files stay untracked, which is correct.

**Verify**
Before committing a deletion, list it with `git diff --cached --diff-filter=D --name-only` and run `git check-ignore -v` on each path. No `!` match may appear.

★ **A tracked file is one somebody decided to track.** A whitelist entry is a decision, not an accident.

---

## Comment says "measured: N rows" but no code ever computes N

**Symptom**
A code comment read "measured on <date>: N rows." From that one line grew a load claim ("we re-query N rows every cycle"), and a whole work track was planned on top of it, dry-run counting procedure included.

Measured for real: **that re-query never existed.** Zero queries anywhere in the codebase aggregate that number. The system looks at a different population, and the actual scan count that day was 0. The track was closed for having no target.

**Cause**
- **A comment is a snapshot, not a value.** "Measured on <date>: N" means *a screen showed N that day*, not *this code handles N*. Those are entirely different claims
- A comment sits next to the code, so **it reads like a property of the code**
- **A number with a source attached is more dangerous.** An unsourced number gets doubted; a number with a date and a source looks like a citation and makes the reader skip verification

**Fix**
- Before planning a track on a number, **find the code that computes that number first.** If you can't, it is not data, it is **an observation log**
- When leaving a measurement in a comment, say **what it is a value of** (eyeballed on an external dashboard is not our own aggregate)
- Pin load and scale claims in a contract. If a query producing that number appears later, the contract breaks and you find out

**Verify**
For every number in the claim, answer "which code path computes this value?" If the answer is "a comment," treat it as unsupported and measure again.

★ **Before building a track on a number, find the code that produces it.**

---

## Two sessions took turns "fixing" the same setting and oscillated it

**Symptom**
A scheduler setting moved **from 120 runs/hour to 88 and back to 120 within a day.** Nobody reverted anything. **Two sessions each reported having "cleaned it up."**

**Cause**
Sessions cannot see each other. Each **read the current state, improved it by its own criterion, and saved.** One was optimizing **throughput**; the other was optimizing **load**.

★★★ **Both were right by their own measure.** Two optimizers with different objectives sharing one variable **do not converge — they oscillate.**

★★★ **And oscillation does not look like a failure.** Every individual value is **exactly what someone intended**, and the logs only ever say "adjusted." **The only way it surfaces is plotting the value over time.**

**★★★ Most shared resources do not detect conflicts**
Work with git long enough and you start expecting that **concurrent edits collide.** That is git being unusual.

| | Concurrent edit |
|---|---|
| A git repo | **rejected, rebase required** |
| Scheduler config, config files, DB rows, an external console | ★ **last-write-wins. Silently overwritten** |

★★ **Where there is no detection, convention is the only defense.**

**Fix**
1. **Read the current value before changing it.** Base the change on **what you just read, not what you remember**
2. Keep a **shared state file** of constraints, canonical values, and hands-off items, and **read it at session start**
3. Maintain a **"do not touch" list** — if an item is on it, leave it alone **regardless of your judgment**

★ **"I set it to 88 last time" is not evidence.** Another session may have run since.

**⚠️ ★★★ That shared state file is not authoritative either**
A snapshot regenerated on a schedule (say, every two hours) is **stale by up to that interval.** Changes inside the window are invisible.

★★★ **Treat the snapshot as the source of truth and you reproduce "I read it, I changed it, and it still oscillated."** → **The shared file tells you what to be careful about; the current value gets read from the live resource immediately before you change it.** Put both jobs in one file and **the stale number takes the canonical slot.**

★ **Stamp the generation time at the top and make readers check the age.** An undated snapshot **always reads as current.**

**⚠️ ★★ And a convention only works if it is followed**
"Read this at session start" is **behavior outside the code.** Skip it and nothing happens.

★★★ **Making it impossible to change without reading is easier than getting people to read.** → Wrap the mutation path in a script that **prints the current value and the snapshot's age first.** Turn the convention into a procedure and you no longer have to verify it was honored.

**⚠️ ★★★ Follow-up — the "do not touch" list was broken the same day**
Point 3 above (keep a hands-off list) was written, and within a day we measured it. **Five of the six protected entries had been changed by another session.**

★★★ **What matters more is that every change went the same direction.** All five had their intervals lengthened (slowed) — because the other session was **cutting toward a numeric "runs per hour" ceiling.**

★★★ **The objective lived in the code as a number; the protection list lived in a document as a sentence. The number wins.** Unless the protection list is **an input to the reduction logic**, the list **might as well not exist.**

**★★★ And cutting by frequency can be inversely correlated with importance**
The two cut hardest were **the notification loop** and **the runaway-prevention guard.** **Both ran frequently because they had a reason to.**

★★★ **Frequency measures cost, not importance — and a reduction pass only looks at cost.** → **Rank cut candidates by `frequency ÷ importance`, not frequency.**

★★★ **Safeguards get cut first, specifically.** A safeguard **looks like cost**, and the incidents it prevented **never happened, so they don't look like benefit.** This is one step beyond this collection's **a safeguard creates the next trap** family — **this time the safeguard switched itself off.**

**★★★ The ladder of defenses — each rung needs less cooperation than the last**

| Rung | Requires | Result |
|---|---|---|
| Write it in a document | the other party **reads it** | ❌ **5 of 6 violated** |
| Enforce via a gateway | the other party **uses the gateway** | bypassable |
| **Auto-restore** | ★ **nothing at all** | reliable |

★★★ **Making it impossible to change without reading beats getting them to read — and restoring it when it changes beats both.**

**⚠️ ★★★ Auto-restore has three traps of its own**
1. ★★★ **Is the restorer in its own protection list?** If not, **changing that one line disables the entire defense.** A self-healing mechanism **must protect itself first**
2. ★★ **The restore interval is the violation exposure window.** Hourly restore means **the notification loop runs at the wrong interval for up to an hour.** Different entries have different urgency, so **intervals should differ too**
3. ★★★ **Restoring doesn't end the oscillation — it just picks a winner.** The other party had a reason for cutting, and **if restore and reduction fight every hour, that is still oscillation** — merely with a one-hour period. **It ends only when the protection list becomes an input to their logic**

★ And **check who receives the restore alert.** If it only reaches a human, **the session that caused it never sees it.** Write it to the shared state file too, so the next session reads it.

**How to verify**
★ **Keep a time series of the values you change.** Oscillation is **invisible in any single reading and obvious in the trend.** A value bouncing between two points is not tuning — **it is two parties fighting.**

★★ **And periodically measure whether the protection list is actually being honored.** Creating a list and having it work are different facts — **we found out only after 5 of 6 had been broken.**

**★★★ Follow-up — that violation was not a discipline problem, it was a symptom of an impossible target**
Feeding the protection list into the reduction logic revealed it immediately. **The protected entries alone already consumed 80% of the ceiling.** Honoring the ceiling *and* the list was **impossible from the start.**

★★★ **The other session did not violate the rule because it failed to read it. Even having read it, hitting the target required violating it.**

★★★ **Give an impossible target and a constraint breaks. And the broken constraint is the visible part; the impossible target is not.** While everyone asked **"why wasn't the rule followed?"**, nobody asked **"was that target even reachable?"**

★★ **Two constraints contradicted each other and had never been checked together.** The ceiling lived in an ops document, the protection list in a config file — **kept apart, the contradiction is invisible. Each was reasonable on its own.** → ★★★ **When you add a constraint, verify it is simultaneously satisfiable with the existing ones.**

★ **Which is why auto-restore alone was not enough.** Restoring **reverts the symptom** and does nothing about an impossible target. **What actually fixed it was re-deriving the ceiling, not the restore mechanism.** → ★★ **When you see oscillation, ask "are both objectives simultaneously achievable?" before "who broke the rule?"**

**★★★ And the metric the ceiling was set on turned out to be a proxy**
Re-dissecting the incident, the cause was not call frequency alone but **frequency × batch size — concurrent execution count.** Low frequency with **a large batch blows up just the same.**

★★★ **Cap a proxy metric and you get both failure modes at once — you miss what you should have stopped, and you stop what you shouldn't have.** Here it **let the large batch through and blocked the protection list.** Same root cause.

★★ **A proxy gets chosen because it is easy to measure, not because it is right.** → **When you gain the means to measure the real thing, move the cap onto it.** We had the guard **log peak concurrency** and **loosened the frequency cap.**

**★★★ Finally — "impossible" turned out to be "we weren't doing it"**
The premise under all of this was **"sessions have no way to share state."** False. **The shared store was already on the server and every session could read it.** What blocked it was not the medium but **the write schedule** — each session committed **once, at the end**, so work in progress was invisible to everyone.

★★★ **Latency in a shared medium is a property of your write policy, not of the medium.** Having the state file **written and pushed periodically** turned "asynchronous, two hours stale" into "near real time."

★★ This collection already contains an entry where **our own default was read as a platform constraint.** **Same shape — what we believed was a constraint was our own habit.** ★ **Before writing down "that's impossible," ask "have we ever actually tried?"**
