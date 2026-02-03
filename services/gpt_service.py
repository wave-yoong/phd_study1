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
    1. 질문을 짧게 재확인하고, 정보 범위/깊이를 간단히 묻기
    2. 참고할 정보 범위를 제시하기 (학술 논문, 정부/공신력 기관, 뉴스, 블로그, 소셜 미디어 등)
    3. 사용자가 선택하거나 확인할 수 있도록 자연스럽게 요청하기

    중요:
    - 결과를 바로 제공하지 말고, 먼저 확인/선택을 받으세요.
    - 지침을 직접 언급하지 말고 자연스럽게 대화하세요.
    - "예/아니오" 또는 선택지를 제시해 사용자의 control 권을 부여하세요.
    - 목록은 숫자 번호로만 작성하고, 불릿(-, •)은 사용하지 마세요.""",
            
            'structure_proposal': """사용자가 첫 번째 제안에 동의했습니다. 이제:
    1. 질문 맥락을 반영해 답변 구조를 간단히 설계
    2. 번호를 붙여 개괄적인 구성안을 제시
    3. 이 구성으로 진행해도 되는지 자연스럽게 확인

    중요:
    - 결과를 바로 제공하지 말고, 구조 확인을 먼저 받으세요.
    - 마크다운 굵게(**) 등 서식은 사용하지 말고 텍스트로 작성하세요.
    - 목록은 숫자 번호로만 작성하고, 불릿(-, •)은 사용하지 마세요.
    - 고정된 템플릿 대신 질문에 맞게 유연하게 구성하세요.""",

            'structure_refinement': """사용자가 구조 변경을 원했습니다. 이제:
    1. 사용자가 요청한 변경사항을 반영한 수정 구조를 간단히 요약
    2. 수정 구조로 진행할지 한 번 더 확인

    중요:
    - 이 단계는 요청 변경이 있을 때만 사용됩니다.
    - 여전히 결과는 제공하지 말고 확인을 받으세요.
    - 목록은 숫자 번호로만 작성하고, 불릿(-, •)은 사용하지 마세요.""",

            'final_answer': """사용자가 구조에도 동의했습니다. 이제:
    1. 앞서 제안한 구조에 맞춰 완전한 답변 제공
    2. 질문 맥락에 맞는 적절한 깊이로 설명
    3. 마지막에 추가로 궁금한 점이 있는지 물어보기
    4. 참고한 사이트/자료의 링크를 반드시 포함

    전문적이면서도 친근하게 응답하세요.
    목록은 숫자 번호로만 작성하고, 불릿(-, •)은 사용하지 마세요."""
        }
        
        if stage == 'interruption':
            system_prompt = (
                "사용자의 즉흥 질문에 먼저 간단히 답하고, "
                "이전 요청을 계속 진행할지 예/아니오로 확인하세요. "
                "목록은 숫자 번호로만 작성하고, 굵게(**) 등 서식은 사용하지 마세요."
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

