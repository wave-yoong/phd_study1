"""
Mock GPT Service for testing the diet/exercise planning agent without an API key.

Mirrors GPTService.generate_agent_response so the experiment UI and condition
logic can be exercised end-to-end in demo mode.
"""

from typing import List, Dict, Optional


class MockGPTService:
    """Mock service that simulates the planning agent without calling OpenAI."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or "mock-api-key"
        self.model = "diet-agent (mock)"

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
        override_instruction: Optional[str] = None,
        profile: Optional[str] = None
    ) -> str:
        is_auto = (condition == 'auto') or (autonomy_level == 'high')

        if phase == 'intake':
            return (
                "2주간 건강한 생활 루틴(식단·운동·수면)을 함께 설계해 드릴게요.\n\n"
                "맞춤 설계를 위해 몇 가지만 알려주세요.\n"
                "1. 이번 2주에 가장 중요한 건강 목표는 무엇인가요? (체중 감량은 선택)\n"
                "2. 좋아하거나 피하고 싶은 음식, 알레르기가 있나요?\n"
                "3. 운동 가능한 요일과 시간대는 어떻게 되나요?\n"
                "4. 평소 수면 습관은 어떤가요?"
            )

        if phase == 'calc':
            body = (
                "영양·에너지 가이드를 실행했습니다.\n"
                "- 가정: 성인 기준 활동량 보통, 건강 유지 중심\n"
                "- 하루 권장 섭취: 약 1,900 kcal\n"
                "- 영양 비율: 탄수화물 45 / 단백질 30 / 지방 25\n"
                "- 수분: 하루 약 1.5~2L\n"
                "- 체중 감량을 원하실 경우에만 하루 약 200~300kcal 정도 가볍게 조정 가능"
            )
            return body + ("\n\n이 가이드로 식단 구성을 진행하겠습니다." if is_auto
                           else "\n\n이 영양 가이드로 진행할까요, 아니면 조정할 부분이 있나요?")

        if phase == 'meal':
            body = (
                "식단 데이터베이스를 조회했습니다.\n"
                "구성 원칙: 균형 잡힌 영양, 가공식품 최소화, 규칙적인 식사\n"
                "하루 예시\n"
                "- 아침: 그릭요거트 + 베리 + 견과 약간\n"
                "- 점심: 현미밥 + 닭가슴살(또는 두부) + 샐러드\n"
                "- 저녁: 채소볶음 + 미역국 + 잡곡밥\n"
                "- 간식: 방울토마토, 삶은 달걀"
            )
            return body + ("\n\n이 구성으로 운동 루틴을 설계하겠습니다." if is_auto
                           else "\n\n이 식단 방향이 괜찮으신가요? 바꾸고 싶은 메뉴가 있으면 말씀해 주세요.")

        if phase == 'workout':
            body = (
                "운동 루틴 설계기를 실행했습니다.\n"
                "원칙: 주 5일 활동, 2일 휴식. 유산소 + 근력 병행\n"
                "- 월/목: 전신 근력 30분\n"
                "- 화/금: 유산소 40분(빠르게 걷기/조깅)\n"
                "- 토: 가벼운 활동(스트레칭/산책)\n"
                "- 수/일: 휴식일로 배치했습니다"
            )
            return body + ("\n\n이 루틴으로 수면·생활습관을 설계하겠습니다." if is_auto
                           else "\n\n휴식일 배치나 운동 종류를 바꾸고 싶으면 말씀해 주세요.")

        if phase == 'sleep':
            body = (
                "수면·생활습관 설계기를 실행했습니다.\n"
                "- 권장 수면: 취침 23:30 / 기상 07:00 (약 7시간 30분)\n"
                "- 취침 1시간 전 스크린 줄이기, 오후 2시 이후 카페인 자제\n"
                "- 아침 기상 후 물 한 잔, 가벼운 스트레칭 5분\n"
                "- 하루 한 번 10분 산책으로 스트레스 관리"
            )
            return body + ("\n\n이 루틴으로 2주 일정을 편성하겠습니다." if is_auto
                           else "\n\n수면 시간대나 생활습관을 조정하고 싶으면 말씀해 주세요.")

        if phase == 'schedule':
            lines = ["일정 편성기를 실행해 2주 루틴을 편성했습니다.\n"]
            for d in range(1, 15):
                rest = (d % 7 in (3, 0))
                workout = "휴식" if rest else ("근력 30분" if d % 2 else "유산소 40분")
                lines.append(
                    f"{d}일차: 식단 균형식 / 운동 {workout} / "
                    f"수면 23:30-07:00{', 컨디션 점검' if d in (1, 8, 14) else ', 스트레칭 5분'}"
                )
            body = "\n".join(lines)
            return body + ("\n\n이대로 장보기 리스트까지 생성하겠습니다." if is_auto
                           else "\n\n특정 날짜를 바꾸고 싶으면 'N일차 ...' 형태로 말씀해 주세요.")

        if phase == 'grocery':
            body = (
                "장보기 리스트 생성기를 실행했습니다(1주차 기준).\n"
                "단백질: 닭가슴살 5팩, 두부 4모, 달걀 1판, 그릭요거트 7개\n"
                "채소: 샐러드 채소, 브로콜리, 미역, 방울토마토\n"
                "탄수화물: 현미 1kg, 고구마 7개\n"
                "기타: 견과류, 올리브유, 베리류"
            )
            return body + ("\n\n루틴을 최종 정리하겠습니다." if is_auto
                           else "\n\n빠진 품목이 있으면 알려주세요.")

        if phase == 'delivery':
            return (
                "2주 건강 루틴을 최종 정리했습니다.\n\n"
                "핵심 요약\n"
                "- 목표: 전반적인 컨디션 향상 (체중 감량은 선택적으로 반영)\n"
                "- 식단: 하루 약 1,900kcal, 균형 잡힌 구성\n"
                "- 운동: 주 5일(근력+유산소), 수/일 휴식\n"
                "- 수면·생활습관: 취침 23:30 / 기상 07:00, 스트레칭·산책 루틴\n"
                "- 1주차 장보기 리스트 포함\n\n"
                "일자별 루틴은 위 일정 편성 결과를 따르고, 1·8·14일차에 컨디션을 점검하세요.\n\n"
                "안전 안내: 무리한 절식은 피하고, 어지럼증 등 이상이 있으면 강도를 낮추세요. "
                "지속 가능한 습관이 가장 중요합니다."
            )

        if phase == 'override':
            return (
                f"요청하신 부분을 수정했습니다: {override_instruction or user_message}\n"
                "- 해당 항목만 교체했고 나머지 루틴은 그대로 유지됩니다.\n\n"
                "추가로 바꾸고 싶은 부분이 있나요?"
            )

        if phase == 'interrupt':
            return (
                f"네, 말씀하신 내용 확인했습니다: {user_message}\n"
                "현재 루틴 편성을 잠시 멈춘 상태입니다. 계속 진행할까요?"
            )

        return f"'{user_message}'에 대해 루틴 설계를 도와드리겠습니다."
