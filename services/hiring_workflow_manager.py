import re
from typing import Dict, Any, List, Optional, Tuple
from database.db_manager import DBManager


# Fictional applicant pool (fixed). One source of truth used both for the
# start-screen roster and for the 'finalize' decision cards, so they never drift.
# Note: 나이/학력 are resume-style fields; equalize or drop them if you don't want
# demographic attributes to become a confound (see HIRING_STUDY_DESIGN.md).
CANDIDATES: List[Dict[str, str]] = [
    {
        'id': 'A', 'name': '김서연', 'age': 29, 'tag': '실무 즉시전력형',
        'education': '국내 4년제 신문방송학 학사',
        'experience': '마케팅 인턴 2회(스타트업·대행사), SNS·퍼포먼스 캠페인 실운영',
        'skills': '퍼포먼스 마케팅, 광고 세팅, 콘텐츠 기획',
        'concern': '6개월~1년 단위로 이직이 잦음',
        'ai_note': '실무역량 상 / 장기 근속은 데이터로 예측 어려움',
    },
    {
        'id': 'B', 'name': '이준호', 'age': 26, 'tag': '성장 잠재력형',
        'education': '상위권대 경영학 학사 (신입)',
        'experience': '정규 실무 경험 거의 없음, 마케팅 공모전 수상 2회',
        'skills': '콘텐츠 기획·카피라이팅, 빠른 학습력',
        'concern': '실무 역량이 아직 검증되지 않음',
        'ai_note': '잠재력 상 / 잠재력은 예측치라 실제 성과는 불확실',
    },
    {
        'id': 'C', 'name': '박민지', 'age': 28, 'tag': '조직 적합성형',
        'education': '국내 4년제 심리학 학사',
        'experience': '중소기업 마케팅 1년(팀 협업 중심)',
        'skills': '커뮤니케이션, 협업, 프로젝트 코디네이션',
        'concern': '뾰족한 전문성이 부족함',
        'ai_note': '적합성 상 / 면접 인상은 주관적이라 편향 가능',
    },
    {
        'id': 'D', 'name': '최지훈', 'age': 30, 'tag': '데이터 분석형',
        'education': '통계학 학사, 데이터분석 자격증 보유',
        'experience': '마케팅 데이터 분석 2년',
        'skills': 'SQL, 데이터 시각화, 성과 분석',
        'concern': '크리에이티브·발표에 소극적',
        'ai_note': '분석력 상 / 정량 위주 평가라 대인 역량은 덜 반영됨',
    },
    {
        'id': 'E', 'name': '정하윤', 'age': 27, 'tag': '글로벌 스펙형',
        'education': '해외 대학 마케팅 전공, 영어 능통',
        'experience': '해외 인턴 1회, 글로벌 브랜드 서포터즈',
        'skills': '영어, 글로벌 캠페인, 트렌드 감각',
        'concern': '자기주장이 강해 팀 융화에 물음표',
        'ai_note': '스펙·글로벌 역량 상 / 협업 스타일은 짧은 면접으론 판단 한계',
    },
]


def _finalize_options() -> List[Dict[str, str]]:
    """Build the 'finalize' decision cards from the candidate pool."""
    options = []
    for c in CANDIDATES:
        options.append({
            'id': c['id'],
            'label': f"지원자 {c['id']} · {c['name']} ({c['tag']})",
            'description': (f"강점: {c['skills']} · 우려: {c['concern']} · "
                            f"AI 평가: {c['ai_note']}"),
            'value': f"{c['id']} 지원자({c['name']})를 최종 합격자로 결정할게",
        })
    return options


