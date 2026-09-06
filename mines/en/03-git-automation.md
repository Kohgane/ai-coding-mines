# Git · Automation · Cron

Unattended automation mostly fails **without telling anyone.** That is the theme of this chapter.

---

## An auto-push that swallows failures produces permanent desync

**Symptom**
The daily auto-commit-and-push stops reaching the remote one day. **No log, no alert.** It happened the first day auto-push was turned on.

**Cause**
Another session or another machine pushes one commit to the remote, and from then on every push is a non-fast-forward rejection. A script that swallows failures swallows that too.

**Fix — the order matters**

```
add → commit → pull --rebase origin main → push
```

★ **`pull --rebase` must not come before `commit`.** The file you just wrote leaves the working tree dirty and the rebase refuses with "unstaged changes."

A rebase left halted on a conflict blocks every following run, so add a fallback:

```bash
for st in rebase-merge rebase-apply; do
  [ -d ".git/$st" ] && git rebase --abort && break
done
```

**The fallback's limit, honestly**
Auto-resolving with `-X theirs` silently overwrites what someone hand-fixed on another machine. So giving up on that run is the right answer when there is a conflict. But **this fallback protects the repo, not the work.** The fact that a conflict happened is not recorded anywhere.

**Verification**
On days when several actors touch the same file, `git log --oneline -3` after push to confirm your commit is actually there.

**Suspected duplicate — don't compare drafts**
The draft pasted into chat and what was actually pushed can differ (it gets rewritten to house style right before the push). Comparing drafts against each other yields a false **"another session added more and pushed it."** Judge from the real thing.

```bash
git log --format='%h|%s' origin/main -- '<path>'
```

One commit, and it's yours: no duplicate.

---

## No git identity in the container: rebase dies halfway

**Symptom**

```
fatal: unable to auto-detect email address
```

You land in detached HEAD and push is rejected as non-fast-forward. From there, `rebase --continue` says `error: you have staged changes`, and `commit --amend` says `fatal: You are in the middle of a cherry-pick -- cannot amend`. **Tangled.**

**Fix**
`rebase --abort`, then **set `user.email` / `user.name` first**, then start over. The commit survives the abort. `status -sb` showing `ahead 1, behind 1` is the normal state.

**Convention**
Put an identity check **ahead of** the pull-rebase loop in every automation script.

---

## Two schedulers producing the same artifact collide every day

**Symptom**
A CI scheduler (00:00 UTC) and a local task scheduler (09:00 KST) both write and commit the same file → a rebase conflict every morning → one side **gives up silently.**

**Cause**
When the automation was migrated, the old actor was **disabled but not deleted**, or simply forgotten.

**Fix**
**One artifact, one actor.** When you migrate, **delete** the old actor (don't just disable it).

**Five places to sweep on migration**
Scheduled tasks · the script file itself · cron · hooks · workflows

**How it was found (for the record)**
Full orphan-document sweep → ghost file → ghost path. A side branch of a different investigation. The duplication was silent; left alone, it would never have surfaced.

---

## Cron + a `pgrep` duplicate-run guard catches itself

**Symptom**
The job **never runs. Not once.** No error, no log. Cron records a clean exit 0.

**Cause**
The shell cron spawns has **the script name on its command line**, so `pgrep` hits every time → "already running" → immediate exit, every run.

**Fix — PID file + `kill -0`**

```bash
PIDFILE=/tmp/job.pid
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then exit 0; fi
echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT INT TERM HUP
```

`kill -0` sends no signal; it **only checks existence.** A dead PID passes, so a stale file can't block you.

★ **Check all three:** 1) the file is non-empty (`-s`) 2) the content is **numeric** 3) **that PID is alive**

**Later case — the silence read as "no orders"**
The same guard sat on an order-notification loop. Cron logged a clean exit 0 every run, and the stretch with no notifications at all was **read as "no notifications = no orders."** A second, unrelated cause was blocking the same path that day, so fixing the guard brought nothing back.

★ **When silence has two causes, fixing one changes nothing visible.** If the silence survives your fix, suspect "there's another cause" before "the fix was wrong."

---

## Forget the `trap` on a lock file and every subsequent run dies

**Symptom**
Since the lock was introduced, the job doesn't run at all. **No log, exit code 0.**

**Cause**
`rm -f` was only on the normal exit path. If the process dies, the lock **stays forever** and every later run exits quietly.

**Fix**

```bash
trap 'rm -f "$LOCK"' EXIT INT TERM HUP
```

**★ This is the trap created by the previous entry's fix.** `pgrep` guard → PID lock → stale lock. Two stages in one day.

---

## The safeguard blocks the thing it was protecting (the general case)

Same shape three times in one day.

