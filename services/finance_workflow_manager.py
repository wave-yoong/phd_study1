from typing import Dict, Any, List, Optional
from database.db_manager import DBManager


class FinanceWorkflowManager:
    """
    Drives the personal-finance ALLOCATION agent for PhD Study 1, V1
    (Effect of User Control — DECISIONAL control, "deciding WHAT to do").

    The agent transparently analyses the participant's finances and, at each
    decision point, presents a small set of concrete options together with their
    trade-offs and risks. The manipulation is who makes the call:

      - 'decision' : the user-control (decisional) group. At every decision point
                     the agent stops and the USER chooses which option to take.
                     The chosen option is the key behavioural DV.
      - 'auto'     : the no-control group. The agent decides the allocation itself
                     and simply reports it. Transparency (the agent's reasoning) is
                     held constant across both groups — only *who decides* varies.

    Note on transparency: both conditions surface the agent's reasoning/trade-offs.
    Only the 'decision' group actually hands the choice to the user, which is what
    isolates decisional control from mere explanation.
    """

    # Ordered pipeline. 'diagnose' and 'compile' are analysis/summary steps;
    # the three in between are the user's decision points.
    PIPELINE = ['diagnose', 'allocate', 'emergency', 'invest', 'compile']
    DECISION_POINTS = ['allocate', 'emergency', 'invest']

    TOOL_META = {
        'diagnose': {'tool': 'finance_diagnoser', 'label': '재무 상황 진단기'},
        'allocate': {'tool': 'allocation_generator', 'label': '여윳돈 배분안 생성기'},
        'emergency': {'tool': 'emergency_fund_planner', 'label': '비상금 설계기'},
        'invest': {'tool': 'investment_analyzer', 'label': '투자 옵션 분석기'},
        'compile': {'tool': 'plan_compiler', 'label': '계획 통합기'},
    }

    STAGE_DESCRIPTIONS = {
        'intake': '목표 확인 및 재무 정보 수집',
        'allocate': '여윳돈 배분 방식 결정 중',
        'emergency': '비상금 목표 규모 결정 중',
        'invest': '투자 성향 결정 중',
        'delivered': '자산 배분 계획 전달 완료',
        'closed': '대화 종료',
    }

    # Option definitions for each decision point. The workflow owns the stable
    # option ids/labels (so choices stay deterministic across participants and
    # across mock/LLM modes); the GPT service owns the transparent prose that
    # explains each option. `value` is the message sent back when a user clicks.
    DECISION_OPTIONS: Dict[str, List[Dict[str, str]]] = {
        'allocate': [
            {'id': '1', 'label': '부채 우선 상환형 (부채 70 / 비상금 30 / 투자 0)',
             'value': '1번 부채 우선 상환형으로 결정할게'},
            {'id': '2', 'label': '균형형 (부채 40 / 비상금 30 / 투자 30)',
             'value': '2번 균형형으로 결정할게'},
            {'id': '3', 'label': '투자 우선형 (부채 20 / 비상금 20 / 투자 60)',
             'value': '3번 투자 우선형으로 결정할게'},
        ],
        'emergency': [
            {'id': '1', 'label': '탄탄하게 — 6개월치 (약 1,200만원)',
             'value': '1번 6개월치 비상금으로 결정할게'},
            {'id': '2', 'label': '적정 — 3개월치 (약 600만원)',
             'value': '2번 3개월치 비상금으로 결정할게'},
            {'id': '3', 'label': '최소 — 1개월치 (약 200만원)',
             'value': '3번 1개월치 비상금으로 결정할게'},
        ],
        'invest': [
            {'id': '1', 'label': '안정형 — 예금·국채 (연 3~4%, 저변동성)',
             'value': '1번 안정형으로 결정할게'},
            {'id': '2', 'label': '중립형 — 인덱스 ETF (장기 연 6~8% 기대, 중변동성)',
             'value': '2번 중립형으로 결정할게'},
            {'id': '3', 'label': '공격형 — 성장주·테마 (기대수익·손실 모두 큼)',
             'value': '3번 공격형으로 결정할게'},
        ],
    }

    def __init__(self, gpt_service, db_manager: DBManager):
        self.gpt_service = gpt_service
        self.db_manager = db_manager

    # ------------------------------------------------------------------ #
    # Entry points
    # ------------------------------------------------------------------ #
    def start_workflow(self, conversation_id: int, user_query: str) -> Dict[str, Any]:
        return self.process_message(conversation_id, user_query)

    def process_message(self, conversation_id: int, user_message: str) -> Dict[str, Any]:
        self.db_manager.add_message(conversation_id, 'user', user_message)

        conv = self.db_manager.get_conversation(conversation_id) or {}
        condition = conv.get('condition', 'decision')
        if condition not in ('decision', 'auto'):
            condition = 'decision'

        latest = self.db_manager.get_latest_workflow_state(conversation_id)
        stage = latest.get('stage') if latest else None

        # 1) First message = the finance goal -> run intake (collect constraints).
        if stage is None:
            return self._run_intake(conversation_id, condition, user_message)

        # 2) Constraints answered -> diagnose, then either hand over the first
        #    decision (decision group) or run everything autonomously (auto group).
        if stage == 'intake':
            if condition == 'auto':
                return self._run_auto_pipeline(conversation_id, user_message)
            return self._present_decision(conversation_id, condition, 'allocate',
                                          user_message, run_diagnose=True)

        # 3) At a decision point (decision group) -> record the choice, advance.
        if stage in self.DECISION_POINTS:
            return self._handle_decision(conversation_id, condition, stage, user_message)

        # 4) Final plan already delivered -> revise a decision / close.
        if stage in ('delivered', 'closed'):
            return self._handle_post_plan(conversation_id, condition, user_message)

        # Fallback: restart intake.
        return self._run_intake(conversation_id, condition, user_message)

    # ------------------------------------------------------------------ #
    # Phase runners
    # ------------------------------------------------------------------ #
    def _run_intake(self, conversation_id: int, condition: str, user_message: str) -> Dict[str, Any]:
        history = self.db_manager.get_conversation_messages(conversation_id)
        response = self.gpt_service.generate_agent_response(
            condition=condition, phase='intake', user_message=user_message,
            conversation_history=history
        )
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='intake',
            user_input=user_message, gpt_response=response
        )
        return self._result(response, 'intake', condition, agent_actions=[], choices=[])

    def _present_decision(
        self, conversation_id: int, condition: str, phase: str,
        user_message: str, run_diagnose: bool = False
    ) -> Dict[str, Any]:
        """Show the agent's analysis for `phase` and hand the choice to the user."""
        history = self.db_manager.get_conversation_messages(conversation_id)

        actions: List[Dict[str, str]] = []
        parts: List[str] = []

        # The very first decision is preceded by the transparent diagnosis step.
        if run_diagnose:
            diag = self.gpt_service.generate_agent_response(
                condition=condition, phase='diagnose', user_message=user_message,
                conversation_history=history
            )
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='diagnose',
                user_input=user_message, gpt_response=diag,
                tool_name=self.TOOL_META['diagnose']['tool']
            )
            actions.append(self._action_card('diagnose'))
            parts.append(diag)
            history = history + [{'role': 'assistant', 'content': diag}]

        options_text = self.gpt_service.generate_agent_response(
            condition=condition, phase=phase, user_message=user_message,
            conversation_history=history
        )
        actions.append(self._action_card(phase))
        parts.append(options_text)

        response = "\n\n".join(parts)
        self.db_manager.add_message(conversation_id, 'assistant', response)
        # Log that we are now awaiting the user's decision at this point.
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage=phase,
            gpt_response=options_text, tool_name=self.TOOL_META[phase]['tool']
        )
        return self._result(response, phase, condition, agent_actions=actions,
                            choices=self._decision_choices(phase))

    def _handle_decision(
        self, conversation_id: int, condition: str, stage: str, user_message: str
    ) -> Dict[str, Any]:
        """Record the user's choice at `stage`, then move to the next decision/plan."""
        chosen_id, chosen_label = self._classify_choice(stage, user_message)

        # Persist the decision as the behavioural DV.
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage=stage,
            user_input=user_message,
            source_selection=chosen_id,
            tool_name=self.TOOL_META[stage]['tool'],
            intervention_type='decide'
        )

        next_phase = self._next_decision(stage)
        if next_phase is not None:
            return self._present_decision(conversation_id, condition, next_phase, user_message)

        # No more decisions -> compile the final plan from the user's choices.
        return self._compile_plan(conversation_id, condition, user_message)

    def _compile_plan(self, conversation_id: int, condition: str, user_message: str) -> Dict[str, Any]:
        history = self.db_manager.get_conversation_messages(conversation_id)
        response = self.gpt_service.generate_agent_response(
            condition=condition, phase='compile', user_message=user_message,
            conversation_history=history
        )
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='delivered',
            gpt_response=response, tool_name=self.TOOL_META['compile']['tool']
        )
        return self._result(response, 'delivered', condition,
                            agent_actions=[self._action_card('compile')], choices=[])

    def _run_auto_pipeline(self, conversation_id: int, user_message: str) -> Dict[str, Any]:
        """Autonomous group: the agent decides every allocation itself and reports."""
        history = self.db_manager.get_conversation_messages(conversation_id)
        working_history = list(history)
        actions: List[Dict[str, str]] = []
        parts: List[str] = []

        for phase in self.PIPELINE:
            text = self.gpt_service.generate_agent_response(
                condition='auto', phase=phase, user_message=user_message,
                conversation_history=working_history
            )
            meta = self.TOOL_META[phase]
            log_stage = 'delivered' if phase == 'compile' else phase
            # In auto, the agent makes each decision itself; record it as an
            # agent decision (no user intervention) for symmetry with the DV.
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage=log_stage,
                user_input=user_message if phase == 'diagnose' else None,
                gpt_response=text, tool_name=meta['tool'],
                intervention_type='agent_decided' if phase in self.DECISION_POINTS else None
            )
            working_history.append({'role': 'assistant', 'content': text})
            actions.append(self._action_card(phase))
            parts.append(f"[{meta['label']}]\n{text}")

        combined = "\n\n".join(parts) + "\n\n배분 계획을 모두 확정했습니다. 그대로 진행하시면 됩니다."
        self.db_manager.add_message(conversation_id, 'assistant', combined)
        return self._result(combined, 'delivered', 'auto', agent_actions=actions, choices=[])

    def _handle_post_plan(self, conversation_id: int, condition: str, user_message: str) -> Dict[str, Any]:
        # Autonomous condition: plan is final, no steering offered.
        if condition == 'auto':
            response = "이 배분 계획은 이미 확정된 최종안입니다. 그대로 진행해 주세요."
            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='delivered',
                user_input=user_message, gpt_response=response
            )
            return self._result(response, 'delivered', 'auto', agent_actions=[], choices=[])

        # Decision condition: let the user re-open and change a past decision.
        target = self._match_revise_target(user_message)
        if target is not None:
            return self._present_decision(conversation_id, condition, target, user_message)

        if self._is_close(user_message):
            response = "좋습니다. 결정하신 배분 계획을 그대로 진행하세요. 바꾸고 싶은 결정이 생기면 언제든 말씀해 주세요."
            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='closed',
                user_input=user_message, gpt_response=response, intervention_type='confirm'
            )
            return self._result(response, 'closed', condition, agent_actions=[], choices=[])

        # Otherwise, treat free text as a revision request handled by the agent.
        history = self.db_manager.get_conversation_messages(conversation_id)
        response = self.gpt_service.generate_agent_response(
            condition=condition, phase='revise', user_message=user_message,
            conversation_history=history, override_instruction=user_message
        )
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='delivered',
            user_input=user_message, gpt_response=response,
            tool_name=self.TOOL_META['compile']['tool'], intervention_type='revise'
        )
        return self._result(response, 'delivered', condition,
                            agent_actions=[self._action_card('compile', label='계획 수정')],
                            choices=self._post_plan_choices())

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _next_decision(self, phase: str) -> Optional[str]:
        idx = self.DECISION_POINTS.index(phase)
        return self.DECISION_POINTS[idx + 1] if idx + 1 < len(self.DECISION_POINTS) else None

    def _action_card(self, phase: str, label: Optional[str] = None) -> Dict[str, str]:
        meta = self.TOOL_META[phase]
        return {'tool': meta['tool'], 'label': label or meta['label'], 'status': '실행 완료'}

    def _decision_choices(self, phase: str) -> List[Dict[str, str]]:
        """Options the user chooses among + an 'other' entry for a custom decision."""
        options = [dict(o) for o in self.DECISION_OPTIONS[phase]]
        options.append({'id': 'other', 'label': '직접 정하기 (직접 입력)', 'value': ''})
        return options

    def _post_plan_choices(self) -> List[Dict[str, str]]:
        return [
            {'id': 'revise_allocate', 'label': '배분 방식 다시 결정', 'value': '배분 방식을 다시 정하고 싶어'},
            {'id': 'revise_emergency', 'label': '비상금 규모 다시 결정', 'value': '비상금 규모를 다시 정하고 싶어'},
            {'id': 'revise_invest', 'label': '투자 성향 다시 결정', 'value': '투자 성향을 다시 정하고 싶어'},
            {'id': 'done', 'label': '이대로 확정', 'value': '이대로 확정할게'},
        ]

    def _classify_choice(self, stage: str, user_message: str) -> (str, str):
        """Map a decision-group message to one of the stage's option ids."""
        msg = user_message.strip().lower()
        options = self.DECISION_OPTIONS[stage]

        # 1) Explicit option number (1/2/3, with or without '번').
        for opt in options:
            oid = opt['id']
            if oid in msg or f"{oid}번" in msg:
                return oid, opt['label']

        # 2) Keyword match against option labels.
        keyword_map = {
            'allocate': {'1': ['부채', '상환'], '2': ['균형'], '3': ['투자 우선', '공격', '투자우선']},
            'emergency': {'1': ['6개월', '탄탄'], '2': ['3개월', '적정'], '3': ['1개월', '최소']},
            'invest': {'1': ['안정', '예금', '국채'], '2': ['중립', '인덱스', 'etf'], '3': ['공격', '성장', '테마']},
        }
        for oid, kws in keyword_map.get(stage, {}).items():
            if any(k in msg for k in kws):
                label = next((o['label'] for o in options if o['id'] == oid), oid)
                return oid, label

        # 3) Unmatched -> a custom, user-defined decision (still decisional control).
        return 'custom', user_message.strip()

    def _match_revise_target(self, user_message: str) -> Optional[str]:
        msg = user_message.strip().lower()
        if any(k in msg for k in ['배분', '비율']):
            return 'allocate'
        if '비상금' in msg:
            return 'emergency'
        if any(k in msg for k in ['투자', '성향']):
            return 'invest'
        return None

    def _is_close(self, user_message: str) -> bool:
        msg = user_message.strip().lower()
        return any(k in msg for k in ['확정', '이대로', '좋아', '완료', '끝', 'ok', 'okay', '없어'])

    def _result(
        self, response: str, stage: str, condition: str,
        agent_actions: List[Dict[str, str]], choices: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        return {
            'response': response,
            'stage': stage,
            'stage_description': self.STAGE_DESCRIPTIONS.get(stage, '진행 중'),
            'condition': condition,
            'agent_actions': agent_actions,
            'choices': choices,
            'awaiting_input': stage != 'closed',
        }
