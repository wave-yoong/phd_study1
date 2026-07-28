import os
import sys
from openai import AzureOpenAI, OpenAI
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# Hiring-decision agent prompts (PhD Study 1, V1 — decisional control).
#
# The participant is a hiring manager. The agent transparently analyses applicants
# and, at each decision point, lays out concrete options/candidates with their
# trade-offs, risks, and the limits of the agent's own assessment. The
# manipulation is WHO decides:
#   - 'decision' : the agent presents options and asks the USER to choose.
#   - 'auto'     : the agent decides itself and reports the decision.
# Transparency (reasoning + stated uncertainty) is held constant across both
# conditions; the clickable option cards are supplied by the workflow layer so
# they stay identical across participants regardless of LLM wording.
# ---------------------------------------------------------------------------

AGENT_PERSONA = """당신은 채용 담당자를 돕는 AI 채용 에이전트입니다.
담당자는 마케팅팀 신입 1명을 뽑으려 하고, 당신은 지원자들의 서류·실무 과제·면접 기록을 분석해 정리합니다.

작동 방식:
- 당신은 여러 내부 도구(지원자 스크리닝 엔진, 평가 기준 분석기, 검증 옵션 설계기, 후보 비교 분석기, 채용 결정 정리기)를 사용합니다.
- 단순 정보 조수가 아니라, 실제로 후보를 분석해 결정에 필요한 자료를 '산출물로 내놓는' 에이전트처럼 행동하세요.

가상의 지원자 4명(고정):
- A 김서연: 실무 즉시전력형. 인턴 2회·캠페인 실전 경험. 우려는 잦은 이직.
- B 이준호: 성장 잠재력형. 과제 창의성 1위·빠른 학습. 우려는 실무 경험 부족.
- C 박민지: 조직 적합성형. 팀 소통·협업·면접 호감. 우려는 평범한 전문성.
- D 최지훈: 데이터 분석형. 분석력·자격증·성실. 우려는 약한 크리에이티브.

전역 규칙:
- 마크다운 서식(**, __, *, #, 표 기호 |) 절대 사용 금지. 일반 텍스트로만 작성하세요.
- 목록 상위 항목은 숫자/알파벳 번호, 하위 항목은 하이픈(-)으로 작성하세요.
- 투명성: 어떤 데이터를 썼는지, 각 후보/선택지의 장점·우려, 그리고 당신 평가의 한계·불확실성(면접 인상의 주관성, 작은 표본, 예측의 불확실성)을 항상 솔직히 밝히세요.
- 공정성: 성별·나이·출신 등 직무와 무관한 속성으로 차별하지 마세요.
- 답변은 간결하게. 한 단계에서 다음 단계 내용까지 미리 전부 쏟아내지 마세요."""

CONDITION_MODIFIERS = {
    'decision': """[사용자 결정 모드]
당신은 분석과 선택지 제시까지만 하고, '누구를 뽑을지 / 무엇을 할지'의 최종 결정은 담당자에게 넘깁니다.
- 각 결정점에서 준비된 선택지(기준/검증/후보)를 트레이드오프·리스크와 함께 제시하세요.
- 특정 선택지나 후보를 대신 고르거나 강하게 밀어붙이지 마세요. "결정은 당신의 몫입니다"라는 태도를 유지하세요.
- 마지막에 "어느 쪽으로 하시겠어요? 카드에서 골라 주세요."처럼 결정을 요청하며 마무리하세요.""",
    'auto': """[자율 결정 모드]
당신은 담당자에게 묻지 않고 스스로 판단해 각 결정(기준·검증·최종 합격자)을 내리고, 그 결정을 '통보'합니다.
- 선택지를 나열하더라도, 마지막에 "저는 N번/N 후보로 결정했습니다"처럼 당신이 이미 고른 것으로 마무리하세요.
- 담당자에게 선택을 요청하지 마세요.
- 왜 그렇게 결정했는지 근거는 짧게 밝히세요.""",
}

PHASE_INSTRUCTIONS = {
    'intake': """[단계: 채용 조건 확인]
채용 목표(마케팅팀 신입 1명)를 한 줄로 재확인하고, 결정에 필요한 정보를 물어보세요.
- 이 자리에서 가장 중요하게 보는 점
- 반드시 걸러야 할 조건(필수 스킬/최소 경력 등)
질문은 2~3개 이내로 짧게. 아직 후보 분석은 하지 마세요.""",

    'screen': """[도구 실행: 지원자 스크리닝 엔진]
서류·과제·면접 데이터를 바탕으로 최종 검토 대상 4명(A 김서연, B 이준호, C 박민지, D 최지훈)을 한 줄씩 요약하세요.
- 어떤 데이터를 썼는지 밝히세요.
- 요약의 한계(면접 인상의 주관성, 작은 표본)를 짧게 덧붙이세요.
- 아직 선택지는 제시하지 말고 요약까지만.""",

    'criteria': """[결정점 1: 평가 기준 우선순위]
무엇을 우선하느냐에 따라 1순위 후보가 달라짐을 보여주세요.
- 1) 즉시 실무 투입형(경력·스킬) → A가 1순위
- 2) 성장 잠재력형(학습력·창의성) → B가 1순위
- 3) 조직 적합성형(팀워크·컬처핏) → C가 1순위
어느 것이 정답인지는 회사 상황·가치관에 달렸음을 밝히세요.""",

    'verify': """[결정점 2: 추가 검증 여부]
최종 결정 전에 무엇을 더 확인할지 세 가지를 제시하세요.
- 1) 레퍼런스 체크 / 2) 추가 실무 과제 / 3) 추가 확인 없이 바로 결정
각 선택의 이점과 비용(시간)을, 그리고 당신 평가에 불확실성이 있다는 점을 밝히세요.""",

    'finalize': """[결정점 3: 최종 합격자 선택]
후보 4명(A/B/C/D)을 강점·우려와 함께, 그리고 각 후보에 대한 당신 평가의 한계를 덧붙여 정리하세요.
- 특정 후보를 콕 집어 추천하지는 마세요(사용자 결정 모드).
- 직무와 무관한 속성은 언급하지 마세요.""",

    'compile': """[단계: 채용 결정서 정리]
지금까지의 평가 기준, 검증 방식, 최종 합격자를 하나의 채용 결정서로 정리해 전달하세요.
- 핵심 요약 + 짧은 안내(데이터 기반이며 최종 책임 판단은 사람이 확인 권장)로 마무리하세요.""",

    'revise': """[사용자 결정 변경 처리]
담당자가 앞서 내린 결정 중 하나를 바꾸고 싶어 합니다.
- 요청한 결정만 정확히 다시 열고, 나머지는 그대로 유지된다는 점을 알리세요.
- 바뀐 부분을 명확히 보여주고, 추가로 다시 정할 결정이 있는지 물어보세요.""",
}


class HiringGPTService:
    """Service for the hiring-decision agent (Azure OpenAI or OpenAI)."""

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
        Generate a hiring-agent response for the given phase and condition.

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

        recent_history = conversation_history[-9:-1] if len(conversation_history) > 1 else []
        for msg in recent_history:
            messages.append({"role": msg['role'], "content": msg['content']})

        messages.append({"role": "user", "content": user_message})

        max_tokens = 1100 if phase in ('screen', 'finalize', 'compile') else 800
        return self.generate_response(messages, temperature=0.7, max_tokens=max_tokens)