| Safeguard | Meant to block | Actually blocked |
|---|---|---|
| `pgrep` guard | Duplicate runs | **Itself** — immediate exit every time |
| Lock file | Overlap | **Every later run** — permanent block after a crash |
| Ever-growing `seen` set | Reprocessing | **All candidates** — the filter exhausted them and the system went silent |

★ **Whenever you write a safeguard, ask: "Can this block the body, not just the target?"**

**About the `seen` set**
A deduplication list that grows without bound eventually drives candidates to zero. Give it a **TTL**, or **count it against the population** and watch for exhaustion. Zero candidates may not mean "none"; it may mean **"all filtered out."**

**The other direction — the safeguard lets the target through**
The three above are safeguards that blocked the body. It also runs the other way.

| Safeguard | Meant to catch | Actually did |
|---|---|---|
| Regex detecting bad tracking numbers | An order number typed into the tracking-number field | **Put `^\d{10,14}$` on the allow-list** — the exact shape of the incident |

Back-test a detection rule against past incidents. If it doesn't fire on them, the rule doesn't exist. Details in chapter 02, "The validator had the very shape it was meant to catch on its allow-list."

---

## Shared hosting's process limit makes your watchdog kill its own child

**Symptom**
A background collector quietly dies every 30–60 minutes. No traceback. The log stops mid-line.

**Cause**

```
fork: Resource temporarily unavailable
```

Restricted shells on shared hosting set **a very low per-user process limit (`ulimit -u`).** And the watchdog wrapper I wrote ran this on every loop:

```bash
while [ "$(ps aux | grep -c '[j]ob_name')" -gt 0 ]
```

One `ps`, one `grep`, one worker. **Every poll burns three process slots** → limit exceeded → the child gets killed.
**The wrapper was killing the process it existed to protect.**

**Iron rules**
1. **No `ps` / `grep` polling** in background watchdog scripts
2. Prevent concurrent runs with a **lock file**
3. Long jobs: **pile all arguments into one process.** Don't split into batches and launch several.
4. **Partial save per item** → progress survives a crash. This saved the day more than once.

**What it looks like once you're over the limit**
When `fork` starts failing, **you can't even open a new SSH session.** Shells already attached can't run commands.
★ **If the number of standing cron jobs is already over the process limit**, the moment a couple of batches overlap they push each other out. Nobody counts them at registration time because each one is just one.
★ **Batches run one at a time, sequentially.** If "it seems stuck" keeps happening, suspect this.

Image conversion tools need `-limit thread 1` + `MAGICK_THREAD_LIMIT=1` for the same reason. Without it, **everything fails while reporting "done"**; always count the output files.

**Three more remedies**
1. **A one-time pre-check before starting** — if `ps -u "$(id -un)" | wc -l` is over a threshold (say 12), skip this run. Count once at startup, not in a polling loop
2. **`nice -n 10`** — lower the batch's priority so SSH stays responsive
3. **Check for duplicate cron registrations** — `crontab -l | grep -c <name>` should be 1. The same entry registered twice fills the limit twice as fast

---

## `nohup` alone dies when the session ends

**Symptom**
Launched with `nohup ... &`; the shell session changed and it was gone. Log cut off mid-line, zero processes.

**Cause**
Shared hosting's restricted shell reaps child processes when the login session ends.

**Fix**

```bash
setsid nohup python3 script.py args < /dev/null > out.log 2>&1 & disown
```

- `setsid` detaches into a new session
- `< /dev/null` detaches stdin
- `disown` removes it from the job table

**Side lesson**
Long jobs get all their arguments in one process. Split into several launches and they block each other on the external API's concurrency limit.

---

## Widen the filter and already-closed items come back to life

**Symptom**
Collection window widened to 30 days. An order **delivered on August 4** was newly registered on August 27 and a "delivered" notification went out again.

**Cause**
The moment you widen the window, closed items become targets again. Only the widening was considered; **the back-end filter to drop them** was never added.

**Fix**
1. Exclude items older than N days from new registration
2. Auto-remove items N days after reaching a terminal state

★ **When you widen a filter, add a matching filter behind it to remove what the widening let in.**

---

## "Which file actually runs" is settled only by following the call chain to the end

**Symptom**
Edited a file; the change is gone on the next run.

**Cause**
The runner **copied the canonical script into a date-stamped file and ran that.** Patch the dated file and the next run overwrites it with a fresh copy.

**Fix**
1. Before patching, **trace the call chain to the end** and confirm the canonical file
2. Patch only the canonical file; **never the derived copies** (they get overwritten anyway)
3. Delete the fragments or move them to `_archive/`. Left in place, you'll pick the wrong one again.

★ **"Not in the crontab" ≠ "not automated."** Only one entry was in cron; three more hops hung off it.

