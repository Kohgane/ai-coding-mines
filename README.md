# AI 코딩 지뢰 도감

**[English](README.en.md)** | 한국어

**AI로 개발하다 실제로 밟은 함정들.**

읽어서 배운 게 아니라 **밟아서 배운 것**만 모았다. 각 항목은 실제로 발생한 사고이고, 대부분 **대가를 치른 뒤에** 원인을 알았다.

> 6주 동안 배치가 아무것도 바꾸지 못했다. 응답은 매번 `200 SUCCESS`였다.
> 크론이 한 번도 안 돌았다. 종료 코드는 매번 0이었다.
> 등록 47건이 전부 성공했다. 전부 이미지가 0장이었다.

---

## 왜 이걸 모으나

AI에게 코드를 맡기면 **속도가 판단을 앞지른다.** 한 번에 수십 건이 처리되고, 결과는 요약으로 돌아온다. 그래서 이 저장소의 항목 중 **절반 이상이 "조용한 실패"** 다 — 실패가 성공처럼, 또는 사실처럼 보이는 구조.

관통하는 규율은 세 문장이다.

1. **어떤 응답도 성공의 증거가 아니다. 재조회만이 증거다.**
2. **0건·미발견·성공플래그는 결론이 아니라 관측이다.** 그 관측이 나온 경위를 먼저 본다.
3. **대조군 없이 세운 가설은 예외 없이 틀렸다.** 되는 놈을 먼저 손에 넣고 나란히 놓는다.

---

## 목차

| | 분류 | 내용 |
|---|---|---|
| 01 | [Windows · PowerShell](mines/01-windows-powershell.md) | PS 5.1 CP949, BOM 없는 `.ps1`, 네이티브 exe 인자·stderr, 인코딩 경계 |
| 02 | [Python · DB · 데이터 로직](mines/02-python-db.md) | 조용한 실패, "없음"과 "못 찾음", 식별자 오용, 이름 매칭, upsert 상태 되돌림 |
| 03 | [Git · 자동화 · 크론](mines/03-git-automation.md) | 무음 자동푸시, `pgrep` 자기탐지, 락 잔재, fork 한도, 비밀값 위생 |
| 04 | [Claude Code · AI 에이전트](mines/04-claude-code-agent.md) | 훅 경로 확장, 컨테이너 레포 역행, 산출물 증발, CI 그린 착시 |
| 05 | [배포 · 인프라 · 외부 API](mines/05-deploy-infra.md) | 무증상 롤백, COPY 누락, 동기 라우트 타임아웃, OAuth 함정 |
| 06 | [쓰기 API · 응답을 믿지 않는 법](mines/06-write-api.md) | 성공 응답이 거짓말하는 다섯 가지, 400을 0건으로 읽기, 부분 업데이트 무반영 |

---

## 이 도감의 형식

각 항목은 **증상 → 원인 → 해법 → (있으면) 검증 방법** 순이다.

**증상을 먼저 쓴 이유**가 있다. 이런 지뢰는 원인을 알고 나면 당연해 보이지만, **밟는 순간에는 증상밖에 안 보인다.** 그래서 증상으로 검색되어야 쓸모가 있다.

`★` 표시는 그 항목에서 **실제로 대가를 치르고 얻은 한 줄**이다.

---

## 몇 가지 좋아하는 항목

