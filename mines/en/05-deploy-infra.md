# Deploy · Infra · External APIs

---

## Missing `requirements.txt` entry → symptomless rollback

**Symptom**
Only the newly added route 404s. The app itself is fine (every other route 200). git push succeeded, the file and the registration line exist on the remote, local import passes on the server. Wait eight minutes: still 404.

**Cause**
`requests` was missing from `requirements.txt`. On a clean build the new module fails to import → app fails to start → **the PaaS keeps serving the last successful build.** Hence "app is healthy, only the new route is missing."

**Why it's easy to miss**
Existing code was already using `requests` without it being in requirements. It only worked because it was cached in the existing container. **It only blows up on a clean build.**

**Iron rules**
1. When adding a module, **diff the import list against `requirements.txt`**
2. New route 404 after deploy → **suspect dependencies first** (not a lost commit)
3. **A successful push is not evidence of a successful deploy.** Hit the real URL.
4. **A successful local import is not evidence of a successful deploy.**

---

## A file the runtime reads isn't in the image

**Symptom**
Local and CI unit tests all green (the file exists in the repo), but **only in the deployed build**: 404 / 400 / file not found. Same type, three recurrences.

**Cause pattern**
A route reads a relative path (`Path("data/x.json")`) and that file isn't in the image. Two root causes, sometimes both:
1. The Dockerfile doesn't COPY that directory
2. `.dockerignore` excludes the whole directory, so it is **gone before the build context even forms**

**Fix**
- **COPY whole directories by default.** Per-file COPY leaks new artifacts every time.
- If a directory mixes in runtime-generated files and can't be copied whole → **explicitly COPY the required static files + `!` re-include in `.dockerignore`**
- In CI, after the image build, **prove existence** with `test -f /app/data/*.json` and fail the job if it's missing

**Habit**
Whenever you add or move a path the runtime reads, **three-way check**: (1) Dockerfile COPY (2) `.dockerignore` exclusions (3) the route's relative path vs WORKDIR

