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
    PIPELINE = ['calc', 'meal', 'workout', 'sleep', 'schedule', 'grocery', 'delivery']

    # Sequential intake: one question at a time, each with clickable options
    # plus a free-text "기타" choice. Deterministic (no LLM) so both conditions
    # see identical onboarding.
    GOAL = '2주간 건강한 생활 루틴(식단·운동·수면) 만들기'
    INTAKE_GREETING = (
        '안녕하세요! 2주간 건강한 생활 루틴을 함께 설계해 드릴게요.\n'
        '식단·운동·수면과 일상 습관을 두루 살펴볼 거예요. '
        '맞춤 설계를 위해 몇 가지만 순서대로 여쭤볼게요.'
    )
    # The goal question is always asked first; the answer selects a goal-specific
    # branch of follow-up questions (see FLOWS).
    GOAL_STEP = {
        'stage': 'intake_goal',
        'icon': 'goal',
        'question': '이번 2주에 가장 중요하게 생각하는 건강 목표는 무엇인가요?',
        'options': [
            {'id': 'goal_overall', 'label': '전반적인 컨디션·에너지 향상', 'value': '전반적인 컨디션과 에너지를 끌어올리고 싶어요'},
            {'id': 'goal_sleep', 'label': '수면의 질 개선', 'value': '수면의 질을 개선하고 싶어요'},
            {'id': 'goal_habit', 'label': '규칙적인 운동 습관 만들기', 'value': '규칙적인 운동 습관을 만들고 싶어요'},
            {'id': 'goal_diet', 'label': '식습관 개선', 'value': '식습관을 개선하고 싶어요'},
            {'id': 'goal_weight', 'label': '체중 감량', 'value': '체중 감량도 함께 고려하고 싶어요'},
            {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''},
        ],
    }

    # Pool of follow-up questions; FLOWS picks an ordered subset per goal.
    # Every flow still collects food + exercise + body so the pipeline has data.
    QUESTIONS = {
        'q_food': {
            'stage': 'q_food', 'icon': 'meal',
            'question': '식단을 살펴볼게요. 좋아하거나 피하고 싶은 음식, 알레르기가 있나요?',
            'options': [
                {'id': 'food_none', 'label': '특별히 가리는 것 없어요', 'value': '특별히 가리는 음식은 없어요'},
                {'id': 'food_meat', 'label': '육류를 선호해요', 'value': '육류를 선호해요'},
                {'id': 'food_fish', 'label': '생선·해산물을 선호해요', 'value': '생선과 해산물을 선호해요'},
                {'id': 'food_veg', 'label': '채식 위주로 할래요', 'value': '채식 위주로 하고 싶어요'},
                {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''},
            ],
        },
        'q_exercise': {
            'stage': 'q_exercise', 'icon': 'workout',
            'question': '운동은 언제 가능하세요? 가능한 요일을 고르고, 각 요일의 시간대를 선택해 주세요.',
            'widget': {'type': 'day_time', 'days': ['월', '화', '수', '목', '금', '토', '일'],
                       'slots': ['오전', '오후', '저녁']},
        },
        'q_sleep': {
            'stage': 'q_sleep', 'icon': 'sleep',
            'question': '평소 수면 습관은 어떤가요?',
            'options': [
                {'id': 'sleep_good', 'label': '규칙적이고 충분해요', 'value': '수면은 규칙적이고 충분한 편이에요'},
                {'id': 'sleep_late', 'label': '늦게 자는 편이에요', 'value': '늦게 자는 편이에요'},
                {'id': 'sleep_short', 'label': '수면이 부족하거나 얕아요', 'value': '수면이 부족하고 얕은 편이에요'},
                {'id': 'sleep_irregular', 'label': '취침 시간이 불규칙해요', 'value': '취침 시간이 불규칙해요'},
                {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''},
            ],
        },
        'q_body': {
            'stage': 'q_body', 'icon': 'body',
            'question': '더 정확한 계획을 위해 키와 몸무게를 알려주실 수 있나요? (선택)',
            'widget': {'type': 'body_metrics'},
        },
        # --- sleep goal ---
        'q_sleep_time': {
            'stage': 'q_sleep_time', 'icon': 'sleep',
            'question': '평소 몇 시에 자고 몇 시에 일어나세요?',
            'widget': {'type': 'sleep_time'},
        },
        'q_sleep_issue': {
            'stage': 'q_sleep_issue', 'icon': 'sleep',
            'question': '수면에서 가장 개선하고 싶은 점은 무엇인가요?',
            'options': [
                {'id': 'si_fall', 'label': '잠들기까지 오래 걸려요', 'value': '잠드는 데 오래 걸려요'},
                {'id': 'si_wake', 'label': '자다가 자주 깨요', 'value': '자다가 자주 깨요'},
                {'id': 'si_tired', 'label': '아침에 개운하지 않아요', 'value': '아침에 일어나도 피곤해요'},
                {'id': 'si_screen', 'label': '자기 전 스크린·카페인', 'value': '자기 전 스마트폰이나 카페인이 문제예요'},
                {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''},
            ],
        },
        # --- diet goal ---
        'q_diet_pattern': {
            'stage': 'q_diet_pattern', 'icon': 'meal',
            'question': '평소 식사 패턴은 어떤가요?',
            'options': [
                {'id': 'dp_regular', 'label': '규칙적으로 세 끼 먹어요', 'value': '규칙적으로 세 끼 먹어요'},
                {'id': 'dp_skip', 'label': '끼니를 자주 거르는 편', 'value': '끼니를 자주 거르는 편이에요'},
                {'id': 'dp_night', 'label': '야식이 잦아요', 'value': '야식이 잦은 편이에요'},
                {'id': 'dp_snack', 'label': '간식·군것질이 많아요', 'value': '간식과 군것질이 많은 편이에요'},
                {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''},
            ],
        },
        'q_eatout': {
            'stage': 'q_eatout', 'icon': 'meal',
            'question': '외식이나 배달은 얼마나 자주 하세요?',
            'options': [
                {'id': 'eo_rare', 'label': '거의 안 해요', 'value': '외식·배달은 거의 안 해요'},
                {'id': 'eo_few', 'label': '주 1~2회', 'value': '외식·배달은 주 1~2회 정도예요'},
                {'id': 'eo_some', 'label': '주 3~4회', 'value': '외식·배달은 주 3~4회 정도예요'},
                {'id': 'eo_daily', 'label': '거의 매일', 'value': '외식·배달을 거의 매일 해요'},
                {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''},
            ],
        },
        # --- habit goal ---
        'q_ex_level': {
            'stage': 'q_ex_level', 'icon': 'workout',
            'question': '현재 운동 수준은 어느 정도인가요?',
            'options': [
                {'id': 'el_none', 'label': '거의 안 해요', 'value': '운동을 거의 안 해요'},
                {'id': 'el_some', 'label': '가끔 해요', 'value': '운동을 가끔 해요'},
                {'id': 'el_1_2', 'label': '주 1~2회', 'value': '주 1~2회 운동해요'},
                {'id': 'el_3', 'label': '주 3회 이상', 'value': '주 3회 이상 운동해요'},
                {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''},
            ],
        },
        'q_ex_pref': {
            'stage': 'q_ex_pref', 'icon': 'workout',
            'question': '선호하는 운동 유형이 있나요?',
            'options': [
                {'id': 'ep_cardio', 'label': '걷기·유산소', 'value': '걷기 같은 유산소를 선호해요'},
                {'id': 'ep_strength', 'label': '근력 운동', 'value': '근력 운동을 선호해요'},
                {'id': 'ep_home', 'label': '홈트레이닝', 'value': '집에서 하는 홈트를 선호해요'},
                {'id': 'ep_yoga', 'label': '요가·스트레칭', 'value': '요가나 스트레칭을 선호해요'},
                {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''},
            ],
        },
        # --- weight goal ---
        'q_weight_target': {
            'stage': 'q_weight_target', 'icon': 'goal',
            'question': '감량 목표는 어느 정도로 생각하세요? (건강한 범위 안에서 도와드려요)',
            'options': [
                {'id': 'wt_light', 'label': '약 1~2kg', 'value': '2주간 약 1~2kg 정도 빼고 싶어요'},
                {'id': 'wt_mod', 'label': '약 3~4kg', 'value': '약 3~4kg 빼고 싶어요'},
                {'id': 'wt_health', 'label': '숫자보다 건강하게', 'value': '특정 숫자보다 건강하게 빠지면 좋겠어요'},
                {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''},
            ],
        },
        'q_activity': {
            'stage': 'q_activity', 'icon': 'workout',
            'question': '평소 활동량은 어떤 편인가요?',
            'options': [
                {'id': 'ac_sed', 'label': '주로 앉아서 지내요', 'value': '주로 앉아서 생활해요'},
                {'id': 'ac_mod', 'label': '보통이에요', 'value': '활동량은 보통이에요'},
                {'id': 'ac_active', 'label': '활동적인 편', 'value': '활동적인 편이에요'},
                {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''},
            ],
        },
        # --- overall goal ---
        'q_energy': {
            'stage': 'q_energy', 'icon': 'goal',
            'question': '요즘 컨디션에서 가장 신경 쓰이는 부분은 무엇인가요?',
            'options': [
                {'id': 'en_fatigue', 'label': '쉽게 피로하고 기력이 없어요', 'value': '쉽게 피로하고 기력이 없어요'},
                {'id': 'en_stress', 'label': '스트레스가 많아요', 'value': '스트레스가 많은 편이에요'},
                {'id': 'en_stamina', 'label': '체력이 떨어졌어요', 'value': '예전보다 체력이 떨어졌어요'},
                {'id': 'en_focus', 'label': '집중력이 떨어져요', 'value': '집중력이 떨어지는 편이에요'},
                {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''},
            ],
        },
    }

    # Goal-specific question order (after the goal question). Each ends with q_body.
    FLOWS = {
        'sleep':   ['q_sleep_time', 'q_sleep_issue', 'q_food', 'q_exercise', 'q_body'],
        'diet':    ['q_diet_pattern', 'q_eatout', 'q_food', 'q_exercise', 'q_body'],
        'habit':   ['q_ex_level', 'q_ex_pref', 'q_exercise', 'q_food', 'q_body'],
        'weight':  ['q_weight_target', 'q_activity', 'q_food', 'q_exercise', 'q_body'],
        'overall': ['q_energy', 'q_food', 'q_exercise', 'q_sleep', 'q_body'],
    }
    DEFAULT_FLOW = 'overall'
    # Max intake answers (goal + longest flow) for profile extraction.
    INTAKE_SPAN = 1 + max(len(f) for f in FLOWS.values())

    # tool: internal tool id (logged) · label: UI name · icon: frontend icon key
    # approve: phase-specific question shown to the control group at the checkpoint
    TOOL_META = {
        'calc': {'tool': 'nutrition_guide', 'label': '영양·에너지 가이드', 'icon': 'calc',
                 'approve': '이 영양 가이드로 식단을 구성할까요?'},
        'meal': {'tool': 'meal_database', 'label': '식단 데이터베이스', 'icon': 'meal',
                 'approve': '이 식단 구성으로 운동 계획을 세울까요?'},
        'workout': {'tool': 'workout_planner', 'label': '운동 루틴 설계기', 'icon': 'workout',
                    'approve': '이 운동 루틴으로 수면·생활습관 루틴을 설계할까요?'},
        'sleep': {'tool': 'sleep_planner', 'label': '수면·생활습관 설계기', 'icon': 'sleep',
                  'approve': '이 수면·생활습관 루틴으로 2주 일정을 편성할까요?'},
        'schedule': {'tool': 'schedule_builder', 'label': '2주 일정 편성기', 'icon': 'calendar',
                     'approve': '이 2주 일정으로 장보기 리스트를 만들까요?'},
        'grocery': {'tool': 'grocery_generator', 'label': '장보기 리스트 생성기', 'icon': 'grocery',
                    'approve': '이 리스트로 최종 계획을 정리할까요?'},
        'delivery': {'tool': 'plan_compiler', 'label': '계획 통합', 'icon': 'plan',
                     'approve': None},
    }

    STAGE_DESCRIPTIONS = {
        'intake_goal': '건강 목표 확인',
        'q_food': '식단 선호 확인',
        'q_exercise': '운동 가능 시간 확인',
        'q_sleep': '수면 습관 확인',
        'q_body': '신체 정보 확인 (선택)',
        'q_sleep_time': '수면 시간 확인',
        'q_sleep_issue': '수면 개선점 확인',
        'q_diet_pattern': '식사 패턴 확인',
        'q_eatout': '외식 빈도 확인',
        'q_ex_level': '운동 수준 확인',
        'q_ex_pref': '선호 운동 확인',
        'q_weight_target': '감량 목표 확인',
        'q_activity': '활동량 확인',
        'q_energy': '컨디션 확인',
        'calc': '영양·에너지 가이드 산출 중',
        'meal': '식단 구성 중',
        'workout': '운동 루틴 설계 중',
        'sleep': '수면·생활습관 루틴 설계 중',
        'schedule': '2주 일정 편성 중',
        'grocery': '장보기 리스트 생성 중',
        'delivered': '2주 루틴 전달 완료',
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

        # 1) First message = the opening request -> ask the goal question.
        if stage is None:
            return self._ask_question(conversation_id, self.GOAL_STEP, condition, autonomy,
                                      user_message, greet=True)

        # 2) Goal-adaptive intake: answer current question, ask the next one in the
        #    goal-specific flow, or launch the pipeline once the flow is complete.
        if stage == 'intake_goal' or stage in self.QUESTIONS:
            return self._advance_intake(conversation_id, condition, autonomy, stage, user_message)

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
        return self._ask_question(conversation_id, self.GOAL_STEP, condition, autonomy,
                                  user_message, greet=True)

    # ------------------------------------------------------------------ #
    # Goal-adaptive intake
    # ------------------------------------------------------------------ #
    def _detect_goal_key(self, text: str) -> str:
        t = text or ''
        if '체중' in t or '감량' in t:
            return 'weight'
        if '수면' in t or '잠' in t:
            return 'sleep'
        if '식습관' in t or '식사' in t or '식단' in t:
            return 'diet'
        if '운동 습관' in t or '규칙' in t:
            return 'habit'
        if '컨디션' in t or '에너지' in t or '피로' in t or '체력' in t:
            return 'overall'
        return self.DEFAULT_FLOW

    def _goal_key(self, conversation_id: int, current_answer: Optional[str] = None) -> str:
        """Resolve which goal flow we are in (from the goal answer)."""
        if current_answer is not None:
            return self._detect_goal_key(current_answer)
        msgs = self.db_manager.get_conversation_messages(conversation_id)
        user_msgs = [m['content'] for m in msgs if m.get('role') == 'user']
        return self._detect_goal_key(user_msgs[1] if len(user_msgs) > 1 else '')

    def _advance_intake(self, conversation_id: int, condition: str, autonomy: str,
                        stage: str, user_message: str) -> Dict[str, Any]:
        goal_key = self._goal_key(conversation_id,
                                  current_answer=user_message if stage == 'intake_goal' else None)
        flow = self.FLOWS.get(goal_key, self.FLOWS[self.DEFAULT_FLOW])

        if stage == 'intake_goal':
            next_id = flow[0]
        else:
            idx = flow.index(stage) if stage in flow else len(flow) - 1
            next_id = flow[idx + 1] if idx + 1 < len(flow) else None

        if next_id is None:
            # Intake complete -> launch the agentic pipeline.
            if condition == 'auto' or autonomy == 'high':
                return self._run_pipeline(conversation_id, condition, 'calc', user_message, autonomy)
            return self._run_single_phase(conversation_id, condition, 'calc', user_message, autonomy)

        # Position-aware connector so wording fits the flow (먼저 / 이제 / 마지막으로).
        pos = flow.index(next_id)
        if pos == 0:
            connector = '먼저, '
        elif pos == len(flow) - 1:
            connector = '마지막으로, '
        else:
            connector = '이제, '
        return self._ask_question(conversation_id, self.QUESTIONS[next_id],
                                  condition, autonomy, user_message, connector=connector)

    def _ask_question(
        self, conversation_id: int, step: Dict[str, Any], condition: str, autonomy: str,
        user_message: str, greet: bool = False, connector: str = ''
    ) -> Dict[str, Any]:
        """Ask one intake question with clickable options or a widget (deterministic)."""
        question = (connector + step['question']) if connector else step['question']
        response = (self.INTAKE_GREETING + '\n\n' + question) if greet else question
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage=step['stage'],
            user_input=user_message, gpt_response=response, autonomy_level=autonomy
        )
        return self._result(
            response, step['stage'], condition, autonomy,
            agent_actions=[], controls=False,
            choices=step.get('options'), widget=step.get('widget'),
            intake_icon=step.get('icon')
        )

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
            override_instruction=override_instruction,
            profile=self._user_profile(conversation_id)
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
        steps = [self._step_card(phase, response, visual=self._step_visual(phase))]
        approval_prompt = meta['approve'] if (condition == 'control' and not is_last) else None
        # The step card carries the content; keep the message body empty to avoid
        # duplicating it. For the final plan, add a short confirmation note.
        note = '계획이 완성됐습니다. 특정 항목을 바꾸고 싶으면 알려주세요.' if is_last else ''
        return self._result(note, stage, condition, autonomy,
                            agent_actions=actions, controls=controls,
                            steps=steps, approval_prompt=approval_prompt)

    def _run_pipeline(
        self, conversation_id: int, condition: str, start_phase: str,
        user_message: str, autonomy: str, intervention: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run all remaining tool steps end-to-end and deliver the plan (autonomous)."""
        start_idx = self.PIPELINE.index(start_phase)
        phases = self.PIPELINE[start_idx:]

        history = self.db_manager.get_conversation_messages(conversation_id)
        working_history = list(history)
        profile = self._user_profile(conversation_id)
        actions: List[Dict[str, str]] = []
        steps: List[Dict[str, str]] = []
        parts: List[str] = []

        for i, phase in enumerate(phases):
            text = self.gpt_service.generate_agent_response(
                condition=condition, phase=phase, user_message=user_message,
                conversation_history=working_history, autonomy_level='high',
                profile=profile
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
            steps.append(self._step_card(phase, text, visual=self._step_visual(phase)))
            parts.append(f"[{meta['label']}]\n{text}")

        closing = ("계획을 모두 확정했습니다. 그대로 따라 주시면 됩니다."
                   if condition == 'auto'
                   else "계획이 완성됐습니다. 특정 항목을 바꾸고 싶으면 알려주세요.")
        combined = "\n\n".join(parts) + "\n\n" + closing
        self.db_manager.add_message(conversation_id, 'assistant', combined)

        # The autonomous run reveals every step (animated) but never pauses.
        return self._result(closing, 'delivered', condition, 'high',
                            agent_actions=actions, controls=False, steps=steps)

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

        # The user asked a question about this step -> explain, stay at the checkpoint.
        if intent == 'question':
            return self._answer_question(conversation_id, condition, stage, user_message)

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

    def _answer_question(self, conversation_id: int, condition: str, stage: str,
                         user_message: str) -> Dict[str, Any]:
        """Answer a question about the current step substantively, then stay at the
        checkpoint so the user can still approve / modify / stop."""
        meta = self.TOOL_META[stage]
        history = self.db_manager.get_conversation_messages(conversation_id)
        response = self.gpt_service.generate_agent_response(
            condition=condition, phase=stage, user_message=user_message,
            conversation_history=history, autonomy_level='low',
            override_instruction=f"__QUESTION__[{meta['label']}] {user_message}",
            profile=self._user_profile(conversation_id)
        )
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage=stage,
            user_input=user_message, gpt_response=response,
            tool_name=meta['tool'], intervention_type='question', autonomy_level='low'
        )
        approval = meta['approve'] if condition == 'control' else None
        return self._result(response, stage, condition, 'low',
                            agent_actions=[], controls=(condition == 'control'),
                            approval_prompt=approval)

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

    def _user_profile(self, conversation_id: int) -> str:
        """Summarize the participant's intake answers so every pipeline phase is
        tailored to their stated goal/preferences (not weight-loss by default)."""
        msgs = self.db_manager.get_conversation_messages(conversation_id)
        user_msgs = [m['content'] for m in msgs if m.get('role') == 'user']
        # user_msgs[0] is the opening request; the next answers are the intake replies.
        answers = user_msgs[1:1 + self.INTAKE_SPAN]
        return ' / '.join(a for a in answers if a)

    def _action_card(self, phase: str, label: Optional[str] = None) -> Dict[str, str]:
        meta = self.TOOL_META[phase]
        return {
            'tool': meta['tool'],
            'label': label or meta['label'],
            'icon': meta.get('icon', 'plan'),
            'status': '실행 완료',
        }

    def _step_card(self, phase: str, content: str, visual: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """A pipeline step the frontend reveals with a working->done animation."""
        meta = self.TOOL_META[phase]
        return {
            'tool': meta['tool'],
            'label': meta['label'],
            'icon': meta.get('icon', 'plan'),
            'content': content,
            'visual': visual,
        }

    # Canonical baseline values, shared by the visuals and the demo content.
    MACROS = {'kcal': 1900, 'carb': 45, 'protein': 30, 'fat': 25}

    def _step_visual(self, phase: str) -> Optional[Dict[str, Any]]:
        """Structured data the frontend renders as an infographic (macro bar / calendar)."""
        if phase == 'calc':
            m = self.MACROS
            return {
                'type': 'macros', 'kcal': m['kcal'],
                'items': [
                    {'label': '탄수화물', 'pct': m['carb']},
                    {'label': '단백질', 'pct': m['protein']},
                    {'label': '지방', 'pct': m['fat']},
                ],
            }
        if phase == 'schedule':
            days = []
            for d in range(1, 15):
                if d % 7 in (3, 0):
                    kind = 'rest'
                else:
                    kind = 'strength' if d % 2 else 'cardio'
                days.append({'day': d, 'kind': kind,
                             'tag': '컨디션 점검' if d in (1, 8, 14) else ''})
            # Constant routines are stated once (single line) rather than repeated
            # in every day cell, which reads as more trustworthy.
            return {
                'type': 'calendar',
                'sleep_summary': '매일 취침 23:30 · 기상 07:00 (약 7.5시간)',
                'diet_summary': f"매일 약 {self.MACROS['kcal']:,}kcal 균형식 (3끼 + 가벼운 간식)",
                'days': days,
            }
        return None

    def _classify_intent(self, user_message: str) -> str:
        """Classify a control-group user action at a checkpoint."""
        msg = user_message.strip().lower()

        raise_patterns = ['알아서', '자율', '끝까지', '한번에', '한 번에', '쭉', '전체 진행', '다 해줘', '다해줘', '바로 완성']
        if any(p in msg for p in raise_patterns):
            return 'raise_autonomy'

        stop_patterns = ['중단', '멈춰', '그만', '잠깐', '스톱', 'stop', '정지', '대기']
        if any(p in msg for p in stop_patterns):
            return 'interrupt'

        # A question about the step (reasoning/clarification) -> answer it, don't modify.
        question_patterns = ['왜', '이유', '어째서', '무슨', '무엇', '뭐', '어떻게', '어떤', '궁금',
                             '설명', '근거', '왜냐', '뜻', '의미', 'why', '인가요', '인가', '나요?', '맞나']
        if user_message.strip().endswith('?') or any(p in msg for p in question_patterns):
            # but an explicit change request that also contains '?' should still modify
            change_words = ['바꿔', '수정', '변경', '교체', '빼줘', '추가해']
            if not any(c in msg for c in change_words):
                return 'question'

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
        resumable: bool = False, post_plan: bool = False,
        choices: Optional[List[Dict[str, str]]] = None,
        widget: Optional[Dict[str, Any]] = None,
        steps: Optional[List[Dict[str, str]]] = None,
        approval_prompt: Optional[str] = None,
        intake_icon: Optional[str] = None
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
            'choices': choices,
            'widget': widget,
            'steps': steps,
            'approval_prompt': approval_prompt,
            'intake_icon': intake_icon,
            'awaiting_input': stage not in ('closed',),
        }
