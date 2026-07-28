# V2 — Stock-Report Agent (Execution-Version Control)

This is **version 2** of the user-control agent, a **different kind of control**
from V1. Everyone does the *same* agentic task — the agent writes a report on
**2026 Q1 Korean domestic / overseas stock-market conditions** — but the
user-control group controls **which execution version the agent runs**.

This is the **Functional (information-seeking)** task of the planned
Social vs Functional split. Run it with `STUDY=stock` (the default).

---

## 1. Manipulation (implemented)

- **IV (between-subjects):** `condition` = `version` (user picks the execution
  version) vs `auto` (the agent picks for the user).
- **Control group (`version`):** the agent offers **3 versions**, each labelled
  with its trade-offs — **분량 (length) / 사용 모델 (model) / 소요 시간 (time)**:
  1. 빠른 요약본 — A4 ~1장 / 경량 모델 / ~20초
  2. 표준 분석본 — A4 ~2–3장 / 표준 모델 / ~1분 30초
  3. 실시간 심층본 — A4 ~3장+ / 고급 모델 + 실시간 조회 / ~3분
  The user selects one (shown as cards).
- **No-control group (`auto`):** the agent says *"제가 판단했을 때 가장 적절한
  버전으로 준비해드릴게요!"* and proceeds (it internally picks 표준 분석본).
- **Output held constant (critical):** whichever version is chosen — and in the
  `auto` group too — the participant receives the **exact same report**
  (`REPORT_TEXT` in `services/report_workflow_manager.py`). Only the *control
  experience* varies; the deliverable is a constant. Because of this the study
  uses **fixed strings, no LLM**, so the report can never drift between
  participants.
- **Behavioural DV logged:**
  - `intervention_type = 'select_version'` (user chose) vs `'agent_selected'`
    (auto), `'confirm'` (accepted).
  - `source_selection` = the chosen version id (`1`/`2`/`3`).

Only the intro line differs by choice (it echoes the picked version's model/time);
the report body is identical. Assign via URL (`/?group=version`, `/?group=auto`).

---

## 2. What you still need to provide

- **A. Report content.** `REPORT_TEXT` is a fixed illustrative report with a
  footer noting the figures are simulated for research. Replace it with your
  finalized 2026 Q1 content, or remove/keep the disclaimer per your IRB.
- **B. Version attributes.** Length / model / time labels live in
  `StockReportWorkflowManager.VERSIONS`. Tune the trade-offs (and how many
  versions: 2 vs 3) there. Keep them plausible and mutually distinct.
- **C. The agent's auto choice.** `AUTO_CHOICE` (default `'2'`, 표준 분석본) is the
  version the no-control agent claims to pick. Change if a different default fits.
- **D. (Optional) simulated wait.** Right now the stated 소요 시간 is described but
  not enforced (no real delay), to avoid making participants wait minutes. If you
  want the time cost to be *felt* (e.g., a few seconds proportional to the chosen
  version), ask and I'll add an artificial delay + progress UI.
- **E. Outcome measures (surveys).** The app logs behaviour (which version,
  revisions), not self-report DVs (perceived control, autonomy, satisfaction with
  the report, trust, decision confidence). Administer externally (Qualtrics) or
  ask to add an in-app questionnaire + `survey_responses` table.
- **F. Participant ID / assignment policy.** Same as the other studies — tell me
  your id scheme / block design if needed.

---

## 3. Notes & limitations

- The manipulation is deliberately "cosmetic" on the output: since the report is
  constant, any effect is attributable to the *control experience*, not report
  quality. That is the design intent — keep the output constant when piloting.
- The **Social (communication)** counterpart task is not built yet. The plan is
  the same manipulation (choose among execution versions with trade-offs) applied
  to a communication task; tell me the task and I'll add it as another study.

---

## 4. Fastest path to a runnable pilot

1. `./run.sh demo` (stock is the default study).
2. Open `/?group=version` and `/?group=auto`, walk both flows — confirm the
   report body is identical.
3. Finalize the report (§2A) and version labels (§2B).
4. Wire your survey (§2E).
5. Pilot, then `python view_user_data.py stats` to confirm `select_version` +
   `source_selection` populate in `version` and `agent_selected` in `auto`.
