# Windows · PowerShell

Assumes Windows PowerShell 5.1. Most of these raise **no error at all; the output just comes out quietly broken.**

**Why this chapter bites non-ASCII users**
Nearly every entry here is about text crossing an encoding boundary. If your data, paths, and string literals are pure ASCII, PowerShell 5.1's legacy defaults mostly pass through unnoticed. If they contain Korean, Japanese, Chinese, accented Latin, or emoji, the same defaults silently corrupt them. Every trap below was hit on a Korean-locale Windows box (code page 949), but the mechanism applies to any locale whose ANSI code page is not UTF-8.

---

## PowerShell 5.1 reads UTF-8 files as CP949

**Symptom**
Read a UTF-8 file with `Get-Content`, transform it, write it back: every non-ASCII character self-destructs. No exception.

**Cause**
`Get-Content` in PS 5.1 defaults to the system ANSI code page (949 on Korean Windows, 1252 on US English, 932 on Japanese). The UTF-8 bytes are decoded as that code page the moment they become a string, so the damage is already done; writing back just bakes it into the file.

**Why this bites non-ASCII users**
On an English-locale machine with ASCII-only content, code page 1252 and UTF-8 agree on every byte you'd normally see, so this bug is invisible. Add one Hangul syllable (three UTF-8 bytes) and 949 decodes them as one-and-a-half garbage characters. Non-ASCII content is what makes the default encoding matter.

**Fix**
- Read: pass `-Encoding UTF8` explicitly
- Write: `New-Object System.Text.UTF8Encoding($false)` + `[IO.File]::WriteAllText` (no BOM)

Don't trust the defaults of `Out-File` / `Set-Content` either. Any file another tool will read gets an explicit encoding.

**Verification**
Read the file back after writing and compare it to the original string. Eyeballing console output is not enough: the console code page adds one more translation layer and blurs the verdict.

---

## Korean literals in a BOM-less `.ps1` come out garbled

**Symptom**
Script saved as UTF-8 without BOM. Run under `powershell.exe`, the Korean strings embedded in the source print as garbage. Korean inside comments is harmless; what dies is **output strings and paths containing Korean.**

**Cause**
With no BOM, the PS 5.1 parser reads the *script source itself* as system ANSI (949). The previous entry is about *data file I/O*; this one is about the *source file being parsed*. Different layer, same root.

**Why this bites non-ASCII users**
"Save as UTF-8 without BOM" is standard hygiene in most editors and linters, and the correct default for practically every other toolchain. PowerShell 5.1 is the one that punishes it, and only when the source has non-ASCII in it. An ASCII-only script never notices.

**Fix**
Adding a BOM fixes it but collides with a "no BOM" rule. If you must keep the rule:

- Keep the source **pure ASCII** and decode the non-ASCII strings at runtime.
  ```powershell
  function U($b64) { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64)) }
  ```
- Never write a path containing non-ASCII as a literal. Assemble it from `$env:USERPROFILE` and friends.

**Verification**
`LC_ALL=C grep -n '[^ -~]' script.ps1` — no output means pure ASCII.

---

## `2>&1` on a native exe: exit 0, but `$?` is false

**Symptom**
A native executable like `git` exits 0, yet `$?` is false and git's ordinary progress messages are spewed as red errors.

**Cause**
When you redirect a native exe's stderr with `2>&1`, PS 5.1 **wraps each line in an ErrorRecord.** Writing anything to stderr is treated as failure. Plenty of CLIs send normal progress to stderr.

**Fix**
Don't put `2>&1` on native commands. If you must swallow output, wrap it:
```powershell
try { & $exe @args 2>&1 | Out-Null } catch { }
```

**Verification**
Look at `$LASTEXITCODE`. For native commands, that is the success signal, not `$?`.

---

## Double quotes inside a commit message split the arguments

**Symptom**
```
git commit -m "... "ok:1284"처럼 ..."
error: pathspec '남길' did not match any file(s) known to git
```
(The "pathspec" git complains about is a Korean word from the middle of the message.)

**Cause**
PowerShell re-parses arguments before handing them to a native exe. A double quote inside the string terminates the quoting, and from that point the rest is split on whitespace. A word in the middle of your message suddenly becomes a pathspec.

**Fix**
- Don't put double quotes in the message (the only bulletproof option)
- Otherwise: single quotes, backtick escapes, or `git commit --file <tempfile>`
- Multi-line messages: single-quoted here-string `@'...'@`, and the closing `'@` **must sit in column 0**

**Verification**
`git log -1 --format=%B` shows what was actually stored.

---

## Environment variable keys can't be non-ASCII

**Symptom**
Put Korean in an environment variable *key* and somewhere along the chain (shell, PaaS console, `os.environ`) it fails to take or comes out mangled. The **key**, not the value.

**Cause**
How env var keys are encoded is guaranteed differently by every platform and shell. Values mostly get through; keys have paths where they don't.

**Why this bites non-ASCII users**
It's tempting to name config in your own language when the values are already in it. Values ride through as opaque bytes most of the time. Keys are parsed, matched, and normalized by every layer, and at least one layer will assume ASCII.

**Fix**
Keys are **Latin letters, uppercase, underscores.** If you need to group by prefix, the prefix is Latin too.

---

## Don't paste multi-line blocks onto a live prompt

**Symptom**
A Username / password prompt is waiting. You paste a block of commands. The prompt **eats the following lines as input.** The next command ends up typed into the password field.

**Fix**
Split the block. Paste the next piece only after the prompt has gone quiet.

---

## Emoji through a heredoc kills the script

**Symptom**
Python code written inside a shell heredoc, an emoji inside the Python, and the surrogate pair gets broken. The script dies.

**Cause**
The shell → Python hop is **one more** encoding boundary. Each boundary applies its own rules.

**Why this bites non-ASCII users**
Emoji sit outside the Basic Multilingual Plane and CJK needs multi-byte sequences; ASCII never does. A heredoc that passes ASCII text untouched can still corrupt these.

**Fix**
1. Don't push it through a heredoc. **Write it to a file, then run the file.**
2. Put the **emoji character itself** in the source, not an escape sequence.

Same reason we don't apply large patches via heredoc.

---

## Encoding changes at every tool boundary (the general case)

Every time text crosses a tool boundary, the encoding rules change. **Neither side raises an error.** Only the output comes out quietly broken.

| Boundary | Symptom |
|---|---|
| File → `Get-Content` | UTF-8 read as 949, written back, non-ASCII self-destructs |
| File → powershell.exe parser | No BOM, source read as ANSI, literals garbled |
| Shell heredoc → Python | Emoji surrogate pairs broken |
| PS → native exe arguments | Double quotes re-parsed, arguments split |
| Code → env var key | Non-ASCII key ignored or mangled |

**Principles**
1. **Cross boundaries with files.** Don't shove bulk text through inline strings.
2. **Don't leave non-ASCII as literals.** If you can't guarantee the code page the source will be read in, decode at runtime or fall back to Latin letters.
3. **Print once after the hop.** Look at the actual bytes right after they cross the boundary.
