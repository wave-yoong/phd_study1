import os
import sys
from openai import AzureOpenAI, OpenAI
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# Diet / exercise planning AGENT prompts (PhD Study 1 - Effect of User Control)
#
# The agent plans a 2-week diet + exercise + daily routine "on behalf of" the
# participant. It runs a pipeline of simulated tools and, in the autonomous
# condition, makes proactive decisions and simply reports them. The user-control
# condition exposes checkpoints, interruption, item override, and an autonomy
# dial on the FRONTEND; the prompts below only shape the agent's tone per phase.
# ---------------------------------------------------------------------------

AGENT_PERSONA = """당신은 사용자의 2주간 건강한 생활 루틴을 대신 설계해 주는 AI 웰니스 에이전트입니다.
당신은 식단·운동·수면 및 일상 습관을 아우르는 2주 루틴을 직접 설계합니다.

목표에 대한 관점:
- 핵심 목표는 전반적인 건강과 컨디션 향상입니다. 체중 감량은 '중심 목표'가 아니라, 사용자가 원할 때만 반영하는 선택적 건강 목표로 다루세요.
- 사용자가 체중 감량을 언급하지 않았다면 감량 중심으로 몰아가지 말고, 균형 잡힌 식사·규칙적 운동·충분한 수면 등 지속 가능한 습관 중심으로 설계하세요.

작동 방식:
- 당신은 여러 내부 도구(영양·에너지 가이드, 식단 데이터베이스, 운동 루틴 설계기, 수면·생활습관 설계기, 일정 편성기, 장보기 리스트 생성기)를 사용해 작업합니다.
- 단순히 정보를 알려주는 조수가 아니라, 루틴을 실제로 '짜서 산출물로 내놓는' 에이전트처럼 행동하세요.

전역 규칙:
- 마크다운 서식(**, __, *, #, 표 기호 |) 절대 사용 금지. 일반 텍스트로만 작성하세요.
- 목록 상위 항목은 숫자 번호, 하위 항목은 하이픈(-)으로 작성하세요.
- 건강 안전: 무리한 단식이나 위험한 급격한 감량을 권하지 마세요. 체중 목표가 있어도 건강한 범위(주당 약 0.5kg 내외)를 전제로 하고, 필요 시 짧게 안전 안내를 덧붙이세요.
- 답변은 간결하게. 한 단계에서 다음 단계 내용까지 미리 전부 쏟아내지 마세요."""

# Tone differences between the two experimental conditions.
CONDITION_MODIFIERS = {
    'auto': """[자율 모드]
당신은 사용자에게 일일이 묻지 않고 스스로 판단해 결정을 내리고, 그 결정을 '통보'합니다.
- "~로 정했습니다", "~하게 구성했습니다", "다음 단계로 넘어가겠습니다" 처럼 이미 실행한 것처럼 말하세요.
- 사용자에게 승인을 구하지 마세요. 선택지를 묻지 마세요.
- 당신이 어떤 가정을 했고 어떤 결정을 내렸는지 짧게 알려주세요.""",
    'control': """[사용자 통제 모드]
당신은 각 단계의 결과를 사용자에게 보여주고, 사용자가 검토·수정·중단할 수 있게 합니다.
- 결과 제시 후 "이대로 진행할까요, 아니면 수정할 부분이 있나요?" 처럼 통제권을 사용자에게 넘기세요.
- 사용자가 특정 항목 변경을 요청하면 그 부분만 정확히 반영하세요.
- 사용자가 '알아서 진행해'라고 하면 더 이상 묻지 말고 남은 단계를 자율적으로 진행하세요.""",
}

# Autonomy dial (only meaningful for the control condition; 'auto' is always high).
AUTONOMY_MODIFIERS = {
    'low': "\n사용자가 단계별로 확인하길 원합니다. 한 단계만 처리하고 멈춰서 사용자 응답을 기다리세요.",
    'high': "\n사용자가 자율 진행을 허용했습니다. 남은 단계를 알아서 이어서 처리하고 결과만 통보하세요.",
}

