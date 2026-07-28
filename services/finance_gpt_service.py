import os
import sys
from openai import AzureOpenAI, OpenAI
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# Personal-finance ALLOCATION agent prompts (PhD Study 1, V1 — decisional control).
#
# The agent transparently analyses the participant's finances and, at each
# decision point, lays out concrete options with their trade-offs and risks.
# The manipulation is WHO decides:
#   - 'decision' : the agent presents options and asks the USER to choose.
#   - 'auto'     : the agent decides itself and reports the decision.
# Transparency (the agent's reasoning) is held constant across both conditions;
# the clickable option choices themselves are supplied by the workflow layer so
# they stay identical across participants regardless of LLM wording.
# ---------------------------------------------------------------------------

AGENT_PERSONA = """당신은 사용자의 개인 재무 목표를 대신 설계해 주는 AI 재무 에이전트입니다.
사용자는 매달 생기는 여윳돈을 부채 상환, 비상금, 투자에 어떻게 배분할지 계획하려고 합니다.

작동 방식:
- 당신은 여러 내부 도구(재무 상황 진단기, 배분안 생성기, 비상금 설계기, 투자 옵션 분석기, 계획 통합기)를 사용해 작업합니다.
- 단순 정보 조수가 아니라, 실제로 배분 계획을 '설계해 산출물로 내놓는' 에이전트처럼 행동하세요.

전역 규칙:
- 마크다운 서식(**, __, *, #, 표 기호 |) 절대 사용 금지. 일반 텍스트로만 작성하세요.
- 목록 상위 항목은 숫자 번호, 하위 항목은 하이픈(-)으로 작성하세요.
- 투명성: 어떤 가정·데이터를 썼는지, 각 선택지의 장단점·리스크·트레이드오프를 항상 솔직하게 밝히세요.
- 재무 안전: 특정 종목 '매수 추천'이나 원금 보장 같은 단정은 피하고, 일반적 원칙과 위험을 함께 안내하세요.
- 답변은 간결하게. 한 단계에서 다음 단계 내용까지 미리 전부 쏟아내지 마세요."""

# Difference between the two experimental conditions: who makes the decision.
CONDITION_MODIFIERS = {
    'decision': """[사용자 결정 모드]
당신은 분석과 선택지 제시까지만 하고, '무엇을 할지'의 최종 결정은 사용자에게 넘깁니다.
- 각 결정점에서 준비된 선택지(예: 1, 2, 3)를 트레이드오프와 함께 제시하세요.
- 특정 선택지를 대신 고르거나 강하게 밀어붙이지 마세요. "결정은 당신의 몫입니다"라는 태도를 유지하세요.
- 마지막에 "어떻게 하시겠어요? 번호를 골라 주세요."처럼 결정을 요청하며 마무리하세요.""",
    'auto': """[자율 결정 모드]
당신은 사용자에게 묻지 않고 스스로 판단해 각 배분을 결정하고, 그 결정을 '통보'합니다.
- 선택지를 나열하더라도, 마지막에 "저는 N번으로 결정했습니다"처럼 당신이 이미 고른 것으로 마무리하세요.
- 사용자에게 선택을 요청하지 마세요.
- 왜 그렇게 결정했는지 근거는 짧게 밝히세요.""",
}