- **[방지 장치가 본체를 막는다](mines/03-git-automation.md)** — 중복 실행 가드가 자기 자신을 잡아 작업이 한 번도 안 돌았다. 고쳤더니 이번엔 락 잔재가 이후 전 회차를 막았다. **하루에 두 단계로.**
- **[절단으로 값이 안 변하는 무한루프](mines/02-python-db.md)** — 프로세스가 `Killed`(137). 메모리 문제로 보였지만 실사용량은 36MB였고 원인은 CPU 무한루프였다. **증가 연산 뒤에 길이 제한이 붙으면 단조성이 깨진다.**
- **[동기 대량 라우트 타임아웃](mines/05-deploy-infra.md)** — 같은 지뢰를 네 번 밟으며 처방이 네 번 바뀐 기록. 결론(즉답 202 + 백그라운드)만 쓰면 재현이 안 되므로 순서대로 남겼다.
- **[성공 응답이 거짓말하는 다섯 가지](mines/06-write-api.md)** — `200 + SUCCESS`를 받고도 값이 안 바뀐다. 이걸 모르고 **배치가 6주간 아무것도 못 바꿨다.** 진행 파일에 찍힌 길이는 *보내려 한* 문자열의 길이였다.
- **[대조군 없이 세운 가설](mines/04-claude-code-agent.md)** — 가설 5개가 전부 관측 범위를 넘어선 단정이었고 전부 틀렸다. 진짜 원인은 의존성 목록 한 줄이었다.

---

## English Summary

**A field guide to landmines hit while building with AI coding agents.**

Not lessons read in a blog post — **lessons paid for.** Every entry is an incident that actually happened, and in most cases the cause was found only after the damage.

### Why this exists

When you hand code to an AI agent, **throughput outruns judgment.** Dozens of items get processed at once and the result comes back as a summary. That is why more than half the entries here are one shape: **silent failure** — a failure that looks like success, or looks like a fact.

Three rules run through the whole collection:

1. **No response is proof of success. Only a re-query is proof.**
2. **"Zero results", "not found", and success flags are observations, not conclusions.** Look at how the observation was produced.
3. **Every hypothesis formed without a control was wrong.** Get a working case in hand and put it side by side first.

### Contents

| | Category | Topics |
|---|---|---|
| 01 | [Windows · PowerShell](mines/en/01-windows-powershell.md) | PS 5.1 CP949 corruption, BOM-less `.ps1`, native exe argument and stderr traps, encoding boundaries |
| 02 | [Python · DB · data logic](mines/en/02-python-db.md) | Silent failure, "absent" vs "not found", identifier misuse, name matching, upsert reverting state |
| 03 | [Git · automation · cron](mines/en/03-git-automation.md) | Silent auto-push, `pgrep` self-detection, stale lock files, fork limits, secret hygiene |
| 04 | [Claude Code · AI agents](mines/en/04-claude-code-agent.md) | Hook path expansion, container repo regression, vanished artifacts, green-CI illusion |
| 05 | [Deploy · infra · external APIs](mines/en/05-deploy-infra.md) | Symptomless rollback, missing COPY, sync-route timeouts, OAuth traps |
| 06 | [Write APIs · not trusting the response](mines/en/06-write-api.md) | Five ways a success response lies, reading a 400 as "zero rows", partial updates silently ignored |

### Format

Each entry is **Symptom → Cause → Fix → (where applicable) How to verify**.

Symptom comes first on purpose. These traps look obvious once you know the cause, but **at the moment you step on one, the symptom is all you can see.** It has to be findable by symptom to be useful.

`★` marks the one line that was actually paid for.

A full English edition is available: **[README.en.md](README.en.md)**. The Korean-specific entries (CP949, Hangul paths, CJK matching) are kept there with notes on why they matter to non-ASCII users.

---

## 지은이

**KOHGANE** — 커머스 자동화 파이프라인을 AI 에이전트와 함께 굴리면서 밟은 것들을 옵시디언 볼트에 쌓아왔다. 이 저장소는 그중 **일반적인 기술 함정에 해당하는 분량만** 골라 정제한 것이다. 운영 정보·거래처·계정·인프라 식별자는 전부 제외했다.

사례가 커머스 도메인에서 나온 건 맞지만, 지뢰 자체는 도메인과 무관하다. 승인 워크플로가 있는 API를 상대하거나, 크론으로 배치를 돌리거나, 에이전트에게 대량 작업을 맡기는 사람이면 같은 자리에서 걸린다.

## 라이선스

[CC BY 4.0](LICENSE) — 출처를 밝히면 자유롭게 쓰고, 고치고, 재배포할 수 있다.

> Kohgane, *AI 코딩 지뢰 도감* (AI Coding Landmines), CC BY 4.0
