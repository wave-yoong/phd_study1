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
    
    def generate_stage_response(self, stage: str, user_query: str) -> str:
        """Generate a mock stage-specific response."""
        stage_responses = {
            'source_check': f"""
Based on your query "{user_query}", I recommend the following sources:

1. **Academic Databases**: Check Google Scholar, JSTOR, or IEEE Xplore for peer-reviewed articles
2. **Official Documentation**: Look for official websites and documentation related to your topic
3. **Reputable Publications**: Consider sources from established journals and publications

These sources will provide reliable, verifiable information to address your question.
            """.strip(),
            
            'content_structure': f"""
Here's a structured approach to answer "{user_query}":

**I. Introduction**
   - Brief overview of the topic
   - Context and importance

**II. Main Content**
   - Key concepts and definitions
   - Detailed explanation
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
