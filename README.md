# phd_study1
Effect of User Control — **AI Agents with User Control**

This repository contains a Flask web app for studying the **effect of user control
over an AI agent**. It ships several versions differing in *what kind of control*
the user is granted. Pick one with the `STUDY` env var.

| Version | `STUDY` | Type of control | Domain |
|---------|---------|-----------------|--------|
| **V1** (default) | `hiring` | **Decisional** — "deciding **WHAT** to do" | Hiring-candidate selection |
| V1 (draft) | `finance` | **Decisional** | Personal-finance allocation |
| **V-process** | `diet` | **Process** — "steering **HOW** it's done" | Diet / exercise planning |

## V1 — Hiring decision, decisional control

The participant is a **hiring manager**. An AI recruiting agent **transparently
analyses applicants** and, at each decision point, lays out concrete options and
candidates — with trade-offs, risks, and the **limits of its own assessment** — as
**selectable option cards**. The manipulation is *who decides*.

> 당신은 한 IT 회사의 채용 담당자입니다. 마케팅팀 신입 1명을 뽑는데, AI 채용 에이전트가 지원자들의 서류·실무 과제·면접 기록을 분석해 정리해 줍니다. 에이전트와 대화하며 최종 합격자를 결정해 주세요.

| Condition | URL | What the participant experiences |
|-----------|-----|----------------------------------|
| **decision** (user-control) | `/?group=decision` | At 3 decision points (평가 기준 → 추가 검증 → 최종 합격자) the agent shows option cards + trade-offs and **the user picks**. |
| **auto** (no-control) | `/?group=auto` | The agent **decides everything itself** (criteria, verification, the hire) and reports it. |

Both conditions surface the same tool steps (스크리닝 → 기준 분석 → 검증 옵션 → 후보 비교 → 결정 정리) and the same transparent reasoning + stated uncertainty — only *who makes the call* varies. See **[HIRING_STUDY_DESIGN.md](HIRING_STUDY_DESIGN.md)**.

## Other versions

- **`STUDY=finance`** — earlier V1 draft: allocate a monthly surplus across debt /
  emergency fund / investing. Also decisional control. See [FINANCE_STUDY_DESIGN.md](FINANCE_STUDY_DESIGN.md).
- **`STUDY=diet`** — process control: the agent decides the plan and the user steers
  the *process* (approve / modify / interrupt / raise autonomy). Conditions:
  `control` vs `auto`. See [STUDY_DESIGN.md](STUDY_DESIGN.md).

## Quick Start

```bash
pip install -r requirements.txt

# Demo mode (mock agent, no API key needed) — hiring study by default
./run.sh demo

# Other versions
STUDY=finance ./run.sh demo
STUDY=diet    ./run.sh demo

# Production mode (real LLM via Azure/OpenAI creds in .env)
cp .env.example .env   # then add your key(s)
./run.sh
```

Open `http://localhost:5000` (add `?group=decision` or `?group=auto`; `?group=control` for the diet study).

## Data

Everything is logged to SQLite (`database/chatbot.db`):
- `conversations.condition`, `conversations.autonomy_level`
- `workflow_state.tool_name`, `.intervention_type`, `.source_selection`, `.autonomy_level`

`intervention_type` is the key behavioral DV:
- **V1 (finance):** `decide` (user chose) / `agent_decided` (auto) / `revise` / `confirm`; the chosen option id is in `.source_selection` (`1`/`2`/`3`/`custom`).
- **V-process (diet):** `approve` / `modify` / `interrupt` / `raise_autonomy` / `override`.

See [USER_DATA_GUIDE.md](USER_DATA_GUIDE.md) for how to inspect/export.

## More docs
- [HIRING_STUDY_DESIGN.md](HIRING_STUDY_DESIGN.md) — **V1** (hiring) decisional-control design and what to fill in.
- [FINANCE_STUDY_DESIGN.md](FINANCE_STUDY_DESIGN.md) — finance decisional-control draft.
- [STUDY_DESIGN.md](STUDY_DESIGN.md) — V-process (diet) condition logic and control levers.
- [CHATBOT_README.md](CHATBOT_README.md) — architecture and API.