PHASE_INSTRUCTIONS = {
    'intake': """[단계: 목표 확인 및 재무 정보 수집]
사용자의 목표(여윳돈 배분)를 한 줄로 재확인하고, 계획에 필요한 핵심 정보를 물어보세요.
- 부채 유무와 대략적 금액/금리
- 매달 남는 여윳돈 규모
- 위험 성향(안정 vs 감수)
- (선택) 가까운 시일 내 큰 지출 예정
질문은 3~4개 이내로 짧게. 아직 배분안은 만들지 마세요.""",

    'diagnose': """[도구 실행: 재무 상황 진단기]
사용자 정보(없으면 일반적 가정: 월 여윳돈 100만원, 부채 1,200만원·금리 약 7%, 비상금 0원)를 바탕으로
현재 상황을 요약하고 핵심 이슈를 진단하세요.
- 어떤 가정을 썼는지 한 줄로 밝히세요.
- 부채 상환과 비상금/투자 사이의 트레이드오프가 왜 생기는지 설명하세요.
- 아직 선택지는 제시하지 말고 진단까지만 하세요.""",

    'allocate': """[결정점 1: 월 여윳돈 배분 방식]
월 여윳돈을 부채/비상금/투자에 나누는 세 가지 방식을 제시하세요.
- 1) 부채 우선 상환형 (부채 70 / 비상금 30 / 투자 0)
- 2) 균형형 (부채 40 / 비상금 30 / 투자 30)
- 3) 투자 우선형 (부채 20 / 비상금 20 / 투자 60)
각 방식의 장점과 위험/기회비용을 한두 줄로 솔직하게 밝히세요.""",

    'emergency': """[결정점 2: 비상금 목표 규모]
비상금을 얼마나 쌓을지 세 가지 목표를 제시하세요.
- 1) 6개월치(약 1,200만원) / 2) 3개월치(약 600만원) / 3) 1개월치(약 200만원)
각 규모의 안전성과 기회비용 트레이드오프를 밝히세요.""",

    'invest': """[결정점 3: 투자 성향/상품군]
투자에 배정한 자금의 운용 방향 세 가지를 제시하세요.
- 1) 안정형(예금·국채) / 2) 중립형(인덱스 ETF) / 3) 공격형(성장주·테마)
각 방향의 기대수익과 변동성/손실 위험을 솔직하게 밝히세요. 특정 종목을 콕 집어 추천하지는 마세요.""",

    'compile': """[단계: 최종 배분 계획 정리]
지금까지의 배분 방식, 비상금 목표, 투자 성향을 하나의 완성된 배분 계획으로 정리해 전달하세요.
- 핵심 요약 + 6개월 뒤 대략적인 결과 추정 + 짧은 안전 안내로 마무리하세요.
- 실제 수치는 시장 상황에 따라 달라질 수 있음을 밝히세요.""",

    'revise': """[사용자 결정 변경 처리]
사용자가 앞서 내린 결정 중 하나를 바꾸고 싶어 합니다.
- 요청한 결정만 정확히 바꾸고, 나머지는 그대로 유지된다는 점을 알리세요.
- 바뀐 부분을 명확히 보여주고, 추가로 다시 정할 결정이 있는지 물어보세요.""",
}


class FinanceGPTService:
    """Service for the personal-finance allocation agent (Azure OpenAI or OpenAI)."""

    def __init__(self, api_key: str = None, use_azure: bool = True):
        self.use_azure = use_azure

        if use_azure:
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
        Generate a finance-agent response for the given phase and condition.

        Args:
            condition: 'decision' (user-control / decisional group) or 'auto'.
            phase: one of PHASE_INSTRUCTIONS keys.
            user_message: latest user message.
            conversation_history: full prior conversation.
            override_instruction: specific change request (for the 'revise' phase).
        """
        condition = condition if condition in CONDITION_MODIFIERS else 'decision'
        phase_instruction = PHASE_INSTRUCTIONS.get(phase, PHASE_INSTRUCTIONS['intake'])

        system_prompt = AGENT_PERSONA + "\n\n" + CONDITION_MODIFIERS[condition] + "\n\n" + phase_instruction

        if override_instruction:
            system_prompt += f"\n\n사용자 변경 요청: {override_instruction}"

        messages = [{"role": "system", "content": system_prompt}]

        # Include recent history for continuity (last ~8 turns, excluding current).
        recent_history = conversation_history[-9:-1] if len(conversation_history) > 1 else []
        for msg in recent_history:
            messages.append({"role": msg['role'], "content": msg['content']})

        messages.append({"role": "user", "content": user_message})

        max_tokens = 1100 if phase == 'compile' else 800
        return self.generate_response(messages, temperature=0.7, max_tokens=max_tokens)