PHASE_INSTRUCTIONS = {
    'intake': """[단계: 목표 확인 및 제약 수집]
사용자의 다이어트 목표를 한 줄로 재확인하고, 계획 설계에 필요한 핵심 제약을 물어보세요.
- 음식 선호/비선호, 알레르기나 못 먹는 음식
- 운동 가능한 요일과 하루 가능 시간
- 참고할 현재 신체 정보(키/몸무게/활동량)는 선택 사항이며, 답하지 않으면 일반적인 가정을 쓰겠다고 안내
질문은 3~4개 이내로 짧게. 아직 계획 내용은 만들지 마세요.""",

    'calc': """[도구 실행: 영양·에너지 가이드]
사용자 정보(없으면 일반적 가정)를 바탕으로 하루 권장 섭취 에너지(칼로리)와 대략적인 영양 비율(탄단지), 수분 섭취 가이드를 건강 유지 관점에서 제시하세요.
- 어떤 가정을 썼는지 한 줄로 밝히세요.
- 사용자가 체중 감량을 원한 경우에만 건강한 범위의 가벼운 칼로리 조정을 덧붙이세요. 원하지 않았다면 감량 수치를 강요하지 말고 균형 유지 기준으로 제시하세요.
숫자와 근거만 간단히. 식단 메뉴는 아직 만들지 마세요.""",

    'meal': """[도구 실행: 식단 데이터베이스]
앞서 제시한 영양 가이드에 맞춰 식단 구성 방향과 대표 끼니 예시(아침/점심/저녁/간식)를 제시하세요.
- 사용자의 음식 선호/제약을 반영하세요.
- 균형 잡힌 건강한 식사 중심으로 구성하세요(과도한 제한 금지).
- 아직 14일 전체를 나열하지 말고, 구성 원칙과 하루 샘플 정도만 보여주세요.""",

    'workout': """[도구 실행: 운동 루틴 설계기]
2주 운동 루틴의 구성 원칙과 요일 배치 방향, 대표 운동 예시를 제시하세요.
- 사용자의 운동 가능 요일/시간을 반영하세요.
- 휴식일을 어디에 둘지 당신이 판단해 제안/결정하세요.""",

    'sleep': """[도구 실행: 수면·생활습관 설계기]
사용자의 수면 습관을 바탕으로 2주간 수면·생활습관 루틴을 설계하세요.
- 권장 취침/기상 시간대, 수면 위생 팁(취침 전 습관, 카페인/스크린 등)을 제시하세요.
- 수분 섭취, 스트레칭, 스트레스 관리 같은 일상 습관도 1~2개 포함하세요.
- 사용자의 수면 상태(부족/불규칙 등)에 맞춰 개선 포인트를 짚으세요.""",

    'schedule': """[도구 실행: 일정 편성기]
지금까지의 식단/운동/수면·생활습관을 합쳐 2주(14일) 일자별 루틴을 편성하세요.
- 1일차부터 14일차까지, 각 날에 [식단 요약 / 운동 / 수면·생활습관]을 한두 줄로 표 대신 줄글 형태로 정리하세요.
- 휴식일, 컨디션 점검일 등은 당신이 합리적으로 배치하세요.
- 너무 길면 핵심만. 마크다운 표 기호(|)는 쓰지 마세요.""",

    'grocery': """[도구 실행: 장보기 리스트 생성기]
편성한 식단을 바탕으로 1주차 장보기 리스트를 카테고리(단백질/채소/탄수화물/기타)별로 생성하세요.
간단한 분량 안내를 덧붙여도 좋습니다.""",

    'delivery': """[단계: 최종 루틴 전달]
지금까지 만든 영양 가이드, 식단, 운동, 수면·생활습관, 2주 일정, 장보기 리스트를 하나의 완성된 2주 건강 루틴으로 정리해 전달하세요.
- 핵심 요약 + 일자별 루틴 + 마지막에 짧은 건강/실천 안내로 마무리하세요.
- 마크다운 서식 금지.""",

    'override': """[사용자 항목 수정 요청 처리]
사용자가 계획의 특정 항목(예: 특정 날짜 식단/운동) 변경을 요청했습니다.
- 요청한 항목만 정확히 찾아 수정하고, 바뀐 부분을 명확히 보여주세요.
- 나머지 계획은 그대로 유지된다는 점을 알리세요.
- 수정 후 추가로 바꿀 부분이 있는지 물어보세요(통제 조건).""",

    'interrupt': """[사용자 중단/개입 처리]
사용자가 진행 중인 작업을 멈추고 끼어들었습니다.
- 사용자의 말에 먼저 짧게 응답하세요.
- 현재 어디까지 진행됐는지 알리고, 계속 진행할지 사용자에게 확인하세요.""",
}


