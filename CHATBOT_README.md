# AI Wellness Agent — Architecture

Flask app for PhD Study 1 (Effect of User Control). An AI **agent** designs a 2-week
wellness routine (diet + exercise + sleep/lifestyle) on the participant's behalf by
running a pipeline of simulated tools, with experimental conditions that vary how
much the user can control the agent. Weight loss is an *optional* health goal, not
the central objective.

## Agent pipeline

Intake is a sequential, clickable questionnaire (`intake_goal → intake_food →
intake_exercise → intake_sleep → intake_body`), then the agent advances through
ordered tool steps (`services/workflow_manager.py`):

```
intake* → calc → meal → workout → sleep → schedule → grocery → delivery → (delivered/closed)
```

| Phase | Simulated tool | Output |
|-------|----------------|--------|
| `intake*` | – | sequential Q&A: health goal, food prefs, day×time-slot availability, sleep habits, body info (optional) |
| `calc` | nutrition_guide | daily energy/calorie + macros + hydration (health-oriented; weight optional) |
| `meal` | meal_database | balanced meal composition + sample day |
| `workout` | workout_planner | 2-week workout principles + rest-day placement |
| `sleep` | sleep_planner | sleep schedule + sleep hygiene + daily habits |
| `schedule` | schedule_builder | day-by-day 14-day routine (diet/exercise/sleep) |
| `grocery` | grocery_generator | week-1 grocery list |
| `delivery` | plan_compiler | compiled final routine |

## Conditions & control flow

- **auto** (no control): after `intake`, the agent runs the entire pipeline in one
  turn (`_run_pipeline`) and reports the plan. Autonomy is always `high`.
- **control** (user control): after `intake`, the agent runs **one phase at a time**
  (`_run_single_phase`) and stops at a checkpoint. The user's next message is
  classified (`_classify_intent`) into:
  - `approve` → advance to next phase
  - `modify` → regenerate the current phase with the user's edit (item override)
  - `interrupt` → pause the agent (`paused`); user can resume or modify
  - `raise_autonomy` ("알아서 진행") → flip autonomy to `high` and finish the rest
    autonomously (this is the user-facing **autonomy dial**)

  After delivery, the control group can still **override items** (e.g. "3일차 저녁 …
  바꿔줘") or confirm to close.

## Files

```
backend/app.py              # Flask app: condition assignment, control buttons, JSON API
services/workflow_manager.py# Agent pipeline + condition / autonomy / interrupt logic
services/gpt_service.py     # Real LLM agent prompts (per phase, per condition)
services/mock_gpt_service.py# Mock agent for demo mode (no API key)
database/db_manager.py      # SQLite: conversations + messages + workflow_state
frontend/index.html         # Scenario intro, agent-action cards, control levers
```

## API

- `GET /` — agent UI
- `POST /api/start` — `{query, group?}` → assigns condition, runs `intake`. Returns
  `condition`, `stage`, `agent_actions`, `choices`, `conversation_id`.
- `POST /api/chat` — `{message}` → advances the agent. Returns `stage`,
  `agent_actions`, `choices`, `autonomy_level`.
- `GET /api/history` — messages + workflow_state for the session
- `POST /api/reset` — clears the session conversation
- `GET /health` — status + active model

`choices` are the control-group levers (approve / modify / autonomy / interrupt);
the auto group always receives an empty list.

## Service selection

`backend/app.py:_build_gpt_service()` picks, in order:
1. `USE_MOCK_GPT=1` → mock agent
2. `AZURE_OPENAI_ENDPOINT` set → Azure OpenAI
3. `OPENAI_API_KEY` set → OpenAI
4. otherwise → mock agent (so the app always boots)

## Data schema (key columns)

- `conversations`: `condition` (`control`/`auto`), `autonomy_level` (`low`/`high`)
- `messages`: `role`, `content`
- `workflow_state`: `stage`, `tool_name`, `intervention_type`, `autonomy_level`,
  `user_input`, `gpt_response`
