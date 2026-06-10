# phd_study1
Effect of User Control — **AI Wellness Agent**

This repository contains a Flask web app for studying the **effect of user control over an AI agent**. Participants delegate a goal ("build a healthier 2-week routine") to an AI agent that **designs a diet + exercise + sleep/lifestyle routine on their behalf** by running a pipeline of simulated tools. Weight loss is treated as an *optional* health goal, not the central objective.

## Scenario (shown to participants)

> 당신은 앞으로 2주간 더 건강한 생활 루틴을 만들고 싶어 합니다. 당신의 AI 웰니스 에이전트는 식단·운동·수면과 일상 습관을 포함한 2주 루틴을 대신 설계해 줍니다. 체중 감량 같은 특정 목표가 있다면 선택적으로 반영할 수 있습니다. AI 에이전트와 대화하면서 2주간의 건강 루틴을 함께 계획해 주세요.

이 시나리오 문구는 `frontend/index.html`의 시나리오 박스와 동일하게 유지됩니다.

## Experimental conditions (between-subjects)

| Condition | URL | What the participant experiences |
|-----------|-----|----------------------------------|
| **control** (user-control group) | `/?group=control` | The agent runs each tool step, then **pauses** so the user can **approve / modify an item / interrupt-stop / raise autonomy**. |
| **auto** (no-control group) | `/?group=auto` | The agent runs the **whole pipeline autonomously**, makes proactive decisions, and just reports the finished plan. No control levers. |

Both conditions surface the agent's tool steps (nutrition guide → meal DB → workout planner → sleep/lifestyle planner → schedule builder → grocery list → plan compiler) as on-screen animated "agent step" cards revealed one at a time. If `group` is omitted, the condition is **randomly assigned**.

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
