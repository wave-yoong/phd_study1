# V1 — Hiring-Decision Agent (Decisional Control)

This is the active **version 1** of the user-control agent: the user is granted
control over **"deciding WHAT to do."** The domain is **hiring** — the participant
is a hiring manager, an AI recruiting agent analyses applicants transparently, and
the participant makes each call by picking from **selectable option cards**.

Run it with `STUDY=hiring` (the default). Earlier drafts still run with
`STUDY=finance` (finance allocation, also decisional) and `STUDY=diet` (process
control).

---

## 1. Manipulation (implemented)

- **IV (between-subjects):** `condition` = `decision` (user chooses at each
  decision point) vs `auto` (agent decides and reports).
- **Held constant across conditions:** the agent's **transparency** — both groups
  see the same applicant analysis, options, trade-offs, risks, and the agent's
  **stated uncertainty about its own assessment** (subjective interviews, small
  sample, prediction limits). Only *who makes the call* differs. This isolates
  **decisional control** from mere explanation.
- **Three decision points** where the user decides "what to do", each shown as
  cards:
  1. `criteria` — what to prioritize (실무 즉시전력 / 성장 잠재력 / 조직 적합성).
     The agent shows that the top candidate literally changes with this choice.
  2. `verify` — what to check before deciding (레퍼런스 체크 / 추가 과제 / 바로 결정).
     Directly engages trust in the AI's read.
  3. `finalize` — which of 4 candidates to hire (A 김서연 / B 이준호 / C 박민지 / D 최지훈).
- **Behavioural DV logged per decision:**
  - `workflow_state.intervention_type = 'decide'` (user chose) vs `'agent_decided'`
    (auto), `'revise'` (changed a past decision), `'confirm'` (accepted).
  - `workflow_state.source_selection` = the chosen option id (`1`/`2`/`3` for
    criteria & verify; `A`/`B`/`C`/`D` for the hire; `custom` for a free-text call).

Assign condition via URL (`/?group=decision`, `/?group=auto`) or let it randomize.

---

## 2. The four candidates (fixed)

Deterministic, value-laden trade-offs so no option is objectively "correct":

- **A · 김서연** — 실무 즉시전력 (인턴 2회, 캠페인 경험) / 우려: 잦은 이직.
- **B · 이준호** — 성장 잠재력 (과제 창의성 1위) / 우려: 실무 미검증.
- **C · 박민지** — 조직 적합성 (소통·협업, 면접 호감) / 우려: 평범한 전문성.
- **D · 최지훈** — 데이터 분석 (분석력·자격증) / 우려: 약한 크리에이티브.

Edit them (and the option cards) in `HiringWorkflowManager.DECISION_OPTIONS`; keep
the prose in `services/hiring_mock_service.py` (demo) and
`services/hiring_gpt_service.py` (`AGENT_PERSONA` / `PHASE_INSTRUCTIONS`) in sync.

---

## 3. What you still need to provide

- **A. Fixed vs LLM content.** For a clean experiment run demo mode
  (`USE_MOCK_GPT=1`) so cards + reasoning are identical across participants.
  Finalize wording in the mock; mirror in the GPT service if you also run live.
- **B. Scenario/IRB framing.** Scenario text is in `backend/app.py` →
  `STUDY_CONFIG['hiring']['scenario']`. Add any framing you need (e.g. "가상의
  지원자입니다"). The agent already avoids job-irrelevant attributes and states its
  own uncertainty.
- **C. Outcome measures (surveys).** The app logs **behaviour** (which option
  chosen, revisions), not self-report DVs (perceived control, autonomy, decision
  confidence, satisfaction, trust, responsibility/accountability, regret).
  Administer externally (Qualtrics, recommended) or ask to add an in-app
  questionnaire + `survey_responses` table.
- **D. Participant ID / session linking.** `conversations` has no participant id
  yet. Tell me your scheme (e.g. `/?pid=123&group=decision`).
- **E. Random assignment policy.** Default 50/50 per session if `group` is absent.

---

## 4. Known limitations

- The `auto` group's chosen defaults (criteria 1 / reference check / candidate A)
  are a design choice — change them in the mock if a different "reasonable agent
  default" better matches your framing.
- `custom` decisions (free text at a decision point) are logged as
  `source_selection='custom'` with the text in `user_input`; hand-code if needed.
- `verify` is logged but does not currently branch the later information shown
  (e.g. a reference note). Ask if you want the verification choice to reveal extra
  transparent info before `finalize`.
- This is a **planning/decision interaction**, not a real hire — target DVs at the
  decision experience.

---

## 5. Fastest path to a runnable pilot

1. `./run.sh demo` (hiring is the default study).
2. Open `/?group=decision` and `/?group=auto`, walk both flows.
3. Finalize candidates/cards/wording (§2, §3A–B).
4. Wire your survey (§3C) and IDs (§3D).
5. Pilot 3–5 per cell, then `python view_user_data.py stats` to confirm
   `intervention_type='decide'` + `source_selection` populate in `decision`, and
   that `auto` logs `agent_decided`.
