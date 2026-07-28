"""
Mock GPT service for the personal-finance allocation agent (PhD Study 1, V1 —
decisional control) so the experiment UI and condition logic can be exercised
end-to-end without an API key.

Content is fixed/deterministic on purpose: in a clean experiment the plan and its
reasoning should be constant across participants so that only *who decides* varies.
Mirrors FinanceGPTService.generate_agent_response.
"""

from typing import List, Dict, Optional


class FinanceMockService:
    """Simulates the finance allocation agent without calling OpenAI."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or "mock-api-key"
        self.model = "finance-agent (mock)"

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
                "앞으로의 자산 배분 계획을 함께 세워보겠습니다. 매달 생기는 여윳돈을 "
                "부채 상환·비상금·투자에 어떻게 나눌지 정하는 것이 목표입니다.\n\n"
                "계획을 맞추기 위해 몇 가지만 알려주세요.\n"
                "1. 갚고 있는 대출/부채가 있나요? (금액과 대략적인 금리)\n"
                "2. 매달 남는 여윳돈은 어느 정도인가요?\n"
                "3. 위험을 감수하는 편인가요, 안정을 선호하는 편인가요?\n"
                "4. (선택) 곧 큰 지출 예정이 있나요? 없으면 일반적인 가정으로 진행할게요."
            )

        if phase == 'diagnose':
            return (
                "재무 상황 진단기를 실행했습니다.\n"
                "- 가정: 월 여윳돈 100만원, 신용/학자금 부채 1,200만원(금리 약 7%), 비상금 현재 0원\n"
                "- 핵심 이슈: 부채 금리(7%)가 예금 이자(3~4%)보다 높아, 갚을수록 확정 수익 효과가 납니다.\n"
                "- 다만 비상금이 없어, 갑작스러운 지출 시 다시 빚을 낼 위험이 있습니다.\n"
                "- 즉 '부채 상환'과 '비상금 확보'가 충돌하며, 어디에 무게를 둘지는 가치관에 달려 있습니다."
            )

        if phase == 'allocate':
            body = (
                "여윳돈 배분안 생성기를 실행했습니다. 월 100만원을 나누는 세 가지 방식입니다.\n\n"
                "1) 부채 우선 상환형 — 부채 70 / 비상금 30 / 투자 0\n"
                "   - 이자 부담을 가장 빠르게 줄임(확정 절감). 대신 자산 증식은 늦음.\n"
                "2) 균형형 — 부채 40 / 비상금 30 / 투자 30\n"
                "   - 상환·안전·증식을 고루. 어느 쪽도 최고는 아니지만 리스크가 분산됨.\n"
                "3) 투자 우선형 — 부채 20 / 비상금 20 / 투자 60\n"
                "   - 장기 수익 기대가 가장 큼. 대신 부채 이자와 투자 손실 위험을 함께 짊어짐."
            )
            if is_auto:
                return body + "\n\n저는 2번 균형형으로 결정했습니다(리스크 분산). 다음 단계로 넘어가겠습니다."
            return body + "\n\n어떤 방식으로 하시겠어요? 결정은 당신의 몫입니다. 번호를 골라 주세요."

        if phase == 'emergency':
            body = (
                "비상금 설계기를 실행했습니다. 비상금을 얼마나 쌓을지 세 가지 목표입니다.\n\n"
                "1) 탄탄하게 — 6개월치 생활비(약 1,200만원)\n"
                "   - 실직·큰 지출에도 버팀. 대신 그만큼 상환/투자에 쓸 돈이 늦게 풀림.\n"
                "2) 적정 — 3개월치(약 600만원)\n"
                "   - 일반적으로 권장되는 수준. 안전과 기회비용의 절충.\n"
                "3) 최소 — 1개월치(약 200만원)\n"
                "   - 상환/투자에 자금을 몰아줌. 대신 예기치 못한 지출에 취약."
            )
            if is_auto:
                return body + "\n\n저는 2번 3개월치로 결정했습니다(표준 권장치). 다음 단계로 넘어가겠습니다."
            return body + "\n\n비상금 목표를 얼마로 하시겠어요? 번호를 골라 주세요."

        if phase == 'invest':
            body = (
                "투자 옵션 분석기를 실행했습니다. 투자에 배정한 돈의 운용 방향입니다.\n\n"
                "1) 안정형 — 예금·국채 (연 3~4%, 원금 손실 거의 없음)\n"
                "   - 변동성이 낮아 마음 편함. 대신 물가상승률을 겨우 따라가는 수준.\n"
                "2) 중립형 — 인덱스 ETF (장기 연 6~8% 기대, 중간 변동성)\n"
                "   - 시장 평균을 따라감. 단기 등락은 있지만 장기 분산 효과.\n"
                "3) 공격형 — 성장주·테마 (기대수익도 손실 위험도 큼)\n"
                "   - 크게 벌 수도, 크게 잃을 수도. 원금 변동을 견딜 수 있어야 함."
            )
            if is_auto:
                return body + "\n\n저는 2번 중립형(인덱스 ETF)으로 결정했습니다. 계획을 정리하겠습니다."
            return body + "\n\n투자 성향을 어떻게 하시겠어요? 번호를 골라 주세요."

        if phase == 'compile':
            if is_auto:
                return (
                    "계획 통합기를 실행해 최종 배분 계획을 정리했습니다.\n\n"
                    "핵심 요약(에이전트 결정)\n"
                    "- 월 배분: 부채 40 / 비상금 30 / 투자 30 (균형형)\n"
                    "- 비상금 목표: 3개월치(약 600만원)\n"
                    "- 투자: 인덱스 ETF 중립형\n"
                    "- 6개월 예상: 부채 약 240만원 감소, 비상금 약 180만원 적립, 투자 원금 약 180만원\n\n"
                    "안내: 실제 수치는 시장 상황에 따라 달라질 수 있습니다."
                )
            return (
                "계획 통합기를 실행해, 당신이 결정한 내용으로 최종 배분 계획을 정리했습니다.\n\n"
                "핵심 요약(당신의 결정 기준)\n"
                "- 월 배분: 앞서 고른 배분 방식대로 매달 100만원을 나눕니다.\n"
                "- 비상금: 고른 목표 규모까지 우선 적립합니다.\n"
                "- 투자: 고른 성향에 맞는 상품으로 운용합니다.\n"
                "- 6개월 뒤 대략적인 결과를 위 기준으로 추정할 수 있습니다.\n\n"
                "안내: 실제 수치는 시장 상황에 따라 달라질 수 있습니다. "
                "바꾸고 싶은 결정이 있으면 말씀해 주세요."
            )

        if phase == 'revise':
            return (
                f"요청하신 부분을 반영했습니다: {override_instruction or user_message}\n"
                "- 해당 결정만 바꾸고 나머지 배분은 그대로 유지됩니다.\n\n"
                "추가로 다시 정하고 싶은 결정이 있나요?"
            )

        return f"'{user_message}'에 대해 배분 계획을 도와드리겠습니다."