**Same family**
Values entered in a console or dashboard (keys, toggles, manual edits) **are not in the repo.** Patch from the local copy as the base and **the key gets overwritten with an empty value and the feature quietly turns off.** Re-download the live file before patching; confirm the value survived after. Losing it raises no error.

**When the canonical file is right and the old rows are wrong**
Some defects never show up no matter how long you read the code — **because the current canonical file is correct.** The canonical script set a flag to `True`; half the registered rows had `False`, and the defect appeared **only below a certain ID.** A clean ID boundary means not "a bug in the current code" but **"rows uploaded earlier by a different path (manual, an older script)."** The diagnostic is not a code audit. Split the population by ID range into generations, sample each one, and ask **"when was this uploaded, and by what."** If accounts had different upload paths, the same defect shows up in one account only.

★ **A clean ID boundary says: look at the upload generation, not the code.**

---

## Secret hygiene

**Tokens**
A full-scope (classic) token left in chat or logs is equivalent to leaking the account master key.
→ **Fine-grained + single repo + least privilege + short expiry**, deleted right after use.

**★ An instruction to put the value inside code is itself a leak path.**
I once told someone to type an app password directly into a heredoc. Plaintext exposure → revoked and reissued immediately.

**Fix**
Secrets go in by **file append**, not through code.

```bash
printf 'KEY=%s\n' "value" >> .env
```

As a **shell argument** the value scrolls by and doesn't land in a code block. It still lands in shell history, so the truly safe route is **a human editing the file in an editor.**

**"The value is definitely right" but auth keeps failing: print a fingerprint and compare**

```python
fp = f"{len(V)} chars | {V[:6]}…{V[-4:]}"
has_ws = V != V.strip()
```

Real incident: a copy-paste **dropped the first character** of a token, leaving 45. Two redeploys didn't find it; a fingerprint of the value the server actually held did. Also check leading/trailing whitespace and newlines, unwanted prefixes, and the wrong variable name.

---

## When a resource runs out, your diagnostic tools go with it

**The incident**
Cron entries grew to **74** and crossed the process limit.

```
fork: Resource temporarily unavailable
```

**★★ This is where it gets bad.** Every external command needs to `fork`, so **`ps`, `pkill`, `cat`, `chmod` and `crontab` all stop working.** You cannot see what is running, so **you cannot tell what to kill.**

★ **The commands you normally check with become unusable exactly when you need them.** Same shape as a full disk refusing new SSH sessions — **exhaustion takes observability first.**

**★★ An emergency route that consumes the normal resource is unavailable in an emergency**
- The shared-hosting panel has **no process manager**
- `/proc` is **container-isolated** and shows only your own; you cannot kill anything else
- **The web terminal draws on the same process limit** — equally blocked

The one remaining route was **deleting entries from the cron list screen in the control panel** — the only path that consumed no process.

★ **When designing a recovery route, look at what resource that route consumes.** If it is the same resource that is exhausted, it is not a recovery route.

**★★ Recovery technique — what runs without forking**
Shell builtins (`echo`, `read`, `kill`, `for`) run **without forking.** And **once a single interpreter is up**, `os.kill`, file writes and subprocesses inside it can do everything else.

★ **Near zero resources, switch from "issue many commands" to "one execution that does all of it."** The whole problem is **securing one process.**

**Removing the cause does not remove the symptom**
★ **Deleting the cron entries does not kill the processes already spawned.** You have to wait for recovery. Concluding "it isn't fixed" and intervening further makes it worse.

**★★ Count schedules by occurrences per hour, not by lines**
Half the problem was **ten sub-hourly cron entries.**

```
1-59/4 · 3-59/8 · 1-59/5 · 2-59/9 · 9-59/10 · ...
```

Each reads as "once every few minutes" and looks small. **Ten of them together spawn close to 100 per hour.**
★ **Counting cron entries is not enough. Sum the per-hour rate of each line.**

**Fix — a sequential runner**
Keep the work list in a file and have **one cron entry pull one item per tick.**

1. **A PID lock pinning concurrency at one** (the `pgrep` approach matches itself — don't)
2. **Refuse to start at all if the process count is above a threshold**
3. **A `timeout` shorter than the interval** so ticks never overlap

★★ **Availability beats throughput. One sequential worker beats twenty concurrent ones.**
★★ **Raising the gate looks like more throughput, but crossing the limit stops everything.** Aiming for 20 lands you at 0.

**★★★ How it got there**
Batch size was raised, the concurrency gate was raised, and cron entries were added. **All three at once.** Each was a reasonable-looking throughput adjustment on its own.

★ **High priority does not mean it is safe to do a lot at once.**
★ **On a capped resource, the optimum is in the middle, not at either end.** Elsewhere the same system had a limit set **far too low** and was suppressing itself; here one was set **far too high** and everything stopped. Two ends of the same mistake.
