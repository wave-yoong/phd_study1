from typing import Dict, Any
from services.gpt_service import GPTService
from database.db_manager import DBManager


class WorkflowManager:
    """Manages natural conversation workflow with implicit 3-stage confirmation."""
    
    def __init__(self, gpt_service: GPTService, db_manager: DBManager):
        """Initialize workflow manager with services."""
        self.gpt_service = gpt_service
        self.db_manager = db_manager
    
    def process_message(self, conversation_id: int, user_message: str) -> Dict[str, Any]:
        """
        Process user message and generate appropriate response based on conversation state.
        
        The workflow naturally progresses through 3 stages:
        1. Understanding & Source Planning - AI asks clarifying questions, suggests sources
        2. Content Structuring - AI proposes how to organize the answer
        3. Final Answer - AI provides complete answer and asks for confirmation
        
        Args:
            conversation_id: ID of the conversation
            user_message: User's message
            
        Returns:
            Dict with response
        """
        # Store user message
        self.db_manager.add_message(conversation_id, 'user', user_message)
        
        # Get conversation history
        messages = self.db_manager.get_conversation_messages(conversation_id)
        workflow_state = self._determine_workflow_stage(conversation_id, messages)
        
        # Generate contextual response based on workflow stage
        response = self.gpt_service.generate_conversational_response(
            stage=workflow_state['stage'],
            user_message=user_message,
            conversation_history=messages
        )
        
        # Store assistant response
        self.db_manager.add_message(conversation_id, 'assistant', response)
        
        # Update workflow state
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id,
            stage=workflow_state['stage'],
            user_input=user_message,
            gpt_response=response
        )
        
        return {
            'response': response,
            'stage': workflow_state['stage']
        }
    
    def _determine_workflow_stage(
        self,
        conversation_id: int,
        messages: list
    ) -> Dict[str, Any]:
        """
        Determine current workflow stage based on conversation history.
        
        Stage progression logic:
        - Stage 1 (source_planning): Initial query or early discussion
        - Stage 2 (structure_proposal): After user confirms approach (2-4 messages)
        - Stage 3 (final_answer): After user confirms structure (5+ messages)
        """
        message_count = len(messages)
        
        # Get latest workflow state
        latest_state = self.db_manager.get_latest_workflow_state(conversation_id)
        
        if message_count <= 2:
            # Initial stage: understanding and source planning
            return {'stage': 'source_planning', 'stage_number': 1}
        elif message_count <= 4:
            # Second stage: content structuring
            return {'stage': 'structure_proposal', 'stage_number': 2}
        else:
            # Final stage: complete answer
            return {'stage': 'final_answer', 'stage_number': 3}