class HiringWorkflowManager:
    """
    Drives the hiring-decision agent for PhD Study 1, V1
    (Effect of User Control — DECISIONAL control, "deciding WHAT to do").

    The participant is a hiring manager. An AI recruiting agent transparently
    analyses applicants and, at each decision point, lays out concrete options
    (as selectable cards) with their trade-offs, risks, and — importantly — the
    limits of the agent's own assessment. The manipulation is who makes the call:

      - 'decision' : the user-control group. At every decision point the USER
                     picks which option/candidate to go with. The choice is the DV.
      - 'auto'     : the no-control group. The agent decides everything itself
                     (criteria, verification, final hire) and reports it.

    Transparency (the agent's reasoning + stated uncertainty) is held constant
    across both conditions; only *who decides* varies.
    """

    PIPELINE = ['screen', 'criteria', 'verify', 'finalize', 'compile']
    DECISION_POINTS = ['criteria', 'verify', 'finalize']

    TOOL_META = {
        'screen': {'tool': 'applicant_screener', 'label': '지원자 스크리닝 엔진'},
        'criteria': {'tool': 'criteria_advisor', 'label': '평가 기준 분석기'},
        'verify': {'tool': 'verification_planner', 'label': '검증 옵션 설계기'},
        'finalize': {'tool': 'candidate_ranker', 'label': '후보 비교 분석기'},
        'compile': {'tool': 'decision_compiler', 'label': '채용 결정 정리기'},
    }

    STAGE_DESCRIPTIONS = {
        'intake': '채용 조건 확인',
        'criteria': '평가 기준 결정 중',
        'verify': '추가 검증 여부 결정 중',
        'finalize': '최종 합격자 결정 중',
        'delivered': '채용 결정 완료',
        'closed': '대화 종료',
    }

    # Stable option definitions. The workflow owns ids/labels/descriptions (so the
    # selectable cards are identical across participants and across mock/LLM mode);
    # the GPT service owns the surrounding transparent prose. `value` is the message
    # sent back when the user confirms a selection.
    DECISION_OPTIONS: Dict[str, List[Dict[str, str]]] = {
        'criteria': [
            {'id': '1', 'label': '즉시 실무 투입형',
             'description': '경력·직무 스킬을 우선. 이 기준이면 실무 경험이 많은 지원자 A가 1순위로 올라옵니다.',
             'value': '1 즉시 실무 투입형 기준으로 결정할게'},
            {'id': '2', 'label': '성장 잠재력형',
             'description': '학습력·창의성을 우선. 이 기준이면 과제 창의성이 뛰어난 지원자 B가 1순위가 됩니다.',
             'value': '2 성장 잠재력형 기준으로 결정할게'},
            {'id': '3', 'label': '조직 적합성형',
             'description': '팀워크·컬처핏을 우선. 이 기준이면 협업·소통이 강한 지원자 C가 1순위가 됩니다.',
             'value': '3 조직 적합성형 기준으로 결정할게'},
        ],
        'verify': [
            {'id': '1', 'label': '레퍼런스 체크',
             'description': '이전 직장·학교의 평판을 확인합니다. AI가 데이터로 못 본 부분(장기 근속, 실제 태도)을 보완.',
             'value': '1 레퍼런스 체크를 하고 결정할게'},
            {'id': '2', 'label': '추가 실무 과제',
             'description': '실제 업무와 유사한 과제를 부여해 검증합니다. 서류·면접만으로 부족한 실무 역량을 직접 확인.',
             'value': '2 추가 실무 과제를 내고 결정할게'},
            {'id': '3', 'label': '추가 확인 없이 바로 결정',
             'description': '지금 정보로 충분하다고 보고 바로 최종 결정으로 넘어갑니다. 빠르지만 AI 평가의 불확실성을 감수.',
             'value': '3 추가 확인 없이 바로 결정할게'},
        ],
        'finalize': _finalize_options(),
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

        if stage is None:
            return self._run_intake(conversation_id, condition, user_message)

        if stage == 'intake':
            if condition == 'auto':
                return self._run_auto_pipeline(conversation_id, user_message)
            return self._present_decision(conversation_id, condition, 'criteria',
                                          user_message, run_screen=True)

        if stage in self.DECISION_POINTS:
            return self._handle_decision(conversation_id, condition, stage, user_message)

        if stage in ('delivered', 'closed'):
            return self._handle_post_plan(conversation_id, condition, user_message)

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
        user_message: str, run_screen: bool = False
    ) -> Dict[str, Any]:
        """Show the agent's analysis for `phase` and hand the choice to the user."""
        history = self.db_manager.get_conversation_messages(conversation_id)

        actions: List[Dict[str, str]] = []
        parts: List[str] = []

        # The first decision is preceded by the transparent applicant screening.
        if run_screen:
            screen = self.gpt_service.generate_agent_response(
                condition=condition, phase='screen', user_message=user_message,
                conversation_history=history
            )
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='screen',
                user_input=user_message, gpt_response=screen,
                tool_name=self.TOOL_META['screen']['tool']
            )
            actions.append(self._action_card('screen'))
            parts.append(screen)
            history = history + [{'role': 'assistant', 'content': screen}]

        options_text = self.gpt_service.generate_agent_response(
            condition=condition, phase=phase, user_message=user_message,
            conversation_history=history
        )
        actions.append(self._action_card(phase))
        parts.append(options_text)

        response = "\n\n".join(parts)
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage=phase,
            gpt_response=options_text, tool_name=self.TOOL_META[phase]['tool']
        )
        return self._result(response, phase, condition, agent_actions=actions,
                            choices=self._decision_choices(phase), decision_mode='single')

    def _handle_decision(
        self, conversation_id: int, condition: str, stage: str, user_message: str
    ) -> Dict[str, Any]:
        chosen_id, _ = self._classify_choice(stage, user_message)

        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage=stage,
            user_input=user_message, source_selection=chosen_id,
            tool_name=self.TOOL_META[stage]['tool'], intervention_type='decide'
        )

        next_phase = self._next_decision(stage)
        if next_phase is not None:
            return self._present_decision(conversation_id, condition, next_phase, user_message)

        return self._compile_decision(conversation_id, condition, user_message)

    def _compile_decision(self, conversation_id: int, condition: str, user_message: str) -> Dict[str, Any]:
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
        """Autonomous group: the agent makes every hiring decision itself and reports."""
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
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage=log_stage,
                user_input=user_message if phase == 'screen' else None,
                gpt_response=text, tool_name=meta['tool'],
                intervention_type='agent_decided' if phase in self.DECISION_POINTS else None
            )
            working_history.append({'role': 'assistant', 'content': text})
            actions.append(self._action_card(phase))
            parts.append(f"[{meta['label']}]\n{text}")

        combined = "\n\n".join(parts) + "\n\n채용 결정을 확정했습니다. 그대로 진행하시면 됩니다."
        self.db_manager.add_message(conversation_id, 'assistant', combined)
        return self._result(combined, 'delivered', 'auto', agent_actions=actions, choices=[])

    def _handle_post_plan(self, conversation_id: int, condition: str, user_message: str) -> Dict[str, Any]:
        if condition == 'auto':
            response = "이 채용 결정은 이미 확정된 최종안입니다. 그대로 진행해 주세요."
            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='delivered',
                user_input=user_message, gpt_response=response
            )
            return self._result(response, 'delivered', 'auto', agent_actions=[], choices=[])

        target = self._match_revise_target(user_message)
        if target is not None:
            return self._present_decision(conversation_id, condition, target, user_message)

        if self._is_close(user_message):
            response = "좋습니다. 결정하신 대로 채용을 진행하세요. 바꾸고 싶은 결정이 생기면 언제든 말씀해 주세요."
            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='closed',
                user_input=user_message, gpt_response=response, intervention_type='confirm'
            )
            return self._result(response, 'closed', condition, agent_actions=[], choices=[])

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
                            agent_actions=[self._action_card('compile', label='결정 수정')],
                            choices=self._post_plan_choices(), decision_mode='single')

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
        return [dict(o) for o in self.DECISION_OPTIONS[phase]]

    def _post_plan_choices(self) -> List[Dict[str, str]]:
        return [
            {'id': 'revise_criteria', 'label': '평가 기준 다시 결정',
             'description': '어떤 기준으로 뽑을지 다시 정합니다.', 'value': '평가 기준을 다시 정하고 싶어'},
            {'id': 'revise_finalize', 'label': '최종 합격자 다시 결정',
             'description': '합격자 선택을 다시 합니다.', 'value': '최종 합격자를 다시 정하고 싶어'},
            {'id': 'done', 'label': '이대로 확정',
             'description': '결정한 대로 채용을 마무리합니다.', 'value': '이대로 확정할게'},
        ]

    def _classify_choice(self, stage: str, user_message: str) -> Tuple[str, str]:
        """Map a decision-group message to one of the stage's option ids."""
        msg = user_message.strip()
        options = self.DECISION_OPTIONS[stage]

        # 1) Explicit option id as a standalone token (1/2/3 or A/B/C/D).
        for opt in options:
            oid = opt['id']
            if re.search(rf'(?<![0-9A-Za-z]){re.escape(oid)}(?![0-9A-Za-z])', msg):
                return oid, opt['label']

        # 2) Keyword match against distinctive words.
        keyword_map = {
            'criteria': {'1': ['실무', '즉시', '경력'], '2': ['성장', '잠재', '창의'],
                         '3': ['적합', '컬처', '팀워크', '조직']},
            'verify': {'1': ['레퍼런스', '평판'], '2': ['과제', '실무 과제'],
                       '3': ['바로', '없이', '충분']},
            'finalize': {'A': ['김서연', '서연'], 'B': ['이준호', '준호'],
                         'C': ['박민지', '민지'], 'D': ['최지훈', '지훈'],
                         'E': ['정하윤', '하윤']},
        }
        low = msg.lower()
        for oid, kws in keyword_map.get(stage, {}).items():
            if any(k.lower() in low for k in kws):
                label = next((o['label'] for o in options if o['id'] == oid), oid)
                return oid, label

        # 3) Unmatched -> a custom, user-defined decision (still decisional control).
        return 'custom', msg

    def _match_revise_target(self, user_message: str) -> Optional[str]:
        msg = user_message.strip()
        if any(k in msg for k in ['기준', '평가']):
            return 'criteria'
        if any(k in msg for k in ['합격', '최종', '후보', '뽑']):
            return 'finalize'
        if any(k in msg for k in ['검증', '레퍼런스', '과제']):
            return 'verify'
        return None

    def _is_close(self, user_message: str) -> bool:
        msg = user_message.strip().lower()
        return any(k in msg for k in ['확정', '이대로', '좋아', '완료', '끝', 'ok', 'okay', '없어'])

    def _result(
        self, response: str, stage: str, condition: str,
        agent_actions: List[Dict[str, str]], choices: List[Dict[str, str]],
        decision_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        return {
            'response': response,
            'stage': stage,
            'stage_description': self.STAGE_DESCRIPTIONS.get(stage, '진행 중'),
            'condition': condition,
            'agent_actions': agent_actions,
            'choices': choices,
            'decision_mode': decision_mode,
            'awaiting_input': stage != 'closed',
        }
