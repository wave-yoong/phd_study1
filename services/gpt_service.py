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
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Generate a natural conversational response that implicitly guides through workflow stages.
        
        Args:
            stage: Current workflow stage ('source_planning', 'structure_proposal', 'final_answer')
            user_message: Latest user message
            conversation_history: Full conversation history
            
        Returns:
            Contextual conversational response
        """
        stage_instructions = {
            'source_planning': """당신은 친절한 연구 조수입니다. 사용자의 질문을 받으면:
1. 질문을 명확히 이해했는지 확인
2. 어떤 출처나 방법으로 정보를 찾을지 자연스럽게 제안
3. 사용자가 동의하는지 물어보기 (예: "이런 방향으로 찾아보는게 좋을까요?")

자연스럽고 대화하듯이 응답하세요. "Stage 1" 같은 단계 표시는 하지 마세요.""",
            
            'structure_proposal': """사용자가 첫 번째 제안에 동의했습니다. 이제:
1. 답변을 어떻게 구성할지 간단한 아웃라인 제시
2. 어떤 순서로 설명할지 제안
3. 이 구조가 괜찮은지 자연스럽게 확인 (예: "이렇게 정리하면 어떨까요?")

친근하고 대화하듯이 응답하세요.""",
            
            'final_answer': """사용자가 구조에도 동의했습니다. 이제:
1. 제안한 구조대로 완전한 답변 제공
2. 명확하고 체계적으로 설명
3. 마지막에 추가로 궁금한 점이 있는지 물어보기

전문적이면서도 친근하게 응답하세요."""
        }
        
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

