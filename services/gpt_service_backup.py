import os
import sys
from openai import AzureOpenAI, OpenAI
from typing import List, Dict, Optional


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
        previous_request: Optional[str] = None,
        source_selection: Optional[str] = None
    ) -> str:
        """
        Generate a natural conversational response that implicitly guides through workflow stages.
        
        Args:
            stage: Current workflow stage ('source_planning', 'structure_proposal', 'final_answer')
            user_message: Latest user message
            conversation_history: Full conversation history
            previous_request: Previous user request (for interruption handling)
            source_selection: User's selected source types
            
        Returns:
            Contextual conversational response
        """
        stage_instructions = {
            'source_planning': """당신은 친절한 연구 조수입니다.

!!!절대 금지: 지금 단계에서 실제 답변 내용을 절대 제공하지 마세요!!!
!!!이 단계의 유일한 목적: 어떤 자료를 참고할지 사용자에게 선택받는 것입니다!!!

사용자의 질문을 받으면 다음을 수행하세요:
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
            
            'structure_proposal': """사용자가 참고 자료를 선택했습니다.

!!!절대 금지: 지금 단계에서 실제 답변 내용을 절대 제공하지 마세요!!!
!!!절대 금지: 각 항목에 대한 설명, 예시, 내용을 절대 쓰지 마세요!!!
!!!이 단계의 유일한 목적: 목차(제목만)를 보여주고 승인을 받는 것입니다!!!

해야 할 것:
1. 사용자가 선택한 자료 유형을 한 줄로 확인 (예: "학술 논문과 뉴스를 중심으로 정리하겠습니다.")
2. 제목만으로 이루어진 목차를 번호로 제시 (내용, 설명, 예시 절대 금지)
   예시:
   "다음과 같은 순서로 정리해 드리겠습니다:
   
   1. [주제]의 정의
   2. 주요 효능
   3. 주의사항 및 부작용
   4. 전문가 권고사항
   
   이 순서로 진행해도 될까요? 변경을 원하시면 말씀해주세요."

멈추는 지점: 목차 제시 후 반드시 멈추고 사용자의 응답을 기다리세요.

규칙:
- 각 항목은 제목(5단어 이내)만 적을 것 - 설명/내용/예시 금지
- 목록은 숫자 번호로만, 불릿(-, •, *) 사용 금지
- 볼드체(**, __), 이탤릭체(*, _) 등 마크다운 서식 절대 사용 금지
- 구조 항목은 3-5개가 적당합니다.""",

            'structure_refinement': """사용자가 구조 변경을 원했습니다.
1. 사용자가 요청한 변경사항 이해 및 확인
2. 이전 전체 구조를 기반으로 사용자 요청을 반영한 완전한 전체 구조를 다시 제시
   - 사용자가 "이 내용을 포함해서", "이런 내용을 기반으로" 같은 표현을 쓰면, 해당 내용을 하위 항목으로 배치
   - 하위 항목은 숫자 번호 대신 리스팅 형식(-)으로 작성
3. 승인 확인: "예/y를 입력하시면 답변 드리겠습니다."

규칙:
- 각 항목은 명확한 제목만 제시 (괄호 설명 금지)
- 목록의 상위 항목은 숫자 번호로 작성
- 하위 항목은 숫자 번호 대신 리스팅 형식(-)으로 작성
- 마크다운 서식 절대 사용 금지""",

            'final_confirmation': """사용자가 최종 구조를 승인했습니다.

이제 다시 한번 확인을 받으세요:
1. 제안한 구조를 간단히 요약
2. "이 구조로 답변을 드려도 될까요?" 형태로 최종 확인 요청

사용자가 "예"를 말하면 완전한 답변을 제공하세요.

규칙:
- 여전히 결과는 제공하지 말고 구조 확인만 하세요.
- 마크다운 서식 절대 사용 금지""",

            'final_answer': """사용자가 최종 답변 제공에 동의했습니다. 이제 완전한 답변을 제공하세요.

**중요: 사용자가 선택한 자료 유형 기반으로 작성**
- 제안한 구조에 맞춰 자연스럽게 작성
- 일반 텍스트 형식 유지 (마크다운 서식 사용 금지)
- 마지막에 사용자 피드백 요청으로 마무리"""
        }
        
        if stage == 'interruption':
            system_prompt = (
                "사용자의 즉흥 질문에 먼저 간단히 답하고, "
                "이전 요청을 계속 진행할지 예/아니오로 확인하세요. "
                "마크다운 서식 절대 사용 금지 - 일반 텍스트로만 작성하세요."
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
