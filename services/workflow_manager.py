from typing import Dict, Any, List, Optional
from database.db_manager import DBManager


class WorkflowManager:
    """
    Drives the diet/exercise planning AGENT for PhD Study 1 (Effect of User Control).

    Both experimental conditions run the same agentic pipeline of simulated tools
    (calorie calculator -> meal DB -> workout planner -> schedule builder ->
    grocery list -> plan compiler) and surface those tool steps in the UI.

    Conditions:
      - 'auto'    : autonomous agent. Runs the whole pipeline, makes proactive
                    decisions and just reports the finished plan. No user control.
      - 'control' : user-control group. The agent pauses at each tool step and the
                    user can approve, modify a specific item, interrupt/stop, or
                    raise the agent's autonomy ('let it run'). These control actions
                    are logged as the key behavioral DV.
    """

    # Ordered pipeline of agentic tool steps.
    PIPELINE = ['calc', 'meal', 'workout', 'schedule', 'grocery', 'delivery']

    TOOL_META = {
        'calc': {'tool': 'calorie_calculator', 'label': '칼로리 계산기'},
        'meal': {'tool': 'meal_database', 'label': '식단 데이터베이스'},
        'workout': {'tool': 'workout_planner', 'label': '운동 루틴 설계기'},
        'schedule': {'tool': 'schedule_builder', 'label': '2주 일정 편성기'},
        'grocery': {'tool': 'grocery_generator', 'label': '장보기 리스트 생성기'},
        'delivery': {'tool': 'plan_compiler', 'label': '계획 통합'},
    }

    STAGE_DESCRIPTIONS = {
        'intake': '목표 확인 및 제약 수집',
        'calc': '칼로리/목표 산출 중',
        'meal': '식단 구성 중',
        'workout': '운동 루틴 설계 중',
        'schedule': '2주 일정 편성 중',
        'grocery': '장보기 리스트 생성 중',
        'delivered': '2주 계획 전달 완료',
        'paused': '사용자 개입으로 일시 중단',
        'closed': '대화 종료',
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
        condition = conv.get('condition', 'control')
        autonomy = conv.get('autonomy_level', 'low')
        if condition == 'auto':
            autonomy = 'high'

        latest = self.db_manager.get_latest_workflow_state(conversation_id)
        stage = latest.get('stage') if latest else None

        # 1) First message = the diet goal -> run intake (collect constraints).
        if stage is None:
            return self._run_intake(conversation_id, condition, user_message)

        # 2) Constraints answered -> launch the agentic pipeline.
        if stage == 'intake':
            if condition == 'auto' or autonomy == 'high':
                return self._run_pipeline(conversation_id, condition, 'calc', user_message, autonomy)
            return self._run_single_phase(conversation_id, condition, 'calc', user_message, autonomy)

        # 3) Final plan already delivered -> handle post-plan edits / closing.
        if stage in ('delivered', 'closed'):
            return self._handle_post_plan(conversation_id, condition, autonomy, user_message)

        # 4) Paused (control group interrupted) -> resume or accept new instruction.
        if stage == 'paused':
            return self._handle_paused(conversation_id, condition, autonomy, latest, user_message)

        # 5) At a pipeline checkpoint (control + low autonomy).
        if stage in self.PIPELINE:
            return self._handle_checkpoint(conversation_id, condition, autonomy, stage, user_message)

        # Fallback: restart intake.
        return self._run_intake(conversation_id, condition, user_message)

    # ------------------------------------------------------------------ #
    # Phase runners
    # ------------------------------------------------------------------ #
    def _run_intake(self, conversation_id: int, condition: str, user_message: str) -> Dict[str, Any]:
        history = self.db_manager.get_conversation_messages(conversation_id)
        response = self.gpt_service.generate_agent_response(
            condition=condition, phase='intake', user_message=user_message,
            conversation_history=history, autonomy_level='low'
        )
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='intake',
            user_input=user_message, gpt_response=response, autonomy_level='low'
        )
        return self._result(response, 'intake', condition, 'low', agent_actions=[], controls=False)

    def _run_single_phase(
        self, conversation_id: int, condition: str, phase: str,
        user_message: str, autonomy: str, intervention: Optional[str] = None,
        override_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run exactly one tool step and stop at a checkpoint (control, low autonomy)."""
        history = self.db_manager.get_conversation_messages(conversation_id)
        response = self.gpt_service.generate_agent_response(
            condition=condition, phase=phase, user_message=user_message,
            conversation_history=history, autonomy_level=autonomy,
            override_instruction=override_instruction
        )
        meta = self.TOOL_META[phase]
        is_last = (phase == 'delivery')
        # Persist the routing stage ('delivered'), not the pipeline phase name,
        # so the next user message is routed correctly (post-plan vs checkpoint).
        stage = 'delivered' if is_last else phase
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage=stage,
            user_input=user_message, gpt_response=response,
            tool_name=meta['tool'], intervention_type=intervention, autonomy_level=autonomy
        )
        actions = [self._action_card(phase)]
        controls = (condition == 'control') and not is_last
        return self._result(response, stage, condition, autonomy,
                            agent_actions=actions, controls=controls)

    def _run_pipeline(
        self, conversation_id: int, condition: str, start_phase: str,
        user_message: str, autonomy: str, intervention: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run all remaining tool steps end-to-end and deliver the plan (autonomous)."""
        start_idx = self.PIPELINE.index(start_phase)
        phases = self.PIPELINE[start_idx:]

        history = self.db_manager.get_conversation_messages(conversation_id)
        working_history = list(history)
        actions: List[Dict[str, str]] = []
        parts: List[str] = []

        for i, phase in enumerate(phases):
            text = self.gpt_service.generate_agent_response(
                condition=condition, phase=phase, user_message=user_message,
                conversation_history=working_history, autonomy_level='high'
            )
            meta = self.TOOL_META[phase]
            log_stage = 'delivered' if phase == 'delivery' else phase
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage=log_stage,
                user_input=user_message if i == 0 else None, gpt_response=text,
                tool_name=meta['tool'],
                intervention_type=intervention if i == 0 else None,
                autonomy_level='high'
            )
            working_history.append({'role': 'assistant', 'content': text})
            actions.append(self._action_card(phase))
            parts.append(f"[{meta['label']}]\n{text}")

        combined = "\n\n".join(parts)
        self.db_manager.add_message(conversation_id, 'assistant', combined)

        closing = ("\n\n계획을 모두 확정했습니다. 그대로 따라 주시면 됩니다."
                   if condition == 'auto'
                   else "\n\n계획이 완성됐습니다. 특정 항목을 바꾸고 싶으면 알려주세요.")
        combined_out = combined + closing

        return self._result(combined_out, 'delivered', condition, 'high',
                            agent_actions=actions, controls=False)

    # ------------------------------------------------------------------ #
    # Control-group interaction handlers
    # ------------------------------------------------------------------ #
    def _handle_checkpoint(
        self, conversation_id: int, condition: str, autonomy: str,
        stage: str, user_message: str
    ) -> Dict[str, Any]:
        intent = self._classify_intent(user_message)

        # Raise autonomy -> let the agent finish the rest by itself.
        if intent == 'raise_autonomy':
            self.db_manager.set_autonomy_level(conversation_id, 'high')
            next_phase = self._next_phase(stage)
            return self._run_pipeline(conversation_id, condition, next_phase,
                                      user_message, 'high', intervention='raise_autonomy')

        # Interrupt / stop the agent.
        if intent == 'interrupt':
            return self._pause(conversation_id, condition, stage, user_message)

        # Modify the current step.
        if intent == 'modify':
            return self._run_single_phase(
                conversation_id, condition, stage, user_message, 'low',
                intervention='modify', override_instruction=user_message
            )

        # Approve / continue -> advance to next pipeline step.
        next_phase = self._next_phase(stage)
        if next_phase is None:
            return self._handle_post_plan(conversation_id, condition, autonomy, user_message)
        return self._run_single_phase(
            conversation_id, condition, next_phase, user_message, 'low',
            intervention='approve'
        )

    def _pause(self, conversation_id: int, condition: str, stage: str, user_message: str) -> Dict[str, Any]:
        history = self.db_manager.get_conversation_messages(conversation_id)
        response = self.gpt_service.generate_agent_response(
            condition=condition, phase='interrupt', user_message=user_message,
            conversation_history=history, autonomy_level='low'
        )
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='paused',
            user_input=user_message, gpt_response=response,
            intervention_type='interrupt', autonomy_level='low'
        )
        # Remember where we paused so we can resume.
        self._resume_target[conversation_id] = stage
        return self._result(response, 'paused', condition, 'low',
                            agent_actions=[], controls=False, resumable=True)

    def _handle_paused(
        self, conversation_id: int, condition: str, autonomy: str,
        latest: Dict[str, Any], user_message: str
    ) -> Dict[str, Any]:
        intent = self._classify_intent(user_message)
        resume_from = self._resume_target.get(conversation_id)

        if intent in ('approve', 'raise_autonomy') and resume_from:
            next_phase = self._next_phase(resume_from) or resume_from
            if intent == 'raise_autonomy':
                self.db_manager.set_autonomy_level(conversation_id, 'high')
                return self._run_pipeline(conversation_id, condition, next_phase,
                                          user_message, 'high', intervention='raise_autonomy')
            return self._run_single_phase(conversation_id, condition, next_phase,
                                          user_message, 'low', intervention='approve')

        # Otherwise treat the message as a modification of the step we paused on.
        if resume_from:
            return self._run_single_phase(
                conversation_id, condition, resume_from, user_message, 'low',
                intervention='modify', override_instruction=user_message
            )
        return self._run_intake(conversation_id, condition, user_message)

    def _handle_post_plan(
        self, conversation_id: int, condition: str, autonomy: str, user_message: str
    ) -> Dict[str, Any]:
        # Autonomous condition: plan is final, no steering offered.
        if condition == 'auto':
            response = "이 계획은 이미 확정된 최종안입니다. 그대로 진행해 주세요."
            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='delivered',
                user_input=user_message, gpt_response=response, autonomy_level='high'
            )
            return self._result(response, 'delivered', condition, 'high',
                                agent_actions=[], controls=False)

        # Control condition: allow item overrides after delivery.
        intent = self._classify_intent(user_message)
        if intent == 'approve':
            response = "좋습니다. 2주 계획을 그대로 진행하세요. 도중에 바꾸고 싶은 게 생기면 언제든 말씀해 주세요."
            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='closed',
                user_input=user_message, gpt_response=response,
                intervention_type='approve', autonomy_level=autonomy
            )
            return self._result(response, 'closed', condition, autonomy,
                                agent_actions=[], controls=False)

        history = self.db_manager.get_conversation_messages(conversation_id)
        response = self.gpt_service.generate_agent_response(
            condition=condition, phase='override', user_message=user_message,
            conversation_history=history, autonomy_level=autonomy,
            override_instruction=user_message
        )
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='delivered',
            user_input=user_message, gpt_response=response,
            tool_name='plan_compiler', intervention_type='override', autonomy_level=autonomy
        )
        return self._result(response, 'delivered', condition, autonomy,
                            agent_actions=[self._action_card('delivery', label='계획 수정')],
                            controls=True, post_plan=True)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    # Per-process memory of where each conversation paused (best-effort).
    _resume_target: Dict[int, str] = {}

    def _next_phase(self, phase: str) -> Optional[str]:
        idx = self.PIPELINE.index(phase)
        return self.PIPELINE[idx + 1] if idx + 1 < len(self.PIPELINE) else None

    def _action_card(self, phase: str, label: Optional[str] = None) -> Dict[str, str]:
        meta = self.TOOL_META[phase]
        return {
            'tool': meta['tool'],
            'label': label or meta['label'],
            'status': '실행 완료',
        }

    def _classify_intent(self, user_message: str) -> str:
        """Classify a control-group user action at a checkpoint."""
        msg = user_message.strip().lower()

        raise_patterns = ['알아서', '자율', '끝까지', '한번에', '한 번에', '쭉', '전체 진행', '다 해줘', '다해줘', '바로 완성']
        if any(p in msg for p in raise_patterns):
            return 'raise_autonomy'

        stop_patterns = ['중단', '멈춰', '그만', '잠깐', '스톱', 'stop', '정지', '대기']
        if any(p in msg for p in stop_patterns):
            return 'interrupt'

        modify_patterns = ['바꿔', '바꿔줘', '수정', '변경', '대신', '말고', '빼', '제외', '추가', '넣어',
                            '다시', '아니', '싫', '교체', '별로', 'no', '일차', '요일']
        if any(p in msg for p in modify_patterns):
            return 'modify'

        approve_patterns = ['예', '네', '응', '좋아', '계속', '진행', '다음', '승인', '맞아', '동의', 'ok', 'okay', 'y', 'yes', '확인']
        if any(p in msg for p in approve_patterns):
            return 'approve'

        return 'modify'  # default: treat free-text feedback as a modification

    def _result(
        self, response: str, stage: str, condition: str, autonomy: str,
        agent_actions: List[Dict[str, str]], controls: bool,
        resumable: bool = False, post_plan: bool = False
    ) -> Dict[str, Any]:
        return {
            'response': response,
            'stage': stage,
            'stage_description': self.STAGE_DESCRIPTIONS.get(stage, '진행 중'),
            'condition': condition,
            'autonomy_level': autonomy,
            'agent_actions': agent_actions,
            'controls_enabled': controls,
            'resumable': resumable,
            'post_plan': post_plan,
            'awaiting_input': stage not in ('closed',),
        }
