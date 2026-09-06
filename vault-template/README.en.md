# vault-template

English | **[한국어](README.md)**

An Obsidian vault template for keeping the **context that evaporates between sessions** when you work with AI coding agents.

## The problem this vault solves

A session with an agent is gone when it ends. The trap you stepped on yesterday, the decision you made last week, the procedure you fumbled through for the third time: none of it exists for the agent in the next session. So you step on the same mine again, re-argue the same decision, and re-derive the same procedure.

This vault keeps that context as **a graph of notes the agent reads at the start of every session.** It is not a human's notebook; it is the agent's memory. One rule: **write only what must survive the end of a session.** A new session's agent starts at `00_HOME.md`.

## The five-way taxonomy

There are only five kinds of note. The folder is the category, and the color in graph view is the folder.

| Folder | `type` | What goes in | Naming rule |
|---|---|---|---|
| `지뢰/` (mines) | `지뢰` | Traps actually stepped on. Symptom → Cause → Fix → Verification | ends with `… 지뢰` |
| `결정/` (decisions) | `결정` | Decisions and their reasoning. Revisions accumulate as dated sections at the bottom | the decision itself is the title |
| `런북/` (runbooks) | `런북` | Procedures you run repeatedly. When to pull it out is the first line | starts with `런북 …` |
| `프로젝트/` (projects) | `project` | Current state of ongoing work, plus links. Links out to mines, runbooks, decisions | the project name |
| `인프라/` (infra) | `infra` | Services, accounts, and resources a project depends on. Purpose, access path, limits, related mines | the service name |

Alongside them sits `데일리/` (daily). Date files (`YYYY-MM-DD.md`, `type: daily`) hold that day's actions and metrics. Generate them automatically or write them by hand. It starts empty.

**Why five.** Mines say "don't step here again," decisions say "don't argue this again," runbooks say "don't fumble this again," projects say "here is where we are," and infra says "here is how you get in." Those are the five questions an agent needs answered in its first five minutes.

Infra notes **never contain secrets.** Record the account name and the *location* of the secret, not the value. Write the vault as if it might end up in a public repository.

The folder names are Korean because the vault was built in Korean. Rename them if you like, but rename the `path:` queries in `.obsidian/graph.json` to match, or the graph colors stop working.

## Conventions

Three lines, pinned in `00_HOME.md`:

1. Before working on a project, read the mines linked from its note.
2. Version cuts, decisions, and new mines become notes immediately. Don't be stingy with links. The graph is the memory.
3. Essentials only. The moment it turns into a novel, nobody reads it.

Per-note conventions live in each folder's `_TEMPLATE.md` as a fixed format. The core idea: **the title is an index, so keep it current; the body is a record, so let it accumulate.** Mines are never buried inside a decision or project note. They live as standalone notes in `지뢰/` with links pointing at them. Rule 1 only works if the mines are in the folder.

## Install

```bash
git clone https://github.com/Kohgane/ai-coding-mines.git
cp -r ai-coding-mines/vault-template my-vault
cd my-vault && git init -b main
```

The `vault-template/` folder is the entire vault. Copy it out and make it your own repository. In Obsidian, **Open folder as vault** and pick `my-vault`. Open graph view and the per-folder colors are already set.

Then:

1. Replace the placeholder links in `00_HOME.md` with your own project names.
2. Copy each folder's `_TEMPLATE.md` to create your first note. Leave `_TEMPLATE.md` itself in place.
3. Add one line to your agent's project instructions (for example `CLAUDE.md`): "At session start, read `00_HOME.md`."

`.gitignore` excludes all of `.obsidian/` and whitelists only `graph.json`. Workspace state and plugin caches differ per device and cause conflicts, but the graph color groups *are* the taxonomy and must look the same on every device. The reasoning is in the `.gitignore` comments.

## If you want example mines

The `지뢰/` folder in this template is empty. 110 real entries written in the same format live one level up in this repository.

→ **[../mines/en/](../mines/en/)** — AI Coding Landmines, a field guide. Six chapters: Windows · PowerShell, Python · DB, Git · Automation, AI Agents, Deploy · Infra, Write APIs. Korean originals in [../mines/](../mines/).

Port one entry from there into the `지뢰/_TEMPLATE.md` format and you will see immediately how this vault is meant to run.

## License

[CC BY 4.0](../LICENSE). The license at the repository root covers this folder too. Use, modify, and redistribute freely with attribution.

---

This template is the structure and conventions, with the content removed, of the vault that was actually used to record [the 110 mines in this repository](../README.en.md). Same skeleton, emptied out.
