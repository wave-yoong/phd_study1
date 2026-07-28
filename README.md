# phd_study1
Effect of User Control — **AI Agents with User Control**

This repository contains a Flask web app for studying the **effect of user control
over an AI agent**. It ships **two versions** of a user-control agent, differing in
*what kind of control* the user is granted. Pick one with the `STUDY` env var.

| Version | `STUDY` | Type of control | Domain |
|---------|---------|-----------------|--------|
| **V1** (default) | `finance` | **Decisional** — "deciding **WHAT** to do" | Personal-finance allocation |
| **V-process** | `diet` | **Process** — "steering **HOW** it's done" | Diet / exercise planning |

## V1 — Finance allocation, decisional control

Participants delegate a goal (allocate a monthly surplus across debt / emergency
fund / investing) to an AI agent that **transparently analyses the situation and
lays out options with their trade-offs**. The manipulation is *who decides*.

> 당신은 매달 일정한 여윳돈이 생깁니다. AI 재무 에이전트가 당신의 재무 상황을 분석해, 이 여윳돈을 부채 상환·비상금·투자에 어떻게 배분할지 함께 계획합니다.

| Condition | URL | What the participant experiences |
|-----------|-----|----------------------------------|
| **decision** (user-control) | `/?group=decision` | At each of 3 decision points the agent shows options + trade-offs and **the user chooses what to do**. |
| **auto** (no-control) | `/?group=auto` | The agent **decides every allocation itself** and reports the finished plan. |

Both conditions surface the same tool steps (재무 진단기 → 배분안 생성기 → 비상금 설계기 → 투자 옵션 분석기 → 계획 통합기) and the same transparent reasoning — only *who makes the call* varies. See **[FINANCE_STUDY_DESIGN.md](FINANCE_STUDY_DESIGN.md)**.

## V-process — Diet planning, process control

The earlier version: the agent decides the plan content and the user steers the
*process* (approve / modify / interrupt / raise autonomy) at each step. Conditions:
`control` vs `auto`. Run with `STUDY=diet`.

## Quick Start

```bash
pip install -r requirements.txt

# Demo mode (mock agent, no API key needed) — finance study by default
./run.sh demo

# The diet (process-control) study instead
STUDY=diet ./run.sh demo

# Production mode (real LLM via Azure/OpenAI creds in .env)
cp .env.example .env   # then add your key(s)
./run.sh
```

Open `http://localhost:5000` (add `?group=decision` or `?group=auto` to force a condition; `?group=control` for the diet study).

## Data

Everything is logged to SQLite (`database/chatbot.db`):
- `conversations.condition`, `conversations.autonomy_level`
- `workflow_state.tool_name`, `.intervention_type`, `.source_selection`, `.autonomy_level`

`intervention_type` is the key behavioral DV:
- **V1 (finance):** `decide` (user chose) / `agent_decided` (auto) / `revise` / `confirm`; the chosen option id is in `.source_selection` (`1`/`2`/`3`/`custom`).
- **V-process (diet):** `approve` / `modify` / `interrupt` / `raise_autonomy` / `override`.

See [USER_DATA_GUIDE.md](USER_DATA_GUIDE.md) for how to inspect/export.

## More docs
- [FINANCE_STUDY_DESIGN.md](FINANCE_STUDY_DESIGN.md) — **V1** decisional-control design and what to fill in.
- [STUDY_DESIGN.md](STUDY_DESIGN.md) — V-process (diet) condition logic and control levers.
- [CHATBOT_README.md](CHATBOT_README.md) — architecture and API.
