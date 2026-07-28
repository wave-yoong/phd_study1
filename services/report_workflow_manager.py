import re
from typing import Dict, Any, List, Optional, Tuple
from database.db_manager import DBManager


# ---------------------------------------------------------------------------
# The FIXED deliverable. By design, every participant sees the exact same report
# regardless of which version they pick (control group) or what the agent picks
# for them (auto group). Only the *control experience* (choosing the execution
# version) is manipulated; the output is held constant.
# Figures are illustrative research stimuli, not real market data.
# ---------------------------------------------------------------------------
REPORT_TEXT = """2026년 1분기 국내·해외 증시 현황 분석 보고서

1. 요약
- 2026년 1분기 글로벌 증시는 금리 인하 기대와 AI 관련 투자 지속으로 전반적인 상승세를 보였습니다.
- 국내 증시는 반도체 업황 회복에 힘입어 코스피가 분기 중 상승했으나, 원/달러 환율 변동성이 변수로 작용했습니다.

2. 국내 증시
- 코스피: 분기 초 약 2,600선에서 출발해 반도체·2차전지 강세로 2,800선 부근까지 상승, 분기 등락률 약 +7퍼센트.
- 코스닥: 개인 수급과 바이오·AI 소프트웨어 테마로 변동성이 확대되며 분기 등락률 약 +5퍼센트.
- 주요 이슈: 반도체 대형주의 실적 개선 기대와 외국인 순매수 전환이 지수를 견인.

3. 해외 증시
- 미국: S&P500과 나스닥이 AI·기술주 주도로 사상 최고치 부근까지 상승, 연준의 금리 인하 신호가 위험자산 선호를 강화.
- 일본·유럽: 닛케이는 엔화 약세와 기업 지배구조 개선 기대로 강세, 유럽은 경기 둔화 우려로 상대적 약세.
- 중국: 부동산 부진이 이어졌으나 경기 부양책 기대로 반등을 시도.

4. 섹터 동향
- 강세: 반도체, AI 인프라, 방산.
- 혼조·약세: 소비재, 전통 에너지.

5. 리스크 요인
- 원/달러 환율 변동성, 지정학적 리스크, 금리 인하 시점의 불확실성.

6. 전망
- 2분기에도 AI 투자 사이클과 반도체 업황이 핵심 변수로 작용할 전망입니다.
- 다만 밸류에이션 부담과 환율 흐름에 따라 변동성이 확대될 수 있어 분산 관점의 접근이 권장됩니다.

(주) 본 보고서는 연구용으로 작성된 예시이며, 수치는 실제 시장 데이터가 아닌 가상의 예시입니다."""