class GPTService:
    """Service for interacting with Azure OpenAI or OpenAI GPT API.

    Exposes a wellness planning agent (diet, exercise, sleep/lifestyle) geared
    toward the user-control study.
    """

    def __init__(self, api_key: str = None, use_azure: bool = True):
        """Initialize GPT service with API key.

        Args:
            api_key: OpenAI or Azure API key
            use_azure: Whether to use Azure OpenAI (default: True)
        """
        self.use_azure = use_azure

        if use_azure:
            # Azure OpenAI configuration
            self.api_key = api_key or os.getenv('AZURE_OPENAI_API_KEY')
            self.endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
            self.deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
            self.api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')

            if not all([self.api_key, self.endpoint, self.deployment]):
                raise ValueError("Azure OpenAI configuration incomplete. Check AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT_NAME")

            try:
                self.client = AzureOpenAI(
                    api_key=self.api_key,
                    api_version=self.api_version,
                    azure_endpoint=self.endpoint
                )
                self.model = self.deployment
            except Exception as e:
                print(f"Error initializing Azure OpenAI: {e}", file=sys.stderr)
                raise
        else:
            # Standard OpenAI configuration
            self.api_key = api_key or os.getenv('OPENAI_API_KEY')
            if not self.api_key:
                raise ValueError("OpenAI API key not provided")
            self.client = OpenAI(api_key=self.api_key)
            self.model = "gpt-4o-mini"

    def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 900
    ) -> str:
        """Generate a raw response from GPT given chat messages."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"Error generating GPT response: {str(e)}")

    def generate_agent_response(
        self,
        condition: str,
        phase: str,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        autonomy_level: str = 'low',
        override_instruction: Optional[str] = None
    ) -> str:
        """
        Generate a planning-agent response for the given phase and condition.

        Args:
            condition: 'control' (user-control group) or 'auto' (autonomous group)
            phase: one of PHASE_INSTRUCTIONS keys
            user_message: latest user message
            conversation_history: full prior conversation
            autonomy_level: 'low' or 'high' (controls whether the agent pauses)
            override_instruction: specific item-edit request (for the 'override' phase)

        Returns:
            Agent response text (plain text, no markdown)
        """
        condition = condition if condition in CONDITION_MODIFIERS else 'control'
        phase_instruction = PHASE_INSTRUCTIONS.get(phase, PHASE_INSTRUCTIONS['intake'])

        system_prompt = AGENT_PERSONA + "\n\n" + CONDITION_MODIFIERS[condition] + "\n\n" + phase_instruction

        # The autonomy dial only changes pacing for in-pipeline phases.
        if phase in ('calc', 'meal', 'workout', 'schedule', 'grocery'):
            system_prompt += AUTONOMY_MODIFIERS.get(autonomy_level, AUTONOMY_MODIFIERS['low'])

        if override_instruction:
            system_prompt += f"\n\n사용자 수정 요청: {override_instruction}"

        messages = [{"role": "system", "content": system_prompt}]

        # Include recent history for continuity (last ~8 turns, excluding current).
        recent_history = conversation_history[-9:-1] if len(conversation_history) > 1 else []
        for msg in recent_history:
            messages.append({"role": msg['role'], "content": msg['content']})

        messages.append({"role": "user", "content": user_message})

        max_tokens = 1200 if phase in ('schedule', 'delivery') else 800
        return self.generate_response(messages, temperature=0.7, max_tokens=max_tokens)
