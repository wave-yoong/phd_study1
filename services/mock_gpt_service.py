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
        goal, focus = self._detect_goal(profile, user_message)

        # The user asked WHY about the current step -> explain with reasoning.
        if override_instruction and override_instruction.startswith('__QUESTION__'):
            return self._explain(phase)

        def finish(body, auto_tail, ctrl_tail):
            # In the control group a "modify" request arrives as override_instruction;
            # reflect it so the change is visibly applied (demo mode is otherwise fixed).
            if override_instruction:
                return (
                    f"요청을 반영해 수정했습니다.\n반영 내용: {override_instruction}\n\n"
                    + body
                    + "\n\n위 내용에 요청하신 부분을 반영했어요. 이대로 진행할까요, 더 바꿀 부분이 있나요?"
                )
            return body + ("\n\n" + auto_tail if is_auto else "\n\n" + ctrl_tail)

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
            weight_line = ("- 가벼운 체중 조정을 위해 하루 약 200~300kcal 줄인 기준으로 잡았습니다"
                           if goal == '체중 감량'
                           else "- 체중 감량이 목표가 아니므로 균형 유지 기준으로 잡았습니다")
            body = (
                f"영양·에너지 가이드를 실행했습니다.\n"
                f"선택하신 목표: {goal}\n"
                "- 가정: 성인 기준 활동량 보통\n"
                "- 하루 권장 섭취: 약 1,900 kcal\n"
                "- 영양 비율: 탄수화물 45 / 단백질 30 / 지방 25\n"
                "- 수분: 하루 약 1.5~2L\n"
                f"{weight_line}"
            )
            return finish(body, "이 가이드로 식단 구성을 진행하겠습니다.",
                          "이 영양 가이드로 진행할까요, 아니면 조정할 부분이 있나요?")

        if phase == 'meal':
            body = (
                f"식단 데이터베이스를 조회했습니다. ({goal} 중심)\n"
                "구성 원칙: 균형 잡힌 영양, 가공식품 최소화, 규칙적인 식사\n"
                "하루 예시\n"
                "- 아침: 그릭요거트 + 베리 + 견과 약간\n"
                "- 점심: 현미밥 + 닭가슴살(또는 두부) + 샐러드\n"
                "- 저녁: 채소볶음 + 미역국 + 잡곡밥\n"
                "- 간식: 방울토마토, 삶은 달걀"
            )
            return finish(body, "이 구성으로 운동 루틴을 설계하겠습니다.",
                          "이 식단 방향이 괜찮으신가요? 바꾸고 싶은 메뉴가 있으면 말씀해 주세요.")

        if phase == 'workout':
            body = (
                "운동 루틴 설계기를 실행했습니다.\n"
                "원칙: 주 5일 활동, 2일 휴식. 유산소 + 근력 병행\n"
                "- 월/목: 전신 근력 30분\n"
                "- 화/금: 유산소 40분(빠르게 걷기/조깅)\n"
                "- 토: 가벼운 활동(스트레칭/산책)\n"
                "- 수/일: 휴식일로 배치했습니다"
            )
            return finish(body, "이 루틴으로 수면·생활습관을 설계하겠습니다.",
                          "휴식일 배치나 운동 종류를 바꾸고 싶으면 말씀해 주세요.")

        if phase == 'sleep':
            lead = ("수면 개선이 핵심 목표라 더 꼼꼼히 설계했습니다.\n"
                    if goal == '수면의 질 개선' else "")
            body = (
                "수면·생활습관 설계기를 실행했습니다.\n"
                f"{lead}"
                "- 권장 수면: 취침 23:30 / 기상 07:00 (약 7시간 30분)\n"
                "- 취침 1시간 전 스크린 줄이기, 오후 2시 이후 카페인 자제\n"
                "- 아침 기상 후 물 한 잔, 가벼운 스트레칭 5분\n"
                "- 하루 한 번 10분 산책으로 스트레스 관리"
            )
            return finish(body, "이 루틴으로 2주 일정을 편성하겠습니다.",
                          "수면 시간대나 생활습관을 조정하고 싶으면 말씀해 주세요.")

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
            return finish(body, "이대로 장보기 리스트까지 생성하겠습니다.",
                          "특정 날짜를 바꾸고 싶으면 'N일차 ...' 형태로 말씀해 주세요.")

        if phase == 'grocery':
            body = (
                "장보기 리스트 생성기를 실행했습니다(1주차 기준).\n"
                "단백질: 닭가슴살 5팩, 두부 4모, 달걀 1판, 그릭요거트 7개\n"
                "채소: 샐러드 채소, 브로콜리, 미역, 방울토마토\n"
                "탄수화물: 현미 1kg, 고구마 7개\n"
                "기타: 견과류, 올리브유, 베리류"
            )
            return finish(body, "루틴을 최종 정리하겠습니다.", "빠진 품목이 있으면 알려주세요.")

        if phase == 'delivery':
            return (
                "2주 건강 루틴을 최종 정리했습니다.\n\n"
                "핵심 요약\n"
                f"- 목표: {goal}\n"
                f"- 핵심 포인트: {focus}\n"
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

    @staticmethod
    def _explain(phase):
        """Substantive reasoning for a step when the user asks 'why' (demo)."""
        reasons = {
            'calc': (
                "이 수치를 설명드릴게요. 하루 약 1,900kcal는 활동량 보통 성인의 건강 유지 권장 범위(대략 1,800~2,200kcal)에 해당해서 기준으로 잡았어요. "
                "탄수화물45·단백질30·지방25 비율은 에너지와 근육 유지의 균형을 위한 일반적 권장치이고요. "
                "급격히 줄이면 컨디션 저하·요요 위험이 있어 무리한 제한은 피했습니다."
            ),
            'meal': (
                "식단을 이렇게 구성한 이유는, 가공식품을 줄이고 단백질·채소·통곡물을 고르게 넣어 혈당 변동과 공복감을 줄이기 위해서예요. "
                "끼니를 거르지 않고 규칙적으로 먹는 것이 에너지 유지와 습관 형성에 더 효과적이라 하루 3끼+가벼운 간식으로 짰습니다."
            ),
            'workout': (
                "주 5일 활동·2일 휴식으로 잡은 건, 회복 시간을 확보해야 부상 없이 꾸준히 이어갈 수 있기 때문이에요. "
                "유산소와 근력을 번갈아 배치하면 체력과 근지구력을 함께 키우면서 특정 부위 피로를 줄일 수 있습니다."
            ),
            'sleep': (
                "취침 23:30·기상 07:00은 약 7.5시간으로, 성인 권장 수면(7~9시간) 범위예요. "
                "취침 전 스크린·카페인을 줄이라고 한 건 멜라토닌 분비와 입면을 방해하기 때문이고, 일정한 시간에 자고 일어나는 것이 수면의 질 개선에 가장 효과적입니다."
            ),
            'schedule': (
                "일정은 운동일과 휴식일을 번갈아 배치하고, 1·8·14일차에 컨디션 점검을 넣어 2주 동안 무리 없이 흐름을 유지하도록 짰어요. "
                "주중·주말 부담을 고르게 나눠 지속 가능성을 높였습니다."
            ),
            'grocery': (
                "장보기 목록은 위에서 짠 식단에 실제로 필요한 재료만 1주 분량으로 추린 거예요. "
                "단백질·채소·통곡물을 중심으로 담아 균형 잡힌 식사를 쉽게 준비할 수 있게 했습니다."
            ),
        }
        body = reasons.get(phase, "그렇게 설계한 이유를 설명드릴게요. 건강 유지에 적정한 일반 기준과 사용자 정보를 바탕으로 잡았습니다.")
        return body + "\n\n이대로 진행할까요, 아니면 바꿔드릴까요?"

    @staticmethod
    def _detect_goal(profile, user_message):
        """Infer the chosen health goal from intake answers (demo heuristic)."""
        text = f"{profile or ''} {user_message or ''}"
        if '체중' in text or '감량' in text:
            return '체중 감량', '건강한 범위의 가벼운 칼로리 조정 포함'
        if '수면' in text:
            return '수면의 질 개선', '수면 리듬 회복에 가장 집중'
        if '운동 습관' in text or '규칙' in text:
            return '규칙적인 운동 습관 만들기', '매일 실천 가능한 운동 습관 형성'
        if '식습관' in text:
            return '식습관 개선', '균형 잡힌 식습관 형성에 집중'
        if '컨디션' in text or '에너지' in text:
            return '전반적인 컨디션·에너지 향상', '에너지 수준과 일상 활력 향상'
        return '건강한 생활 루틴', '식단·운동·수면의 균형'