class StockReportWorkflowManager:
    """
    Drives the stock-market report agent for PhD Study 1, V2
    (Effect of User Control — EXECUTION-VERSION control).

    Same agentic task for everyone: write a report on 2026 Q1 Korean domestic /
    overseas stock-market conditions. The manipulation is who selects the
    execution version:

      - 'version' : the user-control group. The agent offers 2-3 versions, each
                    labelled with its length / model / expected time trade-offs,
                    and the USER picks which version to run. The choice is the DV.
      - 'auto'    : the no-control group. The agent says it will pick "the most
                    appropriate version" itself and proceeds.

    Crucially, the FINAL REPORT is identical across every version and both
    conditions (REPORT_TEXT). Only the control experience varies; the output is
    held constant. This workflow therefore uses fixed strings (no LLM) so the
    deliverable can never drift between participants.
    """

    # Execution versions shown to the control group (stable ids/attributes).
    VERSIONS: List[Dict[str, str]] = [
        {
            'id': '1', 'name': '빠른 요약본',
            'length': 'A4 약 1장 (약 800자)',
            'model': '경량 모델 (빠른 응답)',
            'time': '예상 소요 약 20초',
            'note': '핵심 지표와 결론 위주로 빠르게. 깊이는 얕습니다.',
        },
        {
            'id': '2', 'name': '표준 분석본',
            'length': 'A4 약 2~3장 (약 2,000자)',
            'model': '표준 모델 (균형)',
            'time': '예상 소요 약 1분 30초',
            'note': '섹터·주요 이슈 분석까지 포함한 균형 잡힌 보고서.',
        },
        {
            'id': '3', 'name': '실시간 심층본',
            'length': 'A4 약 3장 이상 (약 3,000자)',
            'model': '고급 모델 + 실시간 시세·뉴스 조회',
            'time': '예상 소요 약 3분',
            'note': '최신 데이터를 반영한 심층 분석. 대신 가장 오래 걸립니다.',
        },
    ]

    # The version the agent "chooses" for the no-control group.
    AUTO_CHOICE = '2'

    TOOL_META = {
        'collect': {'tool': 'market_data_collector', 'label': '시장 데이터 수집'},
        'analyze': {'tool': 'market_analyzer', 'label': '증시 분석'},
        'write': {'tool': 'report_writer', 'label': '보고서 작성'},
    }

    STAGE_DESCRIPTIONS = {
        'offer': '실행 버전 선택 중',
        'delivered': '보고서 전달 완료',
        'closed': '대화 종료',
    }

    def __init__(self, gpt_service, db_manager: DBManager):
        # gpt_service is accepted for interface symmetry but intentionally unused:
        # the deliverable must be identical across participants, so all text is fixed.
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
        condition = conv.get('condition', 'version')
        if condition not in ('version', 'auto'):
            condition = 'version'

        latest = self.db_manager.get_latest_workflow_state(conversation_id)
        stage = latest.get('stage') if latest else None

        if stage is None:
            if condition == 'auto':
                return self._deliver_auto(conversation_id, user_message)
            return self._offer_versions(conversation_id, user_message)

        if stage == 'offer':
            return self._handle_version_choice(conversation_id, user_message)

        if stage in ('delivered', 'closed'):
            return self._handle_post(conversation_id, condition, user_message)

        return self._offer_versions(conversation_id, user_message)

    # ------------------------------------------------------------------ #
    # Control group: offer versions -> user picks -> deliver (same report)
    # ------------------------------------------------------------------ #
    def _offer_versions(self, conversation_id: int, user_message: str) -> Dict[str, Any]:
        lines = ["요청하신 '2026년 1분기 국내·해외 증시 현황 보고서'를 준비할 수 있습니다.",
                 "아래 세 가지 버전 중 하나를 선택해 주세요. 버전에 따라 분량·사용 모델·소요 시간이 다릅니다.\n"]
        for v in self.VERSIONS:
            lines.append(
                f"{v['id']}) {v['name']}\n"
                f"   - 분량: {v['length']}\n"
                f"   - 사용 모델: {v['model']}\n"
                f"   - {v['time']}\n"
                f"   - {v['note']}"
            )
        response = "\n".join(lines) + "\n\n어떤 버전으로 진행할까요? 선택은 당신의 몫입니다."

        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='offer',
            user_input=user_message, gpt_response=response
        )
        return self._result(response, 'offer', 'version',
                            agent_actions=[], choices=self._version_choices(),
                            decision_mode='single')

    def _handle_version_choice(self, conversation_id: int, user_message: str) -> Dict[str, Any]:
        vid, _ = self._classify_version(user_message)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='offer',
            user_input=user_message, source_selection=vid,
            intervention_type='select_version'
        )
        return self._deliver(conversation_id, 'version', vid, user_message)

    # ------------------------------------------------------------------ #
    # No-control group: agent picks a version itself and delivers (same report)
    # ------------------------------------------------------------------ #
    def _deliver_auto(self, conversation_id: int, user_message: str) -> Dict[str, Any]:
        # Log the agent's own version choice for symmetry with the DV.
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='offer',
            user_input=user_message, source_selection=self.AUTO_CHOICE,
            intervention_type='agent_selected'
        )
        return self._deliver(conversation_id, 'auto', self.AUTO_CHOICE, user_message)

    # ------------------------------------------------------------------ #
    # Shared delivery — identical REPORT_TEXT regardless of version/condition
    # ------------------------------------------------------------------ #
    def _deliver(self, conversation_id: int, condition: str, vid: str, user_message: str) -> Dict[str, Any]:
        version = self._version_by_id(vid)
        if condition == 'auto':
            intro = (f"제가 판단했을 때 가장 적절한 버전({version['name']})으로 준비해 드렸습니다. "
                     f"(사용 모델: {version['model']}, {version['time']})")
        else:
            intro = (f"선택하신 [{version['name']}] 버전으로 작성했습니다. "
                     f"(사용 모델: {version['model']}, {version['time']})")

        response = intro + "\n\n" + REPORT_TEXT
        self.db_manager.add_message(conversation_id, 'assistant', response)
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id, stage='delivered',
            gpt_response=response, tool_name=self.TOOL_META['write']['tool'],
            source_selection=vid
        )
        actions = [self._action_card('collect'), self._action_card('analyze'), self._action_card('write')]
        choices = self._post_choices() if condition == 'version' else []
        return self._result(response, 'delivered', condition,
                            agent_actions=actions, choices=choices,
                            decision_mode='single' if choices else None)

    def _handle_post(self, conversation_id: int, condition: str, user_message: str) -> Dict[str, Any]:
        if condition == 'auto':
            response = "이 보고서가 최종본입니다. 도움이 되었길 바랍니다."
            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='delivered',
                user_input=user_message, gpt_response=response
            )
            return self._result(response, 'delivered', 'auto', agent_actions=[], choices=[])

        # Control group: re-open version selection, or close.
        if self._wants_other_version(user_message):
            return self._offer_versions(conversation_id, user_message)

        if self._is_close(user_message):
            response = "좋습니다. 이 보고서로 마무리하겠습니다. 다른 버전이 필요하면 언제든 말씀해 주세요."
            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id, stage='closed',
                user_input=user_message, gpt_response=response, intervention_type='confirm'
            )
            return self._result(response, 'closed', 'version', agent_actions=[], choices=[])

        # Anything else -> offer the versions again.
        return self._offer_versions(conversation_id, user_message)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _version_choices(self) -> List[Dict[str, str]]:
        return [
            {
                'id': v['id'],
                'label': f"{v['name']} · {v['time'].replace('예상 소요 ', '')}",
                'description': f"분량 {v['length']} · 모델 {v['model']} · {v['note']}",
                'value': f"{v['id']} {v['name']} 버전으로 생성해줘",
            }
            for v in self.VERSIONS
        ]

    def _post_choices(self) -> List[Dict[str, str]]:
        return [
            {'id': 'other', 'label': '다른 버전으로 다시 생성',
             'description': '분량·모델·소요 시간이 다른 버전을 다시 골라 생성합니다.',
             'value': '다른 버전으로 다시 생성해줘'},
            {'id': 'done', 'label': '이대로 확정',
             'description': '이 보고서로 마무리합니다.', 'value': '이대로 확정할게'},
        ]

    def _action_card(self, phase: str) -> Dict[str, str]:
        meta = self.TOOL_META[phase]
        return {'tool': meta['tool'], 'label': meta['label'], 'status': '완료'}

    def _version_by_id(self, vid: str) -> Dict[str, str]:
        for v in self.VERSIONS:
            if v['id'] == vid:
                return v
        return self.VERSIONS[int(self.AUTO_CHOICE) - 1]

    def _classify_version(self, user_message: str) -> Tuple[str, str]:
        msg = user_message.strip()
        for v in self.VERSIONS:
            if re.search(rf'(?<![0-9]){v["id"]}(?![0-9])', msg):
                return v['id'], v['name']
        keyword_map = {'1': ['빠른', '요약'], '2': ['표준', '균형'], '3': ['실시간', '심층']}
        for vid, kws in keyword_map.items():
            if any(k in msg for k in kws):
                return vid, self._version_by_id(vid)['name']
        return self.AUTO_CHOICE, self._version_by_id(self.AUTO_CHOICE)['name']

    def _wants_other_version(self, user_message: str) -> bool:
        msg = user_message.strip()
        return any(k in msg for k in ['다른 버전', '다시', '바꿔', '변경', '버전'])

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
