# AI Coding Landmines — a field guide

English | **[한국어](README.md)**

**Traps actually stepped on while building with AI coding agents.**

Nothing here was learned by reading. **All of it was learned by stepping on it.** Every entry is an incident that really happened, and in most cases the cause was found only **after the bill came due.**

> For six weeks the batch changed nothing. Every response was `200 SUCCESS`.
> The cron never ran once. The exit code was 0 every time.
> All 47 registrations succeeded. Every one had zero images.

---

## Why collect these

Hand code to an AI agent and **throughput outruns judgment.** Dozens of items get processed in one go and the result comes back as a summary. That is why **more than half the entries in this repo are "silent failures"**: a structure where failure looks like success, or looks like a fact.

Three disciplines run through the whole thing.

1. **No response is proof of success. Only re-fetch is.**
2. **0 results is an observation, not a conclusion.** So is "not found", and so is a success flag. Look at how the observation was produced first.
3. **A hypothesis without a control group was always wrong.** Get the working one in hand and put it side by side.

---

## Contents

| | Category | Covers |
|---|---|---|
| 01 | [Windows · PowerShell](mines/en/01-windows-powershell.md) | PS 5.1 and CP949, BOM-less `.ps1`, native exe argument and stderr traps, encoding boundaries |
| 02 | [Python · DB · Data logic](mines/en/02-python-db.md) | Silent failure, "absent" vs "not found", identifier misuse, name matching, upsert reverting state |
| 03 | [Git · Automation · Cron](mines/en/03-git-automation.md) | Silent auto-push, `pgrep` self-detection, stale locks, fork limits, secret hygiene |
| 04 | [Claude Code · AI Agents](mines/en/04-claude-code-agent.md) | Hook path expansion, container repo rollback, vanished artifacts, the green-CI illusion |
| 05 | [Deploy · Infra · External APIs](mines/en/05-deploy-infra.md) | Symptomless rollback, missing COPY, sync-route timeouts, OAuth traps |
| 06 | [Write APIs · How not to trust the response](mines/en/06-write-api.md) | Five ways a success response lies, reading a 400 as 0 rows, partial updates silently ignored |

---

## A note for readers outside Korea

This guide was written on a Korean-locale Windows machine, against Korean marketplace APIs, with Korean product data. Several entries exist *only because of that*: code page 949, Hangul in file paths, CJK substring matching, status values that are Korean prose rather than enum codes.

Those entries are kept, not trimmed. Each carries a short **"Why this bites non-ASCII users"** note explaining what English-only setups never see. If you ship software for any market where the data isn't ASCII, that is the part you won't find elsewhere.

---

## Format

Each entry runs **Symptom → Cause → Fix → (where there is one) Verification.**

**Symptom comes first for a reason.** These traps look obvious once you know the cause, but **at the moment you step on one, the symptom is all you can see.** An entry is only useful if it can be found by its symptom.

`★` marks the one line in that entry **that was actually paid for.**

---

## A few favorites

- **[The safeguard blocks the thing it was protecting](mines/en/03-git-automation.md)** — a duplicate-run guard caught itself and the job never ran. Fixed that, and a stale lock blocked every run after. **Two stages in one day.**
- **[Truncation that keeps the value from changing](mines/en/02-python-db.md)** — process `Killed` (137). Looked like memory; real usage was 36MB and the cause was a CPU-bound infinite loop. **A length cap after an increment breaks monotonicity.**
- **[A synchronous bulk route dies at the caller's timeout](mines/en/05-deploy-infra.md)** — the same mine stepped on four times with a different fix each time. The conclusion alone (immediate 202 + background) can't be reproduced from, so the sequence is kept.
- **[Five ways a success response lies](mines/en/06-write-api.md)** — `200 + SUCCESS` and the value doesn't change. Not knowing this, **a batch changed nothing for six weeks.** The length in the progress file was the length of the string *we tried to send.*
- **[A hypothesis without a control group](mines/en/04-claude-code-agent.md)** — five hypotheses, every one an assertion beyond what was observed, every one wrong. The real cause was one line in the dependency list.

---

## Author

**KOHGANE** — has been running commerce automation pipelines alongside AI agents and piling up what got stepped on in an Obsidian vault. This repo is **only the portion that qualifies as general technical traps**, extracted and cleaned. Operational details, partners, accounts, and infrastructure identifiers are all excluded.

The cases come from a commerce domain, but the mines themselves don't care about the domain. Anyone who deals with an API with an approval workflow, runs batches on cron, or hands bulk work to an agent will get caught in the same places.

## License

[CC BY 4.0](LICENSE) — use, modify, and redistribute freely with attribution.

> Kohgane, *AI Coding Landmines* (AI 코딩 지뢰 도감), CC BY 4.0
