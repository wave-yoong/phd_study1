# V1 — Finance Allocation Agent (Decisional Control)

This is **version 1** of the user-control agent: the user is granted control over
**"deciding WHAT to do."** The domain is **personal-finance allocation**, chosen
because the trade-offs depend on the user's values and the agent's transparency
directly informs the choice.

Run it with `STUDY=finance` (the default). The earlier diet agent (V-process,
"deciding HOW it's done") still runs with `STUDY=diet`.

---

## 1. Manipulation (implemented)

- **IV (between-subjects):** `condition` = `decision` (user chooses at each
  decision point) vs `auto` (agent decides and reports).
- **Held constant across conditions:** the agent's **transparency** — both groups
  see the same analysis, options, trade-offs and risks. Only *who makes the call*
  differs. This isolates **decisional control** from mere explanation.
- **Three decision points** where the user decides "what to do":
  1. `allocate` — how to split the monthly surplus (부채 우선 / 균형 / 투자 우선)
  2. `emergency` — emergency-fund target (6개월치 / 3개월치 / 1개월치)
  3. `invest` — investment stance (안정형 / 중립형 / 공격형)
- **Behavioural DV logged per decision:**
  - `workflow_state.intervention_type = 'decide'` (user made the call) vs
    `'agent_decided'` (auto group), `'revise'` (changed a past decision),
    `'confirm'` (accepted the plan).
  - `workflow_state.source_selection` = the option id the user chose (`1`/`2`/`3`,
    or `custom` for a free-text decision).

Assign condition via URL (`/?group=decision`, `/?group=auto`) or let it randomize.

---

## 2. What you still need to provide

### A. Fixed vs LLM content
The mock agent (`services/finance_mock_service.py`) uses **fixed, deterministic**
numbers (월 여윳돈 100만원, 부채 1,200만원·7%, 세 옵션의 문구). For a clean
experiment where only *control* varies, run demo mode (`USE_MOCK_GPT=1`) so the
options and reasoning are identical across participants. Edit the per-phase strings
there to finalize wording. Mirror any change in `services/finance_gpt_service.py`
(`PHASE_INSTRUCTIONS`) if you also run the live LLM.

### B. Option sets (if you want different choices)
The stable, clickable options live in `FinanceWorkflowManager.DECISION_OPTIONS`
(ids/labels/values) so they stay identical regardless of LLM wording. Change them
there; keep the prose in the service in sync.

### C. Scenario numbers / framing
Scenario text is in `backend/app.py` → `STUDY_CONFIG['finance']['scenario']`.
Decide the surplus amount, debt/rate, and any framing needed for IRB (e.g. "이건
가상의 상황입니다, 실제 투자 권유가 아닙니다"). The agent already avoids naming
specific securities or promising returns.

### D. Outcome measures (surveys) — not in the app
The app logs **behaviour** (which option chosen, revisions). It does **not** collect
self-report DVs (perceived control, autonomy, decision satisfaction, trust,
perceived competence, decision confidence, regret). Administer these externally
(Qualtrics, recommended) or ask to add an in-app questionnaire + `survey_responses`
table.

### E. Participant ID / session linking
`conversations` has no participant id yet. Tell me your scheme (e.g.
`/?pid=123&group=decision`) to persist it for joining logs to survey data.

### F. Random assignment policy
Default: 50/50 per session if `group` is absent. Ask for balanced blocks / fixed
lists if needed.

---

## 3. Known limitations

- The plan is a **planning interaction**, not tracked real-world outcomes — target
  your DVs at the *decision experience*, not actual financial results.
- `custom` decisions (free-text at a decision point) are logged as `source_selection
  = 'custom'` with the text in `user_input`; code them by hand if you need finer
  categories.
- The auto group's chosen defaults (균형형 / 3개월치 / 인덱스 ETF in the mock) are a
  design choice — change them in the mock if a different "reasonable agent default"
  better matches your framing.

---

## 4. Fastest path to a runnable pilot

1. `./run.sh demo` (finance is the default study).
2. Open `/?group=decision` and `/?group=auto`, walk both flows.
3. Finalize wording/numbers (A–C above).
4. Wire your survey (D) and IDs (E).
5. Pilot 3–5 per cell, then `python view_user_data.py stats` to confirm
   `intervention_type='decide'` + `source_selection` populate in `decision` and
   that `auto` logs `agent_decided`.
