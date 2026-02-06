"""
Mock GPT Service for testing without OpenAI API key.
"""

from typing import List, Dict


class MockGPTService:
    """Mock service that simulates GPT responses without calling OpenAI API."""
    
    def __init__(self, api_key: str = None):
        """Initialize mock GPT service."""
        self.api_key = api_key or "mock-api-key"
        self.model = "gpt-3.5-turbo (mock)"
    
    def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Generate a mock response."""
        # Return predefined responses based on message content
        last_message = messages[-1]['content'].lower() if messages else ""
        
        return f"[MOCK RESPONSE] This is a simulated GPT response to: '{last_message}'. In production, this would be a real AI-generated response from OpenAI GPT-3.5-turbo."
    
    def generate_conversational_response(
        self,
        stage: str,
        user_message: str,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """Generate a natural conversational mock response based on stage."""
        
        if stage == 'source_planning':
            return f"""네, "{user_message}"에 대해 알려드리겠습니다!

먼저 이 주제에 대해 정확한 정보를 찾기 위해 다음과 같은 방향으로 조사하면 좋을 것 같아요:

1. 학술 데이터베이스 (Google Scholar, 논문 검색)
2. 공식 문서와 신뢰할 수 있는 출처
3. 최신 연구 동향

이런 방향으로 정보를 찾아보는 게 어떨까요? 다른 방향을 원하시나요?"""
        
        elif stage == 'structure_proposal':
            return f"""좋습니다! 그럼 이렇게 정리해서 설명드리면 어떨까요?

📋 **답변 구성안**

1. **개요**: 기본 개념 소개
2. **핵심 내용**: 자세한 설명과 예시
3. **실용적 적용**: 실제로 어떻게 활용할 수 있는지
4. **추가 참고사항**: 더 알아두면 좋은 정보

이렇게 구조를 잡으면 체계적으로 이해하기 좋을 것 같은데, 괜찮으신가요?"""
        
        elif stage == 'final_answer':
            return f"""완벽합니다! 그럼 제안한 구조대로 자세히 설명드릴게요.

{user_message}에 대한 답변

1. 개요
여기에는 기본 개념과 배경에 대한 설명이 들어갑니다. 실제 GPT를 사용하면 훨씬 더 자세하고 정확한 정보가 제공됩니다.
[출처: Smith et al.(2023) - Understanding Core Concepts, Journal of Research, 45(3), pp.112-128]

2. 핵심 내용
주제에 대한 상세한 설명과 구체적인 예시가 포함됩니다. 최신 연구에 따르면 이러한 접근 방식이 가장 효과적인 것으로 나타났습니다.
[출처: 한국연구재단 - 핵심 연구 동향 보고서, 2023년 12월]

3. 실용적 적용
이론을 실제로 어떻게 활용할 수 있는지에 대한 가이드가 제공됩니다. 전문가들은 단계별 접근을 권장하고 있습니다.
[출처: 한겨레 - 전문가 인터뷰: 실용적 활용법, 2024년 1월 20일]

4. 추가 참고사항
더 깊이 공부하고 싶을 때 참고할 수 있는 자료나 정보를 안내합니다. 관련 분야의 최신 동향을 계속 확인하시는 것을 추천드립니다.
[일반적으로 알려진 정보이며, 전문가와 상담을 권장합니다]

참고 자료:
1. Smith et al.(2023) - Understanding Core Concepts, Journal of Research, 45(3)
2. 한국연구재단 - 핵심 연구 동향 보고서, 2023
3. 한겨레 - 전문가 인터뷰: 실용적 활용법, 2024년 1월
4. 대한학회 - 실무 가이드라인, 2023

(위 자료는 해당 기관 웹사이트나 학술 데이터베이스에서 검색하실 수 있습니다)

이 정도면 충분하신가요? 추가로 궁금하신 점이 있으시면 언제든 물어보세요!"""
        
        else:
            return f"안녕하세요! '{user_message}'에 대해 도움을 드리겠습니다. 어떤 점이 궁금하신가요?"