**Verification trick (when you can't pull the base image)**
`.dockerignore` has nothing to do with the base image. Build the same `COPY` lines `FROM scratch` and context inclusion is verified as-is: if excluded, it fails with "not found in build context."

---

## On a 512MB instance, ffmpeg takes the whole worker down

**Symptom (it doesn't say OOM, so you don't recognize it)**
- Light endpoints return 200; only certain requests 502
- No OOM text in the logs, just repeated `Instance restarted`
- The memory graph spikes to the ceiling and drops

**Cause**
With the Python process resident, fork+exec of ffmpeg as a subprocess spikes memory momentarily. The real peak came from **libx264 re-encoding.**

**Fix — don't re-encode**
If the source is already h264 mp4, just swap the audio.

```bash
ffmpeg -i v.mp4 -i a.mp3 -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a aac -b:a 128k -shortest -movflags +faststart out.mp4
```

Fallback: `-preset ultrafast -crf 28 -threads 1`

**Note**
`WEB_CONCURRENCY=1 by default` in the logs means you are on the smallest instance.

---

## A PaaS `/tmp` is wiped on every redeploy and restart

**Symptom**
Try to use a file you generated earlier: `404 Not Found`. The same cause reproduces a `download failed HTTPError` mid-pipeline.

**Workaround**
Generate → process → upload **as one uninterrupted run** and it's fine. But **"generate now, publish later" and scheduled publishing are impossible.**

**Resolution**
Auto-upload artifacts to object storage. Fall back to the existing path on failure so behavior doesn't break.

---

## With auto-deploy off, pushing still serves the old version

If some services need a Manual Deploy after push, you'll assume it deployed and start debugging.
★ **Watch for service confusion too.** It's easy to deploy a similarly named service and conclude "the change isn't taking."

---

## A synchronous bulk route dies at the caller's timeout

**Symptom**
Processed a high-count job synchronously inside one HTTP request; no response comes back. Partial work was committed, but with no response **you can't tell how far it got** (retrying risks duplicates).

**There is more than one timeout. This is the point.**
Stepping on this mine four times, **each time a tighter timeout appeared.**

| Axis | Nature |
|---|---|
| Worker timeout | Mine. I can raise it. |
| External scheduler timeout | **Can't raise it. Platform hard ceiling.** |
| Worst-case latency per item | External dependency, no guarantee |

★ **A count cap (limit) is not a time cap.** `limit=10` at a worst case of 8s per item is 80s. Under the worker timeout, over the external scheduler's 30s.

**The intermediate fix and its limits (worth keeping)**
First attempt: a **wall-clock budget.** Check elapsed time *before* starting each item; on hitting the budget, stop and return `{processed, remaining, budget_exhausted}` as 200. The next call picks up the rest. Grab, process, and commit one item at a time, so **zero half-done residue** on interruption.

**Still not enough.** Two reasons.
1. **Even with a 22s budget, the one item in flight can overrun.** Against a hard ceiling, "usually fits" is meaningless.
2. The route **stacked two heavy jobs.** The budget was only on the first; the second ran unbudgeted for another 20–40s. Worse, **the second job starved and never ran at all.** The external scheduler's red **doesn't tell you which hop starved.**

**The final fix: respond immediately, don't count backwards from a budget**
- The route **returns 202 immediately** and hands the real work to a **background thread**
- Scheduler verdict = **immediate 202 = success.** Real results are read from logs.
- A **re-entry guard.** But **idempotency is the foundation of multi-worker safety;** the lock is auxiliary.
- The thread **budgets itself to exit.** Keep the order:
  **job budget < scheduler interval < worker timeout**
- **Never stack two heavy external I/O jobs in one request.** If unavoidable, **reserve a minimum budget for each** so neither starves.

**Result**
`http=202 · 0.24s`. **Immediate-response design makes it constant time regardless of queue length.** With 100× headroom against the hard ceiling, that axis drops off the worry list.

**Rule**
> When the caller's timeout is a **platform hard ceiling** and the job might not finish inside it, don't shave the budget. Go **immediate response + background + idempotent resume + re-entry guard.** **Budget-shaving only works when the ceiling can be raised.**

**Don't build a separate state store**
Use the work items themselves as state (draft / published / meta flags *are* the progress). **Stateless resume** with no job store. If the work is already idempotent and resumable, an orphaned background thread is fine: the next call picks it up.

**Follow-up: measure the cost of doing nothing first**
With zero remaining, a tick still took over 30s. The tick was **fetching the full list twice, every time.** Even with nothing to do, that fixed cost burns.
→ A **completion cache that skips immediately** after convergence, fetch the list **once per tick** and share it, and log "0 targets" as **none (normal) vs fetch failed (abnormal).**
★ **Tune a periodic job only after removing its fixed cost. Then measure, then decide.**

---

## Pinning the API spec doesn't pin the *format* of the values

**Symptom**
Parser locked to the confirmed spec. A date field changed without notice from `2026-08-18` to `2026-08-18 00:00:00+00` and the consumer broke.

**Fix**
**Pin field names, normalize values defensively** (dates: first 10 characters, and so on). And when you touch the server, **check the consumers with it.**

---

## Disk full: SSH drops and JSON writes truncate

**Symptom**
Files saved truncated and corrupt. New SSH sessions won't open.

**Cause**
The CMS stores the original plus 4–8 thumbnail sizes. Uploading ~1,000 items at once filled the 10GB quota in a day.

**Four-layer defense**
1. Shrink originals at upload (long edge 1000px, q78)
2. Generate only the thumbnail sizes actually used (measured: just 4)
3. A disk-monitoring cron
4. Cap the number of images the uploader sends

Recovered a third of the disk.

---

## Misdiagnosing a public API's concurrency slot limit as a server outage

**Symptom**
503s. Looks like the server is down.

**How the misdiagnosis went (worth recording)**
"curl gets 200 but Python urllib gets 503" → **concluded it's a client difference** → curl immediately 503 too. In reality, the two clients were **fighting over 2 concurrent slots per IP.**
★ **A conclusion from a single observation.**

**Iron rules**
- **Never run two collection scripts at the same time**
- **Check slots via the status endpoint before requesting**
- 503 / 504 are noise during normal operation. **Absorb with retry + cooldown.**
- Mirrors are generally less stable. Fallback only.

---

## Switch away from a free geocoder with tight rate limits

**Symptom**
Public Nominatim: 1 req/s plus a daily cap. `RATE=1.15` gets 429; `1.6` still 429. Backoff grows to 300s and **stalls at 17%.** 10,000+ items would take 5+ hours with a ban risk.

**Fix**
Switched to Photon (Komoot) reverse geocoding.

```
https://photon.komoot.io/reverse?lat=..&lon=..&lang=en
```

- Lenient rate limit; ran at about 3 req/s
- Response: `street` / `housenumber` / `district` / `city` / `countrycode` under `features[0].properties`
- Sample 4/4 succeeded; results cleaner than Nominatim

---

## Calling a Gradio Space directly over REST

Call it with a **two-step REST flow** without the `gradio_client` package (no runtime dependency to add).

```
POST {base}/gradio_api/call/{fn}   body: {"data":[...]}   → event_id
GET  {base}/gradio_api/call/{fn}/{event_id}               → parse the result URL from SSE
```

`base` is `https://{owner}-{space}.hf.space` (lowercase, `/` → `-`).

**1. Don't guess parameters; check `info`**
`GET {base}/gradio_api/info` → `named_endpoints` lists every function name with parameter order, types, and defaults.
Guessing `predict` with `[prompt, '', w, h, 5]` spun uselessly. The real endpoint was `/generate_video` with `[prompt, aspect_ratio (a Literal string), steps, negative_prompt, ...]`.

**2. Send a float and you get error; it has to be int**
`0.0` (float) for `rate` / `pitch` → **`event: error` and nothing else.** `0` (int) works. **The error body is `null`, so the cause is invisible.** You only catch it by sending the same request with only the type changed.

**3. No token, error**
Anonymous calls get `event: error`. A free account's Read token is enough.

**4. The result URL is a temporary path**
Shaped like `{base}/gradio_api/file=/tmp/gradio/.../x.mp4`. Accessible but volatile; download and push to storage immediately.

---

## The Supabase key overhaul and an RLS misdiagnosis

| Type | Prefix | Use |
|---|---|---|
| Publishable key | `sb_publishable_` | Safe to expose in the browser (old anon) |
| Secret key | `sb_secret_` | Server only, bypasses RLS (old service_role) |
| Legacy tab | `eyJ...` (JWT) | Old anon / service_role, still works |

`service_role` moved to the Legacy tab. Current path: **Settings → API Keys → Secret keys**.

**The anon key can't write to Storage, and it invites a misdiagnosis**
Writes fail with `new row violates row-level security policy`, but **listing buckets returns an empty array with no error.** It looks like "there are no buckets," not a permissions problem.

**Warning**
Secret / service_role is **a master key that bypasses all RLS.** Server env vars only; never in the frontend or a public repo.

---

## WordPress REST: an encoded slash 404s

**Symptom**
`/wp-json/wp/v2/plugins/{slug}%2F{file}` returns 404. Plugin activate / deactivate is blocked.

**Cause**
Apache rejects encoded slashes.

**Workaround**

```
POST https://example.org/index.php?rest_route=/wp/v2/plugins/wordpress-seo/wp-seo
body: {"status":"active"}
```

The `rest_route` query form works (200).

**Stepped on alongside: don't judge from active plugins only**
Concluded "there's no SEO plugin." It was **installed and inactive.** `GET /wp-json/wp/v2/plugins` lists everything including inactive; use that.

---

## Play Console: "Released to production" may not be released

**Symptom**
Submission activity shows **Released to production**; the store is 404 in every region.

**Cause**
Play runs *country/region and listing changes* and *version (aab) releases* as **separate trains.** It was an **empty production track** with only countries opened; the aab was only on a test track.

**How to tell: don't trust the console, measure**

```bash
curl -s -o /dev/null -w "%{http_code}" -A "Mozilla/5.0" \
  "https://play.google.com/store/apps/details?id=<pkg>&gl=KR"
```

404 means not released. Production showing **"Inactive"** on the dashboard is the same signal.

**Fix**
Production > Create new release > (Add from library) > Review release → **press "Start rollout to Production."** Without that button it never ships. Then **Send for review** from the publishing overview.

**Side notes**
- **Never click the pre-registration card.** It queues *delete all production countries + enable pre-registration* for review, turning your live release into a "coming soon" page. Happened twice → withdraw via "Discard changes" in the publishing overview.
- **Managed publishing ON** means even after approval you wait for a manual "Publish" click
- **Two bundles (versionCode 1 and 2) in one release errors out.** Drop the lower one.
- The four recommended actions (edge-to-edge, deprecated APIs, orientation restrictions, R8) **are not blockers**

---

## The upload key fingerprint the console shows ≠ my keystore's fingerprint

**Symptom**
The actual certificate from `keytool -printcert -jarfile` and the console's App Integrity screen show **different fingerprints.** Reproduced on two apps.

**Fix (standard)**
Don't argue; **inject all three keys into assetlinks**: ① the Play app signing key ② the upload key the console shows ③ my build key. Whichever is real, it works. Let the server override via env var, but bake the three keys in as the default.

**Confusion warning**
If you see "signed with the wrong key," **first suspect you picked the wrong app.** That error came from uploading this app's aab onto another app's page (check the app badge top-right first).

```bash
unzip -p X.aab base/manifest/AndroidManifest.xml | strings | grep -oE "app\.[a-z]+\.twa"
keytool -printcert -jarfile X.aab | grep SHA1
```

---

## Three OAuth traps where the error message misleads

**1. `youtubeSignupRequired` ≠ no channel**
With `youtube.upload` as the **only scope**, the API can't identify the owned channel and throws an error that reads as "no channel." The channel existed.
→ Request `youtube.readonly` alongside.

**2. `403 access_denied`: a different account registered as test user**
While the publishing status is "Testing," only registered test users can authenticate. The registered address and the one used to authenticate **differed by one character,** and finding that took hours.
★ **It wasn't a typo. Both accounts were real.** Treating one as a "typo" and cleaning it up would have broken a different feature.
→ Don't trust email addresses by eye; **copy-paste** them, and **confirm which account** every time.

**3. A refresh_token in Testing status expires in 7 days**
Fatal for automation. **Publishing to production is mandatory.**
If the publish button is greyed out, it's because **the privacy policy and terms-of-service links on the branding page are empty.** → Added `/privacy` and `/terms` routes directly to the app. Publishing works without verification; you just click through the "unverified app" warning once during auth.

**Build the diagnostic tool first**
One endpoint that **shows the token's account, scopes, and channel at once.** **Don't guess; hit this first.**

---

## An account locked for exhausted balance doesn't unlock on top-up

**Symptom**
`User is locked. Reason: Exhausted balance`. Top up and the lock stays (a known bug on the provider side).

**Impact**
10 of 14 video-generation providers went through one gateway. **One lock kills most of the pipeline.**

**Response**
- Keep a healthy balance and top up well before zero
- **Don't put everything through one gateway; keep at least one on a separate route**
- If locked, skip the top-up retry and open a support ticket immediately

**Unlock signal (for reference)**
The first attempt getting a **timeout** instead of an immediate 403 was the sign that it was being processed.

---

## A performance diet comes back as "it feels unstable"

**Symptom**
Tightened cache and preload to protect frame rate. Frames held, but tiles filled late and the screen sat empty, and **that felt more unstable than the stutter did.**

**Cause**
**Load speed and frame rate are different axes**, but a diet treats them as one knob and tightens both.

**Fix**
- **Measure the two axes separately.** Watch fps and **time-to-tiles-filled** together.
- **Record the values before tightening** so you can revert. The revert was only possible because the old values were in a previous log.
- A loading indicator that **makes the wait visible** is also a perceived-performance tool (without touching the values).

---

## Three traps in TWA/Android builds on Windows

**1. The generator's update overwrites your settings**

Every `bubblewrap update` resets `org.gradle.jvmargs` in `gradle.properties` to its default. On a machine with less free memory than that, it fails immediately.

```
Could not reserve enough space for 1572864KB object heap
```

**Fix: use the environment variable instead of the file** — it takes precedence.

```powershell
$env:GRADLE_OPTS="-Xmx768m -Dfile.encoding=UTF-8"
```

★ **Settings you keep in a generator-managed file disappear at the next generation.**

**2. A non-ASCII project path is rejected**

```
Your project path contains non-ASCII characters
```

Work from an ASCII path. Do not disable the check — turning off the check does not teach the downstream tools to handle the path.

**3. Editing the manifest does nothing until you run update**

`twa-manifest.json` is **only a blueprint; the actual build input is `app/build.gradle`.** Change the package id and build straight away and you **get a build with the old package name.**

★ Also: editing it in a plain text editor mangles path escapes. Edit it structurally.

---

## Check the console before you throw a keystore away

**What happened — this cost real time**
A generated keystore would not open (password mismatch). **"It was never shipped, so discarding it costs nothing"** — regenerated.

**It had already been registered as the upload key.**

```
Android App Bundle signed with the wrong key
console expects SHA1  AA:BB:CC:DD:...   <- the keystore that will not open
ours                  11:22:33:44:55:...
```

Uploads were **permanently rejected**. An upload-key reset takes **2-7 days** to approve.

★ **"It was never used, so it is safe to delete" is only true within what I happen to know.** Registration may already have happened in a step I forgot.

**Rules**

1. **Look at the console's app-signing page before discarding a keystore**
2. Verify the password with `keytool -list -v` **immediately** after generating. **No bundles and no console entry until it passes**
3. Passwords: **letters and digits only.** Special characters break between tools
4. **Never create two keystores for the same app in two folders.** You will not be able to tell which one is registered

---

## The headroom your monitoring shows is not your headroom

**Symptom**
The disk filled up again. `df` reports **407GB free.** Writes still fail.

**Cause**
`df` reports the **whole server**. The actual limit was a **10GB account quota.**

★★ **Check what denominator the tool is showing you.** In shared environments almost every metric describes **the host, not your slice.** Process limits behave the same way — the ceiling is your account's `ulimit`, not the machine's core count.

**Also learned — establish the blast radius before cleaning up**

Not knowing what was safe to delete kept the problem untouched for a long time. Measuring it:

| Target | Size | Verdict |
|---|---|---|
| 1,002 oversized upload originals | 1.4GB | **can be downscaled** |
| 10,056 thumbnails at one size | 642MB | **not referenced by the theme** |
| Product images on an external platform | — | **on that platform's CDN, unrelated to this server** |

★ **Without establishing where things are actually stored, vague fear stops you from doing anything.** The last row especially — the product images were *assumed* to live on this server.

**★★ Downscaling was chosen over deletion**

Keeping the **same filename and path** and only shrinking the contents leaves **the database and every reference intact.** Deletion breaks if a single reference survives; downscaling has nothing to break.

★ **Prefer a measure that doesn't need undoing over one that can't be undone.**

**★★★ Put the target number in the code**

This was the **second** occurrence. The first time it was cleaned up too and a third of the space was recovered — but that was **first aid applied at the ceiling**, and the same wall came back.

This time the cleanup job **disarms itself once usage drops to the target**.

★ **A threshold a person remembers only fires during a crisis. A threshold in the code fires in peacetime.**
"We'll clean it up when it gets close" is not a plan; it is **a commitment to hitting it again.**
