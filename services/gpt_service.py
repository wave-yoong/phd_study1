import os
from openai import OpenAI
from typing import List, Dict


class GPTService:
    """Service for interacting with OpenAI GPT API."""
    
    def __init__(self, api_key: str = None):
        """Initialize GPT service with API key."""
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
    
    def generate_stage_response(self, stage: str, user_query: str) -> str:
        """
        Generate a stage-specific response.
        
        Args:
            stage: Current workflow stage ('source_check', 'content_structure', 'final_approval')
            user_query: User's input query
            
        Returns:
            Stage-appropriate GPT response
        """
        stage_prompts = {
            'source_check': (
                "You are a helpful assistant in the source checking stage. "
                "The user has provided a query. Respond by acknowledging their query "
                "and suggesting reliable sources or approaches to find information. "
                "Keep your response concise and focused on source validation."
            ),
            'content_structure': (
                "You are a helpful assistant in the content structuring stage. "
                "Based on the approved sources, provide a structured outline or "
                "framework for addressing the user's query. Keep it organized and clear."
            ),
            'final_approval': (
                "You are a helpful assistant providing the final response. "
                "Based on the approved sources and structure, provide a complete, "
                "well-organized answer to the user's query. Be comprehensive yet concise."
            )
        }
        
        system_prompt = stage_prompts.get(stage, stage_prompts['source_check'])
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]
        
        return self.generate_response(messages)
    
    def refine_based_on_context(
        self,
        stage: str,
        original_query: str,
        previous_responses: List[str]
    ) -> str:
        """
        Generate a refined response based on previous stage outputs.
        
        Args:
            stage: Current stage
            original_query: Original user query
            previous_responses: List of approved responses from previous stages
            
        Returns:
            Refined response incorporating previous context
        """
        context = "\n\n".join([
            f"Previous stage output:\n{resp}" 
            for resp in previous_responses
        ])
        
        messages = [
            {"role": "system", "content": f"You are at the {stage} stage."},
            {"role": "user", "content": f"Original query: {original_query}\n\n{context}\n\nProvide your response for this stage."}
        ]
        
        return self.generate_response(messages)
