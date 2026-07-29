# phd_study1
Effect of User Control — **AI Agents with User Control**

This repository contains a Flask web app for studying the **effect of user control
over an AI agent**. It ships several versions differing in *what kind of control*
the user is granted. Pick one with the `STUDY` env var.

| Version | `STUDY` | Type of control | Domain |
|---------|---------|-----------------|--------|
| **V2** (default) | `stock` | **Execution-version** — choose *which version the agent runs* | Stock-market report (functional, fixed content) |
| V2 (LLM) | `travel` | **Execution-version** | Travel planner (functional, LLM-driven conversational intake) |
| **V1** | `hiring` | **Decisional** — "deciding **WHAT** to do" | Hiring-candidate selection |
| V1 (draft) | `finance` | **Decisional** | Personal-finance allocation |
| **V-process** | `diet` | **Process** — "steering **HOW** it's done" | Diet / exercise planning |

## V2 — Stock report, execution-version control

Everyone does the **same task** (the agent writes a 2026 Q1 domestic/overseas
stock-market report). The control group is offered **2–3 versions** — each with
its **length / model / time** trade-offs — and picks which the agent runs. The
no-control group is told the agent will pick "the most appropriate version"
itself. **The final report is identical** across every version and both
conditions — only the *control experience* is manipulated (output held constant).

| Condition | URL | What the participant experiences |
|-----------|-----|----------------------------------|
| **version** (user-control) | `/?group=version` | Agent shows version cards (분량/모델/소요시간); **the user picks** which to run. |
| **auto** (no-control) | `/?group=auto` | "제가 판단했을 때 가장 적절한 버전으로 준비해드릴게요!" → agent proceeds. |

See **[REPORT_STUDY_DESIGN.md](REPORT_STUDY_DESIGN.md)**.

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

- **`STUDY=travel`** — V2 with a **real LLM**: the agent runs a natural
  conversational intake (destination / duration / companions / style), then the
  control group picks an execution version and the agent generates the itinerary.
  The itinerary is generated **once** from the gathered info and reused for every
  version, so the deliverable is held constant per participant. Needs Azure/OpenAI
  creds (`.env`); `USE_MOCK_GPT=1` runs a rule-based demo without a key.
- **`STUDY=finance`** — earlier V1 draft: allocate a monthly surplus across debt /
  emergency fund / investing. Also decisional control. See [FINANCE_STUDY_DESIGN.md](FINANCE_STUDY_DESIGN.md).
- **`STUDY=diet`** — process control: the agent decides the plan and the user steers
  the *process* (approve / modify / interrupt / raise autonomy). Conditions:
  `control` vs `auto`. See [STUDY_DESIGN.md](STUDY_DESIGN.md).

## Quick Start

```bash
pip install -r requirements.txt

# Demo mode (no API key needed) — stock study (V2) by default
./run.sh demo

# Other versions
STUDY=hiring  ./run.sh demo
STUDY=finance ./run.sh demo
STUDY=diet    ./run.sh demo

# Production mode (real LLM via Azure/OpenAI creds in .env)
cp .env.example .env   # then add your key(s)
./run.sh
```

Open `http://localhost:5000`. Force a condition per study: stock `?group=version`, hiring/finance `?group=decision`, diet `?group=control` (all also accept `?group=auto`).

## Data

Everything is logged to SQLite (`database/chatbot.db`):
- `conversations.condition`, `conversations.autonomy_level`
- `workflow_state.tool_name`, `.intervention_type`, `.source_selection`, `.autonomy_level`

`intervention_type` is the key behavioral DV:
- **V2 (stock):** `select_version` (user chose) / `agent_selected` (auto) / `confirm`; the chosen version id is in `.source_selection` (`1`/`2`/`3`).
- **V1 (hiring/finance):** `decide` (user chose) / `agent_decided` (auto) / `revise` / `confirm`; the chosen option id is in `.source_selection` (`1`/`2`/`3`, `A`–`E`, `custom`).
- **V-process (diet):** `approve` / `modify` / `interrupt` / `raise_autonomy` / `override`.

See [USER_DATA_GUIDE.md](USER_DATA_GUIDE.md) for how to inspect/export.

## More docs
- [REPORT_STUDY_DESIGN.md](REPORT_STUDY_DESIGN.md) — **V2** (stock) execution-version control design and what to fill in.
- [HIRING_STUDY_DESIGN.md](HIRING_STUDY_DESIGN.md) — **V1** (hiring) decisional-control design and what to fill in.
- [FINANCE_STUDY_DESIGN.md](FINANCE_STUDY_DESIGN.md) — finance decisional-control draft.
- [STUDY_DESIGN.md](STUDY_DESIGN.md) — V-process (diet) condition logic and control levers.
- [CHATBOT_README.md](CHATBOT_README.md) — architecture and API.
