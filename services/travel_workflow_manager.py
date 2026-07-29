from typing import Dict, Any, List, Optional, Tuple
from database.db_manager import DBManager


class TravelWorkflowManager:
    """
    Drives the LLM-backed travel-planner agent for PhD Study 1, V2
    (Effect of User Control — EXECUTION-VERSION control).

    Flow:
      1) Conversational intake (real LLM): the agent naturally gathers the trip
         info (destination, period, companion, style). When it has enough, it
         signals readiness.
      2) Control ('version'): the agent offers 2-3 execution versions (length /
         model / time trade-offs) and the USER picks which to run.
         No-control ('auto'): the agent says it will pick the most appropriate
         version itself.
      3) The itinerary is generated ONCE from the gathered trip info and reused
         for every version — so the deliverable is held constant per participant;
         only the control experience varies. (DV: which version was selected.)
    """

    VERSIONS: List[Dict[str, str]] = [
        {'id': '1', 'name': '빠른 추천 코스', 'length': '핵심 명소 위주', 'model': '경량 모델',
         'time': '약 20초', 'note': '필수 스팟만 간단히. 세부 동선·맛집은 생략.'},
        {'id': '2', 'name': '표준 상세 일정', 'length': '시간대별 동선', 'model': '표준 모델',
         'time': '약 1분 30초', 'note': '시간대별 동선과 맛집까지 포함한 균형 일정.'},
        {'id': '3', 'name': '실시간 맞춤형', 'length': '실시간 반영', 'model': '고급 모델 + 실시간 조회',
         'time': '약 3분', 'note': '당일 날씨·영업시간·혼잡도까지 반영. 가장 오래 걸립니다.'},
    ]
    AUTO_CHOICE = '2'

    STAGE_DESCRIPTIONS = {
        'intake': '여행 정보 수집 중',
        'offer': '실행 버전 선택 중',
        'delivered': '여행 일정 전달 완료',
        'closed': '대화 종료',
    }

    # Per-conversation caches (single-process). Keep the generated itinerary so
    # re-picking a version returns the identical deliverable.
    _trip: Dict[int, Dict[str, str]] = {}
    _itin: Dict[int, str] = {}

    INTAKE_CAP = 6  # safety: force readiness after this many user turns

    def __init__(self, gpt_service, db_manager: DBManager):
        self.gpt_service = gpt_service
        self.db_manager = db_manager

    # ------------------------------------------------------------------ #
    def start_workflow(self, conversation_id: int, user_query: str) -> Dict[str, Any]:
        return self.process_message(conversation_id, user_query)

    def process_message(self, conversation_id: int, user_message: str) -> Dict[str, Any]:
        self.db_manager.add_message(conversation_id, 'user', user_message)
        conv = self.db_manager.get_conversation(conversation_id) or {}
        condition = conv.get('condition', 'version')
        if condition not in ('version', 'auto'):
            condition = 'version'

        latest = self.db_manager.get_latest_workflow_state(conversation_id)
        stage = latest.get('stage') if latest else None

        if stage is None or stage == 'intake':
            return self._handle_intake(conversation_id, condition, user_message)
        if stage == 'offer':
            return self._handle_version_choice(conversation_id, user_message)
        if stage in ('delivered', 'closed'):
            return self._handle_post(conversation_id, condition, user_message)
        return self._handle_intake(conversation_id, condition, user_message)

    # ------------------------------------------------------------------ #
    def _handle_intake(self, conversation_id: int, condition: str, user_message: str) -> Dict[str, Any]:
        history = self.db_manager.get_conversation_messages(conversation_id)
        result = self.gpt_service.intake_turn(history, user_message)
        user_turns = sum(1 for m in history if m['role'] == 'user')

        ready = result.get('ready') or user_turns >= self.INTAKE_CAP
        visible = (result.get('text') or '').strip()

        if not ready:
            self.db_manager.add_message(conversation_id, 'assistant', visible)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='intake',
                user_input=user_message, gpt_response=visible
            )
            return self._result(visible, 'intake', condition, choices=[])

        # Ready -> resolve trip info and transition.
        trip = result.get('trip')
        if not trip or not trip.get('dest'):
            trip = self.gpt_service.extract_trip(history) or trip or {}
        self._trip[conversation_id] = trip
        if not visible:
            visible = "여행 정보를 정리했습니다."

        if condition == 'auto':
            self.db_manager.add_message(conversation_id, 'assistant', visible)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='intake',
                user_input=user_message, gpt_response=visible
            )
            return self._deliver_auto(conversation_id, visible)

        # Control: confirm + offer versions.
        offer_text = (visible + "\n\n이 정보로 일정을 준비할 수 있습니다. "
                      "아래 세 가지 버전 중 하나를 선택해 주세요. 버전에 따라 분량·사용 모델·소요 시간이 다릅니다.")
        self.db_manager.add_message(conversation_id, 'assistant', offer_text)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='offer',
            user_input=user_message, gpt_response=offer_text
        )
        return self._result(offer_text, 'offer', condition,
                            choices=self._version_choices(), decision_mode='single')

    # ------------------------------------------------------------------ #
    def _handle_version_choice(self, conversation_id: int, user_message: str) -> Dict[str, Any]:
        vid, _ = self._classify_version(user_message)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='offer',
            user_input=user_message, source_selection=vid, intervention_type='select_version'
        )
        return self._deliver(conversation_id, 'version', vid)

    def _deliver_auto(self, conversation_id: int, prior_visible: str) -> Dict[str, Any]:
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='offer',
            source_selection=self.AUTO_CHOICE, intervention_type='agent_selected'
        )
        return self._deliver(conversation_id, 'auto', self.AUTO_CHOICE, announce=True)

    def _deliver(self, conversation_id: int, condition: str, vid: str, announce: bool = False) -> Dict[str, Any]:
        itinerary = self._itin.get(conversation_id)
        if not itinerary:
            trip = self._trip.get(conversation_id, {})
            itinerary = self.gpt_service.make_itinerary(trip)
            self._itin[conversation_id] = itinerary

        version = self._version_by_id(vid)
        if condition == 'auto':
            intro = (f"제가 판단했을 때 가장 적절한 버전({version['name']})으로 준비해 드렸습니다. "
                     f"(사용 모델: {version['model']}, {version['time']})")
        else:
            intro = (f"선택하신 [{version['name']}] 버전으로 작성했습니다. "
                     f"(사용 모델: {version['model']}, {version['time']})")

        response = intro + "\n\n" + itinerary
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='delivered',
            gpt_response=response, tool_name='itinerary_writer', source_selection=vid
        )
        choices = self._post_choices() if condition == 'version' else []
        return self._result(response, 'delivered', condition,
                            choices=choices, decision_mode='single' if choices else None)

    def _handle_post(self, conversation_id: int, condition: str, user_message: str) -> Dict[str, Any]:
        if condition == 'auto':
            response = "이 일정이 최종본입니다. 즐거운 여행 되세요!"
            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='delivered',
                user_input=user_message, gpt_response=response)
            return self._result(response, 'delivered', 'auto', choices=[])

        if self._is_close(user_message):
            response = "좋습니다. 이 일정으로 마무리하겠습니다. 즐거운 여행 되세요!"
            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='closed',
                user_input=user_message, gpt_response=response, intervention_type='confirm')
            return self._result(response, 'closed', 'version', choices=[])

        # Re-open version selection (same itinerary will be reused).
        text = "다른 버전으로 다시 준비할 수 있습니다. 아래에서 선택해 주세요."
        self.db_manager.add_message(conversation_id, 'assistant', text)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='offer',
            user_input=user_message, gpt_response=text)
        return self._result(text, 'offer', 'version',
                            choices=self._version_choices(), decision_mode='single')

    # ------------------------------------------------------------------ #
    def _version_choices(self) -> List[Dict[str, str]]:
        return [{
            'id': v['id'],
            'label': f"{v['name']} · {v['time'].replace('약 ', '')}",
            'description': f"분량 {v['length']} · 모델 {v['model']} · {v['note']}",
            'value': f"{v['id']} {v['name']} 버전으로 생성해줘",
        } for v in self.VERSIONS]

    def _post_choices(self) -> List[Dict[str, str]]:
        return [
            {'id': 'other', 'label': '다른 버전으로 다시 생성',
             'description': '분량·모델·소요 시간이 다른 버전을 다시 골라 생성합니다.',
             'value': '다른 버전으로 다시 생성해줘'},
            {'id': 'done', 'label': '이대로 확정',
             'description': '이 일정으로 마무리합니다.', 'value': '이대로 확정할게'},
        ]

    def _version_by_id(self, vid: str) -> Dict[str, str]:
        for v in self.VERSIONS:
            if v['id'] == vid:
                return v
        return self.VERSIONS[int(self.AUTO_CHOICE) - 1]

    def _classify_version(self, user_message: str) -> Tuple[str, str]:
        msg = user_message.strip()
        for v in self.VERSIONS:
            if v['id'] in msg:
                return v['id'], v['name']
        mapping = {'1': ['빠른', '추천', '간단'], '2': ['표준', '상세', '균형'], '3': ['실시간', '맞춤', '심층']}
        for vid, kws in mapping.items():
            if any(k in msg for k in kws):
                return vid, self._version_by_id(vid)['name']
        return self.AUTO_CHOICE, self._version_by_id(self.AUTO_CHOICE)['name']

    def _is_close(self, user_message: str) -> bool:
        msg = user_message.strip().lower()
        return any(k in msg for k in ['확정', '이대로', '좋아', '완료', '끝', 'ok', 'okay', '없어', '고마'])

    def _result(self, response: str, stage: str, condition: str,
                choices: List[Dict[str, str]], decision_mode: Optional[str] = None) -> Dict[str, Any]:
        return {
            'response': response,
            'stage': stage,
            'stage_description': self.STAGE_DESCRIPTIONS.get(stage, '진행 중'),
            'condition': condition,
            'agent_actions': [],
            'choices': choices,
            'decision_mode': decision_mode,
            'awaiting_input': stage != 'closed',
        }
