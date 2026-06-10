# Study Design Notes & What the Researcher Must Provide

This file is the bridge between the running code and your experimental protocol.
The code gives you a working **agentic** wellness planner (diet + exercise +
sleep/lifestyle; weight loss optional) with a between-subjects
**user-control manipulation**. The items below are decisions/content that only you
(the researcher) can finalize. Each points to exactly where to plug it in.

---

## 1. Manipulation summary (already implemented)

- **IV (between-subjects):** `condition` = `control` (user can steer the agent) vs
  `auto` (agent acts autonomously, user cannot steer).
- **Agentic behavior (both groups):** simulated tool steps are shown as "agent
  action" cards; the agent makes proactive decisions (e.g. rest-day placement).
- **Control levers (control group only):** approve / modify item / interrupt-stop /
  raise autonomy ("알아서 진행") + post-delivery item override.
- **Behavioral DV logged:** `workflow_state.intervention_type` per step.

Assign condition via URL (`/?group=control`, `/?group=auto`) or let it randomize.

---

## 2. What you still need to provide

### A. Goal framing & safety  ⚠️ important
The scenario is now a **general wellness routine** (diet + exercise + sleep),
with **weight loss as an optional health goal** rather than the central target.
This deliberately removes the earlier "lose Nkg in 2 weeks" framing, which was
medically aggressive and risked becoming a **confound** (distrust of advice
unrelated to control). Still confirm:
- That the wellness framing fits your hypothesis (you measure control, not advice
  credibility).
- The `intake_goal` options (one of which is "체중 감량 (선택)") — keep, reword, or
  make multi-select.
- Final safety/disclaimer wording for IRB.

The goal string lives in `services/workflow_manager.py` → `GOAL`; intake questions
and options are in `INTAKE_STEPS` (same file); the scenario box copy is in
`frontend/index.html`.

Where to edit:
- Scenario text: `frontend/index.html` (the `.scenario-box` block).
- Agent's safety stance: `services/gpt_service.py` → `AGENT_PERSONA` (의학적 안전 line)
  and the mock copy in `services/mock_gpt_service.py`.

### B. Exact condition wording / tone
The difference between groups is currently carried by `CONDITION_MODIFIERS` in
`services/gpt_service.py`. If your manipulation needs specific phrasing (e.g. the
auto agent must *never* ask anything; the control agent must explicitly say "당신이
결정하세요"), tighten those two strings. Mirror any change in
`services/mock_gpt_service.py` so demo mode matches.

### C. Domain content you want pinned (optional but recommended)
The mock agent uses placeholder numbers (1,500 kcal, sample meals, week-1 grocery
list). If you want **identical, controlled content across participants** (so the
plan is constant and only *control* varies), replace the per-phase strings in
`services/mock_gpt_service.py` and run in demo mode (`USE_MOCK_GPT=1`). This is the
safest setup for a clean experiment — the LLM's variability is removed.

Provide, per phase, the exact text you want:
- calorie target & macros, meal options/menus, workout split & rest days,
  the 14-day schedule, and the grocery list.

### D. Intake questions
Default intake asks: food prefs/allergies, available workout days/time, optional
height/weight. Edit the `intake` prompt in `services/gpt_service.py` and the mock
in `services/mock_gpt_service.py` if you want fixed fields (or to collect a
participant ID).

### E. Outcome measures (surveys) — not in the app yet
The app logs **behavior** (interventions, autonomy changes) but does **not** collect
self-report DVs (perceived control, autonomy, trust, satisfaction, perceived agent
competence, etc.). Decide how you administer these:
- External survey (Qualtrics) linked after the session — simplest, **recommended**, or
- Ask me to add an in-app post-task questionnaire + a `survey_responses` table.

Provide: the scale items and when they're shown (pre/post).

### F. Participant ID / session linking
Currently a conversation row has no participant identifier. If you need to join
chat logs to survey data, tell me your ID scheme (URL param like
`/?pid=123&group=control`?) and I'll persist it on `conversations`.

### G. Random assignment policy
Default: 50/50 random per session if `group` is absent. If you want balanced
blocks, a fixed list, or assignment by participant ID, specify it.

### H. LLM vs fixed content for the live study
- Demo/mock mode = deterministic, no API, fully controlled content (good for the
  experiment).
- Real LLM mode = natural but variable. If you use it, provide Azure/OpenAI creds
  in `.env` (see `.env.example`) and decide a fixed `temperature`/model.

---

## 3. Known limitations to be aware of

- **"Real-time" interrupt is approximated.** Responses are synchronous (one request
  → one reply), so the control group's "중단" works at step checkpoints rather than
  literally mid-generation. If you need true streaming interruption, that's a larger
  change — tell me and I'll add SSE/streaming.
- **`_resume_target` (paused→resume) is in-process memory.** Fine for a single
  server process; if you deploy multi-worker, move it into `workflow_state`
  (quick change — ask).
- The 2-week plan is produced in one session; adherence over the real 2 weeks is not
  tracked. Make sure your DVs target the *planning interaction*, not actual outcomes.

---

## 4. Fastest path to a runnable pilot

1. `./run.sh demo`
2. Open `/?group=control` and `/?group=auto`, walk both flows.
3. Tweak items A–D above to match your protocol.
4. Wire your survey (E) and IDs (F).
5. Pilot 3–5 people per cell, then `python view_user_data.py stats` to sanity-check
   that `intervention_type` varies in `control` and is empty in `auto`.
