import os
import sys
from openai import AzureOpenAI, OpenAI
from typing import List, Dict


class GPTService:
    """Service for interacting with Azure OpenAI or OpenAI GPT API."""
    
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
            self.model = "gpt-3.5-turbo"
    
    def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """
        Generate a response from GPT.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated response text
        """
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
    
    def generate_conversational_response(
        self,
        stage: str,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        previous_request: str | None = None
    ) -> str:
        """
        Generate a natural conversational response that implicitly guides through workflow stages.
        
        Args:
            stage: Current workflow stage ('source_planning', 'structure_proposal', 'final_answer')
            user_message: Latest user message
            conversation_history: Full conversation history
            previous_request: Previous user request (for interruption handling)
            
        Returns:
            Contextual conversational response
        """
        stage_instructions = {
            'source_planning': """당신은 친절한 연구 조수입니다. 사용자의 질문을 받으면 다음을 수행하세요:
    1. 질문을 짧게 재확인
    2. 어떤 자료를 참고할지 물어보기 - 각 옵션에 설명을 추가하세요
       예시:
       "연구 결과나 전문가 의견, 일반적인 건강 정보 등을 확인할 수 있습니다. 어떤 자료를 선호하시나요?
       
       1. 학술 논문: 관련 연구 결과 및 실험 데이터
       2. 정부/공신력 기관: 보건복지부, 의학 협회 등의 공식 발표
       3. 뉴스: 전문가 의견이 포함된 보도 자료
       4. 블로그 및 소셜 미디어: 일반적인 경험담과 논의들
       
       원하시는 번호를 선택하시거나, 여러 개를 조합해서 말씀해주세요."

    중요:
    - 결과를 바로 제공하지 말고, 먼저 자료 선택을 받으세요.
    - 각 옵션에 구체적인 설명을 붙여서 사용자가 이해하기 쉽게 하세요.
    - 목록은 숫자 번호로만 작성하고, 불릿(-, •, *)은 사용하지 마세요.
    - 볼드체(**, __), 이탤릭체(*, _) 등 마크다운 서식 절대 사용 금지
    - 여러 개 선택 가능하다는 것을 명시하세요.""",
            
            'structure_proposal': """사용자가 참고 자료를 선택했습니다. 이제 답변 구조를 제안하세요:

    1. 사용자가 선택한 자료 유형을 확인 (예: "연구 결과와 뉴스 보도를 중심으로...")
    2. 질문 맥락에 맞는 답변 구조를 구체적으로 제안
       예시:
       "다음과 같은 내용 구성으로 보여드리겠습니다:
       
       1. [주제]의 효능과 과학적 근거
       2. 주의사항 및 부작용
       3. 효과적인 섭취/활용 방법
       4. 전문가 권고사항 및 최신 연구 동향
       
       이대로 보여드려도 될까요?"
    
    3. 사용자 승인 요청 - "예/y를 입력하시면 바로 답변 드리고, 추가 요청이 있으시면 말씀해주세요."

    중요:
    - 아직 결과를 제공하지 말고, 구조 확인만 받으세요.
    - 구조는 사용자의 질문에 맞게 유연하게 구성하세요 (템플릿 사용 금지).
    - 목록은 숫자 번호로만 작성하고, 불릿(-, •, *) 사용 금지
    - 볼드체(**, __), 이탤릭체(*, _) 등 마크다운 서식 절대 사용 금지
    - 구조 항목은 3-5개가 적당합니다.""",

            'structure_refinement': """사용자가 구조 변경을 원했습니다. 이제:
    1. 사용자가 요청한 변경사항을 정확히 반영
    2. 수정된 구조를 다시 명확하게 제시
       예시:
       "알겠습니다. 다음과 같이 수정했습니다:
       
       1. [수정된 항목 1]
       2. [수정된 항목 2]
       3. [추가된 항목]
       
       이제 이 구조로 진행해도 될까요?"
    
    3. 승인 확인: "예/y를 입력하시면 답변 드리겠습니다."

    중요:
    - 여전히 결과는 제공하지 말고 구조 확인만 받으세요.
    - 사용자 요청을 정확히 반영하세요.
    - 목록은 숫자 번호로만 작성하고, 불릿(-, •, *) 사용 금지
    - 볼드체(**, __), 이탤릭체(*, _) 등 마크다운 서식 절대 사용 금지""",

            'final_answer': """사용자가 구조에도 동의했습니다. 이제 완전한 답변을 제공하세요:

    **절대적 필수 사항 - 출처 표기**:
    - 확실하게 존재하는 출처만 사용 (불확실하면 출처 없이 일반 지식으로만 답변)
    - Hallucination 절대 금지: 없는 논문, 기사, 링크를 만들어내지 마세요
    - 실제 접근 가능한 URL만 제공 (링크가 확실하지 않으면 링크 없이 출처명만 표기)
    - 각 정보 뒤에 [출처: ...] 형식으로 즉시 표기
    
    답변 구성:
    1. 앞서 제안한 구조에 맞춰 완전한 답변 제공
    2. 각 섹션마다 출처를 명확히 표기 (확실한 출처만)
       예시: "올리브유는 심혈관 건강에 도움이 됩니다 [출처: 대한영양학회 건강 지방 가이드, 2024]"
    
    3. 답변 마지막에 "참고 자료" 섹션 (확실한 자료만 포함):
       "참고 자료:
       1. 대한영양학회 - 건강 지방 가이드 - 2024 - https://example.com
       2. 연합뉴스 - 올리브유 섭취 방법 - 2024.01.15 - https://example.com"
    
    4. 링크는 전체 URL 형식으로 (https://로 시작)
    
    5. 마지막: "추가로 궁금하신 점이 있으신가요?"

    서식 규칙 (절대 엄수):
    - 볼드체(**, __, ***) 절대 사용 금지 - 일반 텍스트로만 작성
    - 이탤릭체(*, _) 절대 사용 금지
    - 마크다운 문법 일체 사용 금지
    - 목록은 숫자 번호로만 (불릿 -, •, * 금지)
    - 제목이나 강조가 필요하면 그냥 텍스트로만
    
    중요:
    - 출처가 확실하지 않으면 "일반적으로 알려진 정보입니다" 같이 명시
    - 가상의 출처를 만들어내는 것보다 출처 없이 답변하는 게 낫습니다
    - 전문적이면서도 친근하게"""
        }
        
        if stage == 'interruption':
            system_prompt = (
                "사용자의 즉흥 질문에 먼저 간단히 답하고, "
                "이전 요청을 계속 진행할지 예/아니오로 확인하세요. "
                "볼드체(**, __), 이탤릭체(*, _), 불릿(-, •, *) 등 마크다운 서식 절대 사용 금지 - 일반 텍스트로만 작성하세요."
            )
            if previous_request:
                system_prompt += f"\n이전 요청: {previous_request}"
        else:
            system_prompt = stage_instructions.get(stage, stage_instructions['source_planning'])
        
        # Build conversation context
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add recent conversation history (last 5 messages for context)
        recent_history = conversation_history[-6:-1] if len(conversation_history) > 1 else []
        for msg in recent_history:
            messages.append({
                "role": msg['role'],
                "content": msg['content']
            })
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return self.generate_response(messages, temperature=0.7, max_tokens=800)

