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

## 📚 {user_message}에 대한 답변

### 1. 개요
[MOCK] 여기에는 기본 개념과 배경에 대한 설명이 들어갑니다. 실제 GPT를 사용하면 훨씬 더 자세하고 정확한 정보가 제공됩니다.

### 2. 핵심 내용
[MOCK] 주제에 대한 상세한 설명과 구체적인 예시가 포함됩니다.

### 3. 실용적 적용
[MOCK] 이론을 실제로 어떻게 활용할 수 있는지에 대한 가이드가 제공됩니다.

### 4. 추가 참고사항
[MOCK] 더 깊이 공부하고 싶을 때 참고할 수 있는 자료나 정보를 안내합니다.

---

이 정도면 충분하신가요? 추가로 궁금하신 점이 있으시면 언제든 물어보세요! 😊"""
        
        else:
            return f"안녕하세요! '{user_message}'에 대해 도움을 드리겠습니다. 어떤 점이 궁금하신가요?"
   - Examples and applications

**III. Conclusion**
   - Summary of key points
   - Implications and future considerations

This structure will help organize the information logically and comprehensively.
            """.strip(),
            
            'final_approval': f"""
**Complete Answer to: "{user_query}"**

Based on the approved sources and structure, here is a comprehensive response:

**Introduction:**
This topic is important because it addresses fundamental questions in the field. Understanding these concepts provides valuable insights.

**Main Content:**
The key aspects to consider are:
- First, we need to understand the foundational concepts
- Second, we should examine real-world applications
- Third, we must consider the broader implications

**Practical Applications:**
This knowledge can be applied in various scenarios, from academic research to practical implementations in industry.

**Conclusion:**
In summary, this is a multifaceted topic that requires careful consideration of multiple perspectives. The information from reliable sources confirms that a structured approach yields the best understanding.

This response synthesizes information from academic sources and provides a comprehensive answer to your query.
            """.strip()
        }
        
        return stage_responses.get(stage, self.generate_response([{"role": "user", "content": user_query}]))
    
    def refine_based_on_context(
        self,
        stage: str,
        original_query: str,
        previous_responses: List[str]
    ) -> str:
        """Generate a mock refined response."""
        return self.generate_stage_response(stage, original_query)
