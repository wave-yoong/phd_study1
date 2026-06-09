# phd_study1
Effect of User Control — **AI Diet-Planning Agent**

This repository contains a Flask web app for studying the **effect of user control over an AI agent**. Participants delegate a goal ("lose weight in 2 weeks") to an AI agent that **plans diet, exercise, and daily routine on their behalf** by running a pipeline of simulated tools.

## Scenario (shown to participants)

> 당신은 2주 뒤 2kg 감량을 목표로 다이어트를 하고 있습니다. 당신의 AI 에이전트는 목표 체중을 위해 운동과 식단 계획을 대신 짜줍니다. AI 에이전트와 대화하면서 2주의 식단과 운동 및 일상을 계획해 주세요.

## Experimental conditions (between-subjects)

| Condition | URL | What the participant experiences |
|-----------|-----|----------------------------------|
| **control** (user-control group) | `/?group=control` | The agent runs each tool step, then **pauses** so the user can **approve / modify an item / interrupt-stop / raise autonomy**. |
| **auto** (no-control group) | `/?group=auto` | The agent runs the **whole pipeline autonomously**, makes proactive decisions, and just reports the finished plan. No control levers. |

Both conditions surface the agent's tool steps (calorie calculator → meal DB → workout planner → schedule builder → grocery list → plan compiler) as on-screen "agent action" cards. If `group` is omitted, the condition is **randomly assigned**.

## Quick Start

```bash
pip install -r requirements.txt

# Demo mode (mock agent, no API key needed)
./run.sh demo

# Production mode (real LLM via Azure/OpenAI creds in .env)
cp .env.example .env   # then add your key(s)
./run.sh
```

Open `http://localhost:5000` (add `?group=control` or `?group=auto` to force a condition).

## Data

Everything is logged to SQLite (`database/chatbot.db`):
- `conversations.condition`, `conversations.autonomy_level`
- `workflow_state.tool_name`, `.intervention_type` (`approve` / `modify` / `interrupt` / `raise_autonomy` / `override`), `.autonomy_level`

`intervention_type` is the key behavioral measure of how much the user steered the agent. See [USER_DATA_GUIDE.md](USER_DATA_GUIDE.md) for how to inspect/export.

## More docs
- [STUDY_DESIGN.md](STUDY_DESIGN.md) — condition logic, control levers, and **what the researcher still needs to fill in**.
- [CHATBOT_README.md](CHATBOT_README.md) — architecture and API.
