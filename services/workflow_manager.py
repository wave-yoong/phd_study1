import re
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

    # Default (full) pipeline of agentic tool steps.
    PIPELINE = ['calc', 'meal', 'workout', 'sleep', 'schedule', 'grocery', 'delivery']

    # Goal-adaptive pipelines: diet-centric steps (calc/meal/grocery) are dropped
    # for goals where food is not the focus (sleep, exercise habit).
    PIPELINES = {
        'sleep':   ['sleep', 'workout', 'schedule', 'delivery'],
        'habit':   ['workout', 'sleep', 'schedule', 'delivery'],
        'diet':    ['calc', 'meal', 'workout', 'sleep', 'schedule', 'grocery', 'delivery'],
        'weight':  ['calc', 'meal', 'workout', 'sleep', 'schedule', 'grocery', 'delivery'],
        'overall': ['calc', 'meal', 'workout', 'sleep', 'schedule', 'grocery', 'delivery'],
    }

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
    # Sleep / habit goals skip the food question (their pipeline has no diet step).
    FLOWS = {
        'sleep':   ['q_sleep_time', 'q_sleep_issue', 'q_exercise', 'q_body'],
        'diet':    ['q_diet_pattern', 'q_eatout', 'q_food', 'q_exercise', 'q_body'],
        'habit':   ['q_ex_level', 'q_ex_pref', 'q_exercise', 'q_body'],
        'weight':  ['q_weight_target', 'q_activity', 'q_food', 'q_exercise', 'q_body'],
        'overall': ['q_energy', 'q_food', 'q_exercise', 'q_sleep', 'q_body'],
    }
    DEFAULT_FLOW = 'overall'
    # Max intake answers (goal + longest flow) for profile extraction.
    INTAKE_SPAN = 1 + max(len(f) for f in FLOWS.values())

    # tool: internal tool id (logged) · label: UI name · icon: frontend icon key
    # approve: phase-specific question shown to the control group at the checkpoint
    # approve text is order-independent ('~대로 진행할까요?') so it stays correct
    # regardless of which goal-adaptive pipeline is in use.
    TOOL_META = {
        'calc': {'tool': 'nutrition_guide', 'label': '영양·에너지 가이드', 'icon': 'calc',
                 'approve': '이 영양 가이드대로 진행할까요?'},
        'meal': {'tool': 'meal_database', 'label': '식단 데이터베이스', 'icon': 'meal',
                 'approve': '이 식단 구성대로 진행할까요?'},
        'workout': {'tool': 'workout_planner', 'label': '운동 루틴 설계기', 'icon': 'workout',
                    'approve': '이 운동 루틴대로 진행할까요?'},
        'sleep': {'tool': 'sleep_planner', 'label': '수면·생활습관 설계기', 'icon': 'sleep',
                  'approve': '이 수면·생활습관 루틴대로 진행할까요?'},
        'schedule': {'tool': 'schedule_builder', 'label': '2주 일정 편성기', 'icon': 'calendar',
                     'approve': '이 2주 일정대로 진행할까요?'},
        'grocery': {'tool': 'grocery_generator', 'label': '장보기 리스트 생성기', 'icon': 'grocery',
                    'approve': '이 장보기 리스트대로 진행할까요?'},
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
            # Intake complete -> launch the goal-adaptive pipeline at its first step.
            first_phase = self._pipeline(conversation_id)[0]
            if condition == 'auto' or autonomy == 'high':
                return self._run_pipeline(conversation_id, condition, first_phase, user_message, autonomy)
            return self._run_single_phase(conversation_id, condition, first_phase, user_message, autonomy)

        # Position-aware, varied connector so wording feels natural across the flow.
        pos = flow.index(next_id)
        mids = ['다음으로, ', '그럼, ', '이어서, ', '좋아요, 그럼 ']
        if pos == 0:
            connector = '먼저, '
        elif pos == len(flow) - 1:
            connector = '마지막으로, '
        else:
            connector = mids[(pos - 1) % len(mids)]
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
        is_control = (condition == 'control')
        controls = is_control and not is_last
        has_diet = 'meal' in self._pipeline(conversation_id)
        display_response = '' if phase == 'grocery' else response
        steps = [self._step_card(
            phase,
            display_response,
            visual=self._step_visual(
                conversation_id, phase, has_diet, revision=override_instruction
            ),
        )]
        approval_prompt = meta['approve'] if (is_control and not is_last) else None
        modify_options = self._modify_options(phase) if (is_control and not is_last) else None
        # The step card carries the content; keep the message body empty to avoid
        # duplicating it.
        note = ''
        # On the final plan, the control group can still edit items afterwards.
        return self._result(note, stage, condition, autonomy,
                            agent_actions=actions, controls=controls,
                            steps=steps, approval_prompt=approval_prompt,
                            modify_options=modify_options,
                            post_plan=(is_control and is_last))

    def _run_pipeline(
        self, conversation_id: int, condition: str, start_phase: str,
        user_message: str, autonomy: str, intervention: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run all remaining tool steps end-to-end and deliver the plan (autonomous)."""
        pipeline = self._pipeline(conversation_id)
        start_idx = pipeline.index(start_phase) if start_phase in pipeline else 0
        phases = pipeline[start_idx:]
        has_diet = 'meal' in pipeline

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
            display_text = '' if phase == 'grocery' else text
            steps.append(self._step_card(
                phase,
                display_text,
                visual=self._step_visual(conversation_id, phase, has_diet),
            ))
            parts.append(f"[{meta['label']}]\n{text}")

        closing = ("계획을 모두 확정했습니다. 그대로 따라 주시면 됩니다."
                   if condition == 'auto'
                   else "계획이 완성됐습니다. 특정 항목을 바꾸고 싶으면 알려주세요.")
        combined = "\n\n".join(parts) + "\n\n" + closing
        self.db_manager.add_message(conversation_id, 'assistant', combined)

        # The autonomous run reveals every step (animated) but never pauses.
        return self._result(closing, 'delivered', condition, 'high',
                            agent_actions=actions, controls=False, steps=steps,
                            post_plan=(condition == 'control'))

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
            next_phase = self._next_phase(conversation_id, stage)
            if next_phase is None:
                return self._handle_post_plan(conversation_id, condition, 'high', user_message)
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
        next_phase = self._next_phase(conversation_id, stage)
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
        is_control = (condition == 'control')
        approval = meta['approve'] if is_control else None
        return self._result(response, stage, condition, 'low',
                            agent_actions=[], controls=is_control,
                            approval_prompt=approval,
                            modify_options=self._modify_options(stage) if is_control else None)

    def _handle_paused(
        self, conversation_id: int, condition: str, autonomy: str,
        latest: Dict[str, Any], user_message: str
    ) -> Dict[str, Any]:
        intent = self._classify_intent(user_message)
        resume_from = self._resume_target.get(conversation_id)

        if intent in ('approve', 'raise_autonomy') and resume_from:
            next_phase = self._next_phase(conversation_id, resume_from) or resume_from
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
            override_instruction=user_message,
            profile=self._user_profile(conversation_id)
        )
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='delivered',
            user_input=user_message, gpt_response=response,
            tool_name='plan_compiler', intervention_type='override', autonomy_level=autonomy
        )
        has_diet = 'meal' in self._pipeline(conversation_id)
        revision = self._revision_detail(user_message)
        edited_phase = self._revision_phase(revision)
        steps = []
        actions = []
        if edited_phase != 'delivery':
            steps.append(self._step_card(
                edited_phase,
                '',
                visual=self._step_visual(
                    conversation_id, edited_phase, has_diet, revision=user_message
                ),
            ))
            actions.append(self._action_card(edited_phase, label='항목 수정 반영'))
        steps.append(self._step_card(
            'delivery',
            response,
            visual=self._step_visual(conversation_id, 'delivery', has_diet),
        ))
        actions.append(self._action_card('delivery', label='계획 수정 완료'))
        return self._result('', 'delivered', condition, autonomy,
                            agent_actions=actions,
                            controls=True, post_plan=True, steps=steps)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    # Per-process memory of where each conversation paused (best-effort).
    _resume_target: Dict[int, str] = {}

    def _pipeline(self, conversation_id: int) -> List[str]:
        """The goal-adaptive pipeline for this conversation."""
        return self.PIPELINES.get(self._goal_key(conversation_id), self.PIPELINE)

    def _next_phase(self, conversation_id: int, phase: str) -> Optional[str]:
        pipeline = self._pipeline(conversation_id)
        if phase not in pipeline:
            return None
        idx = pipeline.index(phase)
        return pipeline[idx + 1] if idx + 1 < len(pipeline) else None

    def _user_profile(self, conversation_id: int) -> str:
        """Summarize the participant's intake answers so every pipeline phase is
        tailored to their stated goal/preferences (not weight-loss by default)."""
        msgs = self.db_manager.get_conversation_messages(conversation_id)
        user_msgs = [m['content'] for m in msgs if m.get('role') == 'user']
        # user_msgs[0] is the opening request; the next answers are the intake replies.
        answers = user_msgs[1:1 + self.INTAKE_SPAN]
        return ' / '.join(a for a in answers if a)

    def _all_user_text(self, conversation_id: int) -> str:
        """Return user-provided context, including intake answers beyond a fixed slice."""
        msgs = self.db_manager.get_conversation_messages(conversation_id)
        return ' / '.join(
            m['content'] for m in msgs
            if m.get('role') == 'user' and m.get('content')
        )

    def _exercise_context(self, conversation_id: int) -> Dict[str, Any]:
        """Extract exercise availability, current level, and preference from intake."""
        profile = self._all_user_text(conversation_id)
        availability: List[Dict[str, str]] = []
        match = re.search(r'운동 가능:\s*([^/]+)', profile)
        if match:
            for item in match.group(1).split(','):
                item = item.strip()
                day_match = re.match(r'([월화수목금토일])(?:요일)?\s*(.*)', item)
                if day_match:
                    availability.append({
                        'day': day_match.group(1),
                        'time': day_match.group(2).strip() or '가능 시간',
                    })

        if not availability:
            availability = [
                {'day': '월', 'time': '저녁'},
                {'day': '수', 'time': '저녁'},
                {'day': '토', 'time': '오전'},
            ]

        if '거의 안' in profile:
            level = '운동을 거의 하지 않음'
            duration = 20
            max_days = 3
        elif '주 1~2회' in profile:
            level = '현재 주 1~2회 운동'
            duration = 30
            max_days = 4
        elif '주 3회 이상' in profile:
            level = '현재 주 3회 이상 운동'
            duration = 40
            max_days = 5
        elif '가끔' in profile:
            level = '가끔 운동함'
            duration = 25
            max_days = 3
        else:
            level = ('입력한 운동 가능 일정 확인됨'
                     if match else '현재 수준에 맞춰 점진적으로 시작')
            duration = 30
            max_days = 4

        if '요가' in profile or '스트레칭' in profile:
            preference = '요가·스트레칭'
        elif '홈트' in profile:
            preference = '홈트레이닝'
        elif '근력' in profile:
            preference = '근력 운동'
        elif '걷기' in profile or '유산소' in profile:
            preference = '걷기·유산소'
        else:
            preference = '근력과 유산소 병행'

        return {
            'availability': availability[:max_days],
            'level': level,
            'duration': duration,
            'preference': preference,
        }

    def _diet_strategy(self, conversation_id: int) -> str:
        """Return a goal-specific diet description without generic '균형식' wording."""
        strategies = {
            'weight': '단백질을 충분히 챙기고 튀김·포화지방을 줄인 감량형 식사',
            'diet': '채소·통곡물 중심으로 야식과 군것질 빈도를 낮춘 규칙적 식사',
            'overall': '에너지 유지를 위해 단백질·통곡물·채소를 고르게 챙기는 식사',
            'sleep': '늦은 야식과 과도한 카페인을 줄여 수면 리듬을 돕는 식사',
            'habit': '운동 전후 단백질과 수분을 챙겨 회복을 돕는 식사',
        }
        return strategies.get(
            self._goal_key(conversation_id),
            '가공식품을 줄이고 단백질·채소를 충분히 챙기는 식사',
        )

    def _revision_requests(self, conversation_id: int) -> List[str]:
        """Collect raw user edits for applying them to later plan visuals."""
        revisions = []
        for state in self.db_manager.get_workflow_history(conversation_id):
            if state.get('intervention_type') in ('modify', 'override'):
                request = (state.get('user_input') or '').strip()
                if request and request not in revisions:
                    revisions.append(request)
        return revisions

    @staticmethod
    def _revision_detail(
        request: str, phase_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Turn a free-text edit into a concise summary and applicable fields."""
        text = re.sub(r'\s+', ' ', (request or '').strip().strip('"\''))
        day_match = re.search(r'(\d{1,2})\s*일차', text)
        day = int(day_match.group(1)) if day_match else None
        duration_match = re.search(r'(\d{1,3})\s*분', text)
        duration = f"{duration_match.group(1)}분" if duration_match else ''

        if '점검' in text and day:
            return {
                'type': 'check_day',
                'day': day,
                'summary': f"{day}일차에 컨디션 점검 설정",
            }

        kcal_match = re.search(r'(\d{3,4})\s*(?:kcal|칼로리)', text, re.IGNORECASE)
        if '칼로리' in text or kcal_match:
            if kcal_match:
                kcal = int(kcal_match.group(1))
            elif any(word in text for word in ('낮', '줄', '내려')):
                kcal = 1800
            elif any(word in text for word in ('높', '늘', '올려')):
                kcal = 2000
            else:
                kcal = 1900
            return {
                'type': 'calorie',
                'kcal': kcal,
                'summary': f"하루 에너지 목표를 약 {kcal:,}kcal로 조정",
            }

        macro_pct_match = re.search(
            r'(단백질|탄수화물|지방)[^\d]{0,10}(\d{1,2})\s*%', text
        )
        if macro_pct_match or (
            any(word in text for word in ('단백질', '탄수화물', '지방'))
            and any(word in text for word in ('비중', '비율', '높', '늘', '줄', '낮'))
        ):
            macros = {'carb': 45, 'protein': 30, 'fat': 25}
            if macro_pct_match:
                nutrient, pct_text = macro_pct_match.groups()
                pct = max(10, min(60, int(pct_text)))
                if nutrient == '단백질':
                    macros = {'carb': 100 - pct - 25, 'protein': pct, 'fat': 25}
                elif nutrient == '탄수화물':
                    macros = {'carb': pct, 'protein': 100 - pct - 25, 'fat': 25}
                else:
                    macros = {'carb': 100 - pct - 30, 'protein': 30, 'fat': pct}
            elif '단백질' in text and any(word in text for word in ('높', '늘', '올려')):
                macros = {'carb': 40, 'protein': 35, 'fat': 25}
            elif '탄수화물' in text and any(word in text for word in ('낮', '줄', '내려')):
                macros = {'carb': 35, 'protein': 35, 'fat': 30}
            elif '지방' in text and any(word in text for word in ('낮', '줄', '내려')):
                macros = {'carb': 45, 'protein': 35, 'fat': 20}
            return {
                'type': 'macros',
                'macros': macros,
                'summary': (
                    f"영양 비율을 탄수화물 {macros['carb']}% · "
                    f"단백질 {macros['protein']}% · 지방 {macros['fat']}%로 조정"
                ),
            }

        weekdays = []
        weekday_pattern = (
            r'(?<![가-힣])([월화수목금토일])(?:요일)?'
            r'(?=[·,\s/&]|$|으로|로|을|를|은|는)'
        )
        for weekday in re.findall(weekday_pattern, text):
            if weekday not in weekdays:
                weekdays.append(weekday)
        if '휴식' in text and weekdays and not day:
            return {
                'type': 'rest_days',
                'weekdays': weekdays,
                'summary': f"{'·'.join(weekdays)}요일을 휴식일로 설정",
            }

        exercise_kind = None
        exercise_label = ''
        if any(word in text for word in ('휴식', '쉬는 날', '쉬기')):
            exercise_kind, exercise_label = 'rest', '휴식'
        elif any(word in text for word in ('요가', '스트레칭')):
            exercise_kind = 'mobility'
            exercise_label = '요가' if '요가' in text else '스트레칭'
        elif any(word in text for word in ('걷기', '유산소', '달리기', '러닝')):
            exercise_kind = 'cardio'
            exercise_label = '걷기' if '걷기' in text else '유산소'
        elif '근력' in text:
            exercise_kind, exercise_label = 'strength', '근력'

        time_match = re.search(r'(아침|오전|점심|오후|저녁|밤)', text)
        time_label = time_match.group(1) if time_match else ''
        if exercise_kind:
            result_label = ' '.join(
                part for part in (time_label, exercise_label, duration) if part
            )
            if day:
                summary = f"{day}일차 운동을 {result_label or exercise_label}으로 변경"
            else:
                summary = f"운동 구성을 {result_label or exercise_label} 중심으로 변경"
            return {
                'type': 'exercise',
                'day': day,
                'kind': exercise_kind,
                'label': result_label or exercise_label,
                'summary': summary,
            }

        if phase_hint == 'sleep' or any(
            word in text for word in ('취침', '기상', '수면', '카페인', '생활습관')
        ):
            bedtime = None
            waketime = None
            bed_match = re.search(
                r'취침(?:\s*시간)?(?:을|은|:)?\s*((?:오전|오후)?\s*\d{1,2}(?::\d{2})?(?:시)?)',
                text,
            )
            wake_match = re.search(
                r'기상(?:\s*시간)?(?:을|은|:)?\s*((?:오전|오후)?\s*\d{1,2}(?::\d{2})?(?:시)?)',
                text,
            )
            if bed_match:
                bedtime = WorkflowManager._normalize_time(bed_match.group(1))
            if wake_match:
                waketime = WorkflowManager._normalize_time(wake_match.group(1))
            details = []
            if bedtime:
                details.append(f"취침 {bedtime}")
            if waketime:
                details.append(f"기상 {waketime}")
            if not bedtime and not waketime:
                tip = (
                    '취침 8시간 전부터 카페인 음료 피하기'
                    if '카페인' in text
                    else '취침 전 가벼운 스트레칭과 조명 낮추기'
                )
                return {
                    'type': 'sleep_tip',
                    'tip': tip,
                    'summary': f"생활습관 팁을 '{tip}'로 변경",
                }
            detail_text = f": {' · '.join(details)}" if details else ''
            return {
                'type': 'sleep',
                'bedtime': bedtime,
                'waketime': waketime,
                'summary': f"수면 시간 조정{detail_text}",
            }

        grocery_change = any(word in text for word in ('빼', '제외', '삭제', '추가', '넣'))
        grocery_context = any(word in text for word in ('장보기', '품목', '재료'))
        if phase_hint == 'grocery' or (
            phase_hint != 'meal' and (grocery_context or grocery_change)
        ):
            remove_match = re.search(
                r'([가-힣A-Za-z0-9]+?)(?:을|를)?\s*(?:빼|제외|삭제)',
                text,
            )
            add_match = re.search(
                r'([가-힣A-Za-z0-9]+?)(?:을|를)?\s*(?:추가|넣)',
                text,
            )
            remove_item = remove_match.group(1) if remove_match else None
            add_item = add_match.group(1) if add_match else None
            if remove_item and not add_item:
                after_remove = re.search(
                    r'(?:빼고|제외하고)\s*([가-힣A-Za-z0-9]+?)(?:으로|로|을|를|\s)',
                    text,
                )
                add_item = after_remove.group(1) if after_remove else None
            changes = []
            if remove_item:
                changes.append(f"{remove_item} 제외")
            if add_item:
                changes.append(f"{add_item} 추가")
            return {
                'type': 'grocery',
                'remove': remove_item,
                'add': add_item,
                'summary': ' · '.join(changes) or '요청한 식재료 기준으로 장보기 품목 조정',
            }

        meal_target = next(
            (meal for meal in ('아침', '점심', '저녁', '간식') if meal in text),
            None,
        )
        if phase_hint == 'meal' or meal_target or any(
            word in text for word in ('저탄수', '식단', '끼니', '메뉴')
        ):
            if '저탄수' in text or ('탄수' in text and any(word in text for word in ('줄', '낮'))):
                return {
                    'type': 'meal',
                    'mode': 'low_carb',
                    'summary': '탄수화물 양을 줄이고 단백질·채소 중심으로 식단 조정',
                }
            if meal_target and any(word in text for word in ('가볍', '줄', '적게')):
                return {
                    'type': 'meal',
                    'target': meal_target,
                    'mode': 'lighter',
                    'summary': f"{meal_target}을 가벼운 구성으로 변경",
                }
            replacement = re.search(
                r'([가-힣A-Za-z0-9]+?)(?:\s*대신|\s*말고)\s*([가-힣A-Za-z0-9]+)',
                text,
            )
            return {
                'type': 'meal',
                'target': meal_target,
                'remove': replacement.group(1) if replacement else None,
                'add': replacement.group(2) if replacement else None,
                'summary': (
                    f"{meal_target or '식단'} 메뉴를 요청한 구성으로 변경"
                ),
            }

        cleaned = re.sub(
            r'(해\s*줘|해주세요|해주셈|바꿔\s*줘|바꿔주세요|수정해\s*줘|'
            r'변경해\s*줘|하자|했으면 좋겠어(?:요)?|부탁해(?:요)?)\s*[.!?]*$',
            '',
            text,
        ).strip()
        if len(cleaned) > 42:
            cleaned = cleaned[:42].rstrip() + '…'
        return {
            'type': 'general',
            'summary': f"요청한 항목 조정: {cleaned or '세부 설정 변경'}",
        }

    def _revision_details(self, conversation_id: int) -> List[Dict[str, Any]]:
        details = []
        for state in self.db_manager.get_workflow_history(conversation_id):
            if state.get('intervention_type') not in ('modify', 'override'):
                continue
            request = (state.get('user_input') or '').strip()
            if not request:
                continue
            stage = state.get('stage')
            phase_hint = stage if stage in self.PIPELINE else None
            detail = self._revision_detail(request, phase_hint=phase_hint)
            if detail not in details:
                details.append(detail)
        return details

    @staticmethod
    def _revision_phase(revision: Dict[str, Any]) -> str:
        return {
            'calorie': 'calc',
            'macros': 'calc',
            'meal': 'meal',
            'exercise': 'schedule' if revision.get('day') else 'workout',
            'rest_days': 'workout',
            'sleep': 'sleep',
            'sleep_tip': 'sleep',
            'check_day': 'schedule',
            'grocery': 'grocery',
        }.get(revision.get('type'), 'delivery')

    @staticmethod
    def _normalize_time(value: str) -> Optional[str]:
        match = re.search(r'(오전|오후)?\s*(\d{1,2})(?::(\d{2}))?', value or '')
        if not match:
            return None
        period, hour_text, minute_text = match.groups()
        hour = int(hour_text)
        minute = int(minute_text or 0)
        if period == '오후' and hour < 12:
            hour += 12
        if period == '오전' and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            return None
        return f"{hour:02d}:{minute:02d}"

    def _sleep_plan(self, conversation_id: int) -> Dict[str, str]:
        bedtime = '23:30'
        waketime = '07:00'
        for detail in self._revision_details(conversation_id):
            if detail['type'] == 'sleep':
                bedtime = detail.get('bedtime') or bedtime
                waketime = detail.get('waketime') or waketime
        bed_hour, bed_minute = (int(part) for part in bedtime.split(':'))
        wake_hour, wake_minute = (int(part) for part in waketime.split(':'))
        bed_total = bed_hour * 60 + bed_minute
        wake_total = wake_hour * 60 + wake_minute
        duration_minutes = (wake_total - bed_total) % (24 * 60)
        hours = duration_minutes // 60
        minutes = duration_minutes % 60
        duration = f"약 {hours}시간" + (f" {minutes}분" if minutes else '')
        return {'bedtime': bedtime, 'waketime': waketime, 'duration': duration}

    # Per-phase quick-edit menu shown when the control group clicks '이 항목 수정'.
    MODIFY_MENUS = {
        'calc': [('칼로리 목표 조정', '예: 칼로리를 조금 낮춰줘'),
                 ('영양 비율 조정', '예: 단백질 비중을 높여줘')],
        'meal': [('특정 끼니 바꾸기', '예: 저녁을 더 가볍게 바꿔줘'),
                 ('식단 방향 바꾸기', '예: 저탄수 위주로 바꿔줘')],
        'workout': [('운동 종류 바꾸기', '예: 근력 대신 요가로 바꿔줘'),
                    ('휴식일 바꾸기', '예: 휴식일을 토·일로 바꿔줘')],
        'sleep': [('취침/기상 시간 바꾸기', '예: 취침을 23:00으로 바꿔줘'),
                  ('추천 생활습관 바꾸기', '예: 카페인 관련 팁을 바꿔줘')],
        'schedule': [('특정 날짜 바꾸기', '예: 3일차 운동을 요가로 바꿔줘')],
        'grocery': [('품목 추가/삭제', '예: 두부를 빼고 연어를 추가해줘')],
    }

    def _modify_options(self, phase: str) -> List[Dict[str, str]]:
        items = [{'label': l, 'placeholder': p} for l, p in self.MODIFY_MENUS.get(phase, [])]
        items.append({'label': '기타 (직접 입력)', 'placeholder': '바꾸고 싶은 내용을 자유롭게 입력하세요'})
        return items

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
    GOAL_LABELS = {
        'sleep': '수면의 질 개선', 'habit': '규칙적인 운동 습관',
        'diet': '식습관 개선', 'weight': '체중 감량', 'overall': '전반적 컨디션·에너지',
    }

    def _step_visual(
        self,
        conversation_id: int,
        phase: str,
        has_diet: bool = True,
        revision: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Structured data the frontend renders as cards / infographics."""
        revision_details = self._revision_details(conversation_id)
        current_revision = (
            self._revision_detail(revision, phase_hint=phase)
            if revision else None
        )

        def revised(visual: Dict[str, Any]) -> Dict[str, Any]:
            if current_revision:
                visual['revision'] = current_revision['summary']
            return visual

        if phase == 'calc':
            m = dict(self.MACROS)
            for detail in revision_details:
                if detail['type'] == 'calorie':
                    m['kcal'] = detail['kcal']
                elif detail['type'] == 'macros':
                    m.update(detail['macros'])
            return revised({
                'type': 'macros', 'kcal': m['kcal'],
                'items': [
                    {'label': '탄수화물', 'pct': m['carb']},
                    {'label': '단백질', 'pct': m['protein']},
                    {'label': '지방', 'pct': m['fat']},
                ],
                'extras': [{'label': '수분', 'value': '1.5~2L'}],
            })
        if phase == 'meal':
            cards = [
                {'emoji': '🥣', 'title': '아침', 'body': '그릭요거트 + 베리 + 견과'},
                {'emoji': '🍱', 'title': '점심', 'body': '현미밥 + 닭가슴살(또는 두부) + 샐러드'},
                {'emoji': '🥗', 'title': '저녁', 'body': '채소볶음 + 미역국 + 잡곡밥'},
                {'emoji': '🍎', 'title': '간식', 'body': '방울토마토, 삶은 달걀'},
            ]
            for detail in revision_details:
                if detail['type'] != 'meal':
                    continue
                if detail.get('mode') == 'low_carb':
                    cards[0]['body'] = '그릭요거트 + 삶은 달걀 + 베리'
                    cards[1]['body'] = '현미밥 반 공기 + 닭가슴살(또는 두부) + 채소'
                    cards[2]['body'] = '두부·닭가슴살 샐러드 + 채소 수프'
                elif detail.get('mode') == 'lighter' and detail.get('target'):
                    lighter = {
                        '아침': '그릭요거트 + 베리',
                        '점심': '현미밥 반 공기 + 단백질 샐러드',
                        '저녁': '두부 샐러드 + 채소 수프',
                        '간식': '방울토마토 또는 무가당 요거트',
                    }
                    for card in cards:
                        if card['title'] == detail['target']:
                            card['body'] = lighter[detail['target']]
                elif detail.get('remove') and detail.get('add'):
                    targets = [
                        card for card in cards
                        if not detail.get('target') or card['title'] == detail['target']
                    ]
                    for card in targets:
                        card['body'] = card['body'].replace(
                            detail['remove'], detail['add']
                        )
            return revised({'type': 'cards', 'title': '하루 식단 예시', 'cards': cards})
        if phase == 'workout':
            context = self._exercise_context(conversation_id)
            exercise_revisions = [
                item for item in revision_details
                if item['type'] == 'exercise' and not item.get('day')
            ]
            if exercise_revisions:
                latest_exercise = exercise_revisions[-1]
                context['preference'] = latest_exercise['label']
                duration_match = re.search(r'(\d{1,3})분', latest_exercise['label'])
                if duration_match:
                    context['duration'] = int(duration_match.group(1))
            rest_days = []
            for detail in revision_details:
                if detail['type'] == 'rest_days':
                    rest_days = detail['weekdays']
            if rest_days:
                context['availability'] = [
                    slot for slot in context['availability']
                    if slot['day'] not in rest_days
                ]
            if exercise_revisions:
                exercise_types = [context['preference']] * 5
            else:
                exercise_types = [
                    context['preference'],
                    '전신 근력',
                    '빠르게 걷기·가벼운 유산소',
                    '회복 스트레칭',
                    '근력과 유산소 혼합',
                ]
            cards = [{
                'emoji': '📌',
                'title': '현재 루틴 반영',
                'body': (
                    f"{context['level']} · {context['preference']} 선호를 고려해 "
                    f"{context['duration']}분부터 시작"
                ),
            }]
            if rest_days:
                cards.append({
                    'emoji': '🧘',
                    'title': '휴식일',
                    'body': f"{'·'.join(rest_days)}요일은 회복과 가벼운 스트레칭",
                })
            for index, slot in enumerate(context['availability']):
                cards.append({
                    'emoji': '🏃' if index % 2 else '🏋️',
                    'title': f"{slot['day']}요일 {slot['time']}",
                    'body': f"{exercise_types[index % len(exercise_types)]} {context['duration']}분",
                })
            return revised({
                'type': 'cards',
                'title': '사용자 운동 가능 시간에 맞춘 주간 루틴',
                'cards': cards,
            })
        if phase == 'sleep':
            sleep = self._sleep_plan(conversation_id)
            tips = ['취침 1시간 전 스크린 줄이기', '오후 2시 이후 카페인 자제',
                    '기상 후 물 한 잔', '하루 10분 산책으로 스트레스 관리']
            sleep_tip_revisions = [
                detail for detail in revision_details
                if detail['type'] == 'sleep_tip'
            ]
            if sleep_tip_revisions:
                tips[1] = sleep_tip_revisions[-1]['tip']
            return revised({
                'type': 'sleep',
                'bedtime': sleep['bedtime'],
                'waketime': sleep['waketime'],
                'duration': sleep['duration'],
                'tips': tips,
            })
        if phase == 'schedule':
            exercise = self._exercise_context(conversation_id)
            active_days = {item['day'] for item in exercise['availability']}
            rest_days = set()
            for detail in revision_details:
                if detail['type'] == 'rest_days':
                    rest_days = set(detail['weekdays'])
            weekdays = ['월', '화', '수', '목', '금', '토', '일']
            days = []
            for d in range(1, 15):
                weekday = weekdays[(d - 1) % 7]
                if weekday not in active_days or weekday in rest_days:
                    kind = 'rest'
                else:
                    kind = 'strength' if d % 2 else 'cardio'
                days.append({'day': d, 'kind': kind,
                             'tag': '컨디션 점검' if d in (1, 8, 14) else ''})

            check_revisions = [
                item for item in revision_details if item['type'] == 'check_day'
            ]
            if check_revisions:
                check_days = {check_revisions[-1]['day']}
                for item in days:
                    item['tag'] = '컨디션 점검' if item['day'] in check_days else ''

            for change in (
                item for item in revision_details
                if item['type'] == 'exercise' and item.get('day')
            ):
                if 1 <= change['day'] <= len(days):
                    target = days[change['day'] - 1]
                    target['kind'] = change['kind']
                    target['label'] = change['label']
            sleep = self._sleep_plan(conversation_id)
            return revised({
                'type': 'calendar',
                'sleep_summary': (
                    f"매일 취침 {sleep['bedtime']} · 기상 {sleep['waketime']} "
                    f"({sleep['duration']})"
                ),
                'diet_summary': (self._diet_strategy(conversation_id)
                                 if has_diet else ''),
                'days': days,
            })
        if phase == 'grocery':
            weeks = [
                {
                        'label': '1주차',
                        'budget': '약 55,000~65,000원',
                        'cards': [
                            {'emoji': '🍗', 'title': '단백질', 'body': '닭가슴살 5팩, 두부 3모, 달걀 10개, 그릭요거트 4개'},
                            {'emoji': '🥦', 'title': '채소', 'body': '샐러드 채소, 브로콜리, 미역, 방울토마토'},
                            {'emoji': '🍚', 'title': '탄수화물', 'body': '현미 1kg, 고구마 5개, 통밀빵 1봉'},
                            {'emoji': '🥜', 'title': '기타', 'body': '견과류, 올리브유, 냉동 베리'},
                        ],
                },
                {
                        'label': '2주차',
                        'budget': '약 60,000~72,000원',
                        'cards': [
                            {'emoji': '🐟', 'title': '단백질', 'body': '연어 2팩, 흰살생선 2팩, 렌틸콩 1봉, 달걀 10개'},
                            {'emoji': '🥬', 'title': '채소', 'body': '시금치, 파프리카, 양배추, 버섯, 오이'},
                            {'emoji': '🌾', 'title': '탄수화물', 'body': '오트밀 1봉, 잡곡 1kg, 단호박 1개'},
                            {'emoji': '🍊', 'title': '기타', 'body': '무가당 두유, 제철 과일, 플레인 요거트'},
                        ],
                },
            ]
            for detail in revision_details:
                if detail['type'] != 'grocery':
                    continue
                remove_item = detail.get('remove')
                add_item = detail.get('add')
                if remove_item:
                    for week in weeks:
                        for card in week['cards']:
                            items = [
                                item.strip() for item in card['body'].split(',')
                                if remove_item not in item
                            ]
                            card['body'] = ', '.join(items)
                if add_item:
                    protein_card = weeks[0]['cards'][0]
                    if add_item not in protein_card['body']:
                        protein_card['body'] += f", {add_item}"
            return revised({
                'type': 'grocery',
                'title': '2주 장보기 리스트와 예상 예산',
                'weeks': weeks,
                'total_budget': '2주 총예산 약 115,000~137,000원',
                'budget_note': '일반 대형마트 기준의 예상치이며 지역·브랜드·보유 식재료에 따라 달라질 수 있어요.',
            })
        if phase == 'delivery':
            goal = self.GOAL_LABELS.get(self._goal_key(conversation_id), '건강 루틴')
            exercise = self._exercise_context(conversation_id)
            days = '·'.join(item['day'] for item in exercise['availability'])
            cards = [{'emoji': '🎯', 'title': '목표', 'body': goal}]
            if has_diet:
                cards.append({'emoji': '🍽️', 'title': '식단', 'body': self._diet_strategy(conversation_id)})
                cards.append({'emoji': '🛒', 'title': '장보기 예산', 'body': '1주차 약 5.5~6.5만원 · 2주차 약 6~7.2만원'})
            cards.append({
                'emoji': '💪',
                'title': '운동',
                'body': f"{exercise['level']}을 고려해 {days}요일, 회당 약 {exercise['duration']}분",
            })
            sleep = self._sleep_plan(conversation_id)
            cards.append({
                'emoji': '😴',
                'title': '수면',
                'body': f"취침 {sleep['bedtime']} · 기상 {sleep['waketime']}",
            })
            visual = {
                'type': 'summary', 'title': '2주 건강 루틴 요약', 'cards': cards,
                'safety': '무리한 절식·과한 운동은 피하고, 어지럼증 등 이상이 느껴지면 강도를 낮추세요. '
                          '지속 가능한 습관이 가장 중요하며, 지병이 있다면 전문가와 상담하세요.',
            }
            revisions = [item['summary'] for item in revision_details]
            if revisions:
                visual['cards'].append({
                    'emoji': '✏️',
                    'title': '수정 반영',
                    'body': ' / '.join(revisions[-2:]),
                })
                visual['revisions'] = revisions
            return visual
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
            # If the message also requests a change, treat it as a modification.
            change_words = ['바꿔', '바꾸', '수정', '변경', '교체', '빼', '넣어', '추가', '줄여', '늘려',
                            '더 ', '덜 ', '말고', '대신', '조정', '올려', '내려', '해줘', '해 줘']
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
        intake_icon: Optional[str] = None,
        modify_options: Optional[List[Dict[str, str]]] = None
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
            'modify_options': modify_options,
            'awaiting_input': stage not in ('closed',),
        }
