from typing import Optional, Dict, Any, List
from services.gpt_service import GPTService
from database.db_manager import DBManager


class WorkflowManager:
    """Manages the 3-stage confirmation workflow."""
    
    STAGES = ['source_check', 'content_structure', 'final_approval']
    
    STAGE_DESCRIPTIONS = {
        'source_check': 'Stage 1: Source Check - Validating information sources',
        'content_structure': 'Stage 2: Content Structure - Organizing the response',
        'final_approval': 'Stage 3: Final Approval - Complete answer ready'
    }
    
    def __init__(self, gpt_service: GPTService, db_manager: DBManager):
        """Initialize workflow manager with services."""
        self.gpt_service = gpt_service
        self.db_manager = db_manager
    
    def start_workflow(self, conversation_id: int, user_query: str) -> Dict[str, Any]:
        """
        Start a new workflow for a user query.
        
        Args:
            conversation_id: ID of the conversation
            user_query: User's initial query
            
        Returns:
            Dict with stage info and GPT response
        """
        stage = self.STAGES[0]  # Start with source_check
        
        # Store user message
        self.db_manager.add_message(conversation_id, 'user', user_query)
        
        # Generate GPT response for the stage
        gpt_response = self.gpt_service.generate_stage_response(stage, user_query)
        
        # Store GPT response
        self.db_manager.add_message(conversation_id, 'assistant', gpt_response)
        
        # Record workflow state
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id,
            stage=stage,
            user_input=user_query,
            gpt_response=gpt_response
        )
        
        return {
            'stage': stage,
            'stage_number': 1,
            'stage_description': self.STAGE_DESCRIPTIONS[stage],
            'response': gpt_response,
            'awaiting_approval': True
        }
    
    def process_approval(
        self,
        conversation_id: int,
        approval: str
    ) -> Dict[str, Any]:
        """
        Process user approval (y/n) for current stage.
        
        Args:
            conversation_id: ID of the conversation
            approval: User approval ('y' or 'n')
            
        Returns:
            Dict with next stage info or completion status
        """
        # Get latest workflow state
        latest_state = self.db_manager.get_latest_workflow_state(conversation_id)
        
        if not latest_state:
            return {
                'error': 'No active workflow found',
                'completed': True
            }
        
        current_stage = latest_state['stage']
        current_stage_index = self.STAGES.index(current_stage)
        
        # Update the latest workflow state with approval
        self.db_manager.update_workflow_approval(latest_state['id'], approval)
        
        # Store user approval message
        approval_msg = f"{'Approved' if approval.lower() == 'y' else 'Rejected'} - {self.STAGE_DESCRIPTIONS[current_stage]}"
        self.db_manager.add_message(conversation_id, 'user', approval_msg)
        
        # If user rejected, restart the workflow
        if approval.lower() != 'y':
            return {
                'stage': current_stage,
                'stage_number': current_stage_index + 1,
                'stage_description': self.STAGE_DESCRIPTIONS[current_stage],
                'message': 'Stage rejected. Please provide a new query to restart.',
                'awaiting_approval': False,
                'rejected': True
            }
        
        # If approved and not at final stage, move to next stage
        if current_stage_index < len(self.STAGES) - 1:
            next_stage = self.STAGES[current_stage_index + 1]
            
            # Get conversation history for context
            messages = self.db_manager.get_conversation_messages(conversation_id)
            original_query = messages[0]['content'] if messages else ''
            
            # Get approved responses from previous stages
            workflow_history = self.db_manager.get_workflow_history(conversation_id)
            approved_responses = [
                state['gpt_response'] 
                for state in workflow_history 
                if state['user_approval'] == 'y' and state['gpt_response']
            ]
            
            # Generate response for next stage
            if approved_responses:
                gpt_response = self.gpt_service.refine_based_on_context(
                    next_stage,
                    original_query,
                    approved_responses
                )
            else:
                gpt_response = self.gpt_service.generate_stage_response(
                    next_stage,
                    original_query
                )
            
            # Store GPT response
            self.db_manager.add_message(conversation_id, 'assistant', gpt_response)
            
            # Record workflow state
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id,
                stage=next_stage,
                gpt_response=gpt_response
            )
            
            return {
                'stage': next_stage,
                'stage_number': current_stage_index + 2,
                'stage_description': self.STAGE_DESCRIPTIONS[next_stage],
                'response': gpt_response,
                'awaiting_approval': True
            }
        
        # If approved and at final stage, workflow is complete
        else:
            self.db_manager.update_conversation_status(conversation_id, 'completed')
            
            return {
                'stage': 'completed',
                'stage_number': 3,
                'message': 'Workflow completed! All stages approved.',
                'awaiting_approval': False,
                'completed': True
            }
    
    def get_current_stage(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """Get the current workflow stage for a conversation."""
        latest_state = self.db_manager.get_latest_workflow_state(conversation_id)
        
        if not latest_state:
            return None
        
        stage = latest_state['stage']
        stage_index = self.STAGES.index(stage) if stage in self.STAGES else -1
        
        return {
            'stage': stage,
            'stage_number': stage_index + 1,
            'stage_description': self.STAGE_DESCRIPTIONS.get(stage, 'Unknown stage'),
            'awaiting_approval': latest_state.get('user_approval') is None
        }
