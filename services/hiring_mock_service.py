"""
Mock GPT service for the hiring-decision agent (PhD Study 1, V1 — decisional
control) so the experiment UI and condition logic can be exercised without an
API key.

Content is fixed/deterministic on purpose: in a clean experiment the applicant
pool and the agent's reasoning should be constant across participants so that
only *who decides* varies. The clickable option cards themselves are supplied by
HiringWorkflowManager; this service only produces the surrounding prose.
Mirrors HiringGPTService.generate_agent_response.
"""

from typing import List, Dict, Optional


class HiringMockService:
    """Simulates the hiring agent without calling OpenAI."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or "mock-api-key"
        self.model = "hiring-agent (mock)"

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 900
    ) -> str:
        last_message = messages[-1]['content'] if messages else ""
        return f"[MOCK] 시뮬레이션 응답입니다: '{last_message[:60]}'"

    def generate_agent_response(
        self,
        condition: str,
        phase: str,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        autonomy_level: str = 'low',
        override_instruction: Optional[str] = None
    ) -> str:
        is_auto = (condition == 'auto')

        if phase == 'intake':
            return (
                "마케팅팀 신입 1명 채용을 도와드리겠습니다. 지원자들의 서류·실무 과제·면접 "
                "기록을 분석해 정리하고, 결정에 필요한 정보를 투명하게 보여드릴게요.\n\n"
                "먼저 몇 가지만 확인할게요.\n"
                "1. 이 자리에서 가장 중요하게 보는 점은 무엇인가요? (예: 실무 즉시전력 / 성장 잠재력 / 팀 적합성)\n"
                "2. 특별히 걸러야 할 조건이 있나요? (예: 최소 경력, 필수 스킬)\n"
                "없으면 일반적인 신입 채용 기준으로 분석을 시작하겠습니다."
            )

        if phase == 'screen':
            return (
                "지원자 스크리닝 엔진을 실행했습니다. (사용 데이터: 서류, 실무 과제 점수, 면접관 메모)\n"
                "최종 검토 대상 4명으로 압축했습니다.\n"
                "- 지원자 A 김서연: 실무 경험 많음(인턴 2회). 다만 이직이 잦음.\n"
                "- 지원자 B 이준호: 과제 창의성 최고, 실무 경험은 적음.\n"
                "- 지원자 C 박민지: 팀워크·소통 강점, 뾰족한 전문성은 부족.\n"
                "- 지원자 D 최지훈: 데이터 분석 강점, 크리에이티브는 약함.\n\n"
                "투명성 안내: 이 요약은 정량 점수와 면접 메모에 기반합니다. 면접 인상은 주관적일 수 있고, "
                "표본이 작아 '잠재력' 같은 예측은 불확실합니다. 참고 자료로만 사용해 주세요."
            )

        if phase == 'criteria':
            body = (
                "평가 기준 분석기를 실행했습니다. 무엇을 우선하느냐에 따라 1순위 후보가 실제로 달라집니다.\n\n"
                "1) 즉시 실무 투입형 (경력·직무 스킬 우선) → 이 기준이면 지원자 A가 1순위\n"
                "2) 성장 잠재력형 (학습력·창의성 우선) → 이 기준이면 지원자 B가 1순위\n"
                "3) 조직 적합성형 (팀워크·컬처핏 우선) → 이 기준이면 지원자 C가 1순위\n\n"
                "어느 기준이 '정답'인지는 회사 상황과 가치관에 달려 있습니다."
            )
            if is_auto:
                return body + "\n\n저는 1번 즉시 실무 투입형을 기준으로 정했습니다. 다음 단계로 넘어가겠습니다."
            return body + "\n\n어떤 기준으로 보시겠어요? 결정은 당신의 몫입니다. 카드에서 골라 주세요."

        if phase == 'verify':
            body = (
                "검증 옵션 설계기를 실행했습니다. 최종 결정 전에 무엇을 더 확인할지 정할 수 있습니다.\n\n"
                "1) 레퍼런스 체크 — 이전 직장·학교 평판 확인 (AI가 못 본 태도·근속 정보 보완)\n"
                "2) 추가 실무 과제 — 실제 업무 유사 과제로 역량 직접 검증\n"
                "3) 추가 확인 없이 바로 결정 — 지금 정보로 충분하다고 판단\n\n"
                "투명성 안내: 제 평가에는 불확실성이 있습니다. 더 확인할수록 확신은 커지지만 시간이 듭니다."
            )
            if is_auto:
                return body + "\n\n저는 1번 레퍼런스 체크를 하기로 정했습니다. 다음 단계로 넘어가겠습니다."
            return body + "\n\n무엇을 더 확인하시겠어요? 카드에서 골라 주세요."

        if phase == 'finalize':
            body = (
                "후보 비교 분석기를 실행했습니다. 최종 후보 4명을 강점·우려·제 평가의 한계와 함께 정리했습니다.\n\n"
                "A) 김서연 — 실무 즉시전력. 강점: 캠페인 실전 경험. 우려: 잦은 이직. 한계: 장기 근속 예측 어려움.\n"
                "B) 이준호 — 성장 잠재력. 강점: 창의성 1위, 학습 빠름. 우려: 실무 미검증. 한계: 잠재력은 예측치.\n"
                "C) 박민지 — 조직 적합성. 강점: 소통·협업, 면접 호감. 우려: 전문성 평범. 한계: 면접 인상은 주관적.\n"
                "D) 최지훈 — 데이터 분석. 강점: 분석·성실. 우려: 크리에이티브 약함. 한계: 대인 역량 덜 반영됨."
            )
            if is_auto:
                return body + "\n\n저는 A 김서연을 최종 합격자로 결정했습니다(실무 즉시전력 기준). 결정을 정리하겠습니다."
            return body + "\n\n누구를 최종 합격자로 하시겠어요? 카드에서 한 명을 골라 주세요."

        if phase == 'compile':
            if is_auto:
                return (
                    "채용 결정 정리기를 실행했습니다.\n\n"
                    "최종 결정(에이전트 판단)\n"
                    "- 평가 기준: 즉시 실무 투입형\n"
                    "- 검증: 레퍼런스 체크 완료\n"
                    "- 최종 합격자: 지원자 A 김서연\n"
                    "- 근거: 실무 즉시전력이 이 자리에 가장 부합.\n\n"
                    "안내: 이 결정은 제공된 데이터에 기반하며, 최종 책임 판단은 사람이 확인하는 것을 권장합니다."
                )
            return (
                "채용 결정 정리기를 실행해, 당신이 결정한 내용으로 채용 결정서를 정리했습니다.\n\n"
                "최종 결정(당신의 판단)\n"
                "- 평가 기준: 앞서 고른 기준\n"
                "- 검증: 고른 검증 방식대로 진행\n"
                "- 최종 합격자: 당신이 선택한 지원자\n\n"
                "안내: 이 결정은 제공된 데이터에 기반합니다. 바꾸고 싶은 결정이 있으면 말씀해 주세요."
            )

        if phase == 'revise':
            return (
                f"요청하신 부분을 반영했습니다: {override_instruction or user_message}\n"
                "- 해당 결정만 다시 열고, 나머지는 그대로 유지됩니다.\n\n"
                "추가로 다시 정하고 싶은 결정이 있나요?"
            )

        return f"'{user_message}'에 대해 채용 결정을 도와드리겠습니다."
