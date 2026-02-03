from typing import Dict, Any
from services.gpt_service import GPTService
from database.db_manager import DBManager


class WorkflowManager:
    """Manages natural conversation workflow with implicit 3-stage confirmation."""

    STAGES = [
        'source_planning',
        'structure_proposal',
        'structure_refinement',
        'interruption',
        'final_answer'
    ]

    STAGE_DESCRIPTIONS = {
        'source_planning': 'Understanding your question and planning sources',
        'structure_proposal': 'Proposing answer structure',
        'structure_refinement': 'Refining answer structure',
        'interruption': 'Answering an interruption and confirming resumption',
        'final_answer': 'Providing final answer'
    }
    
    def __init__(self, gpt_service: GPTService, db_manager: DBManager):
        """Initialize workflow manager with services."""
        self.gpt_service = gpt_service
        self.db_manager = db_manager
    
    def start_workflow(self, conversation_id: int, user_query: str) -> Dict[str, Any]:
        """
        Start a new workflow with initial user query.
        
        Args:
            conversation_id: ID of the conversation
            user_query: User's initial query
            
        Returns:
            Dict with stage info and response
        """
        return self.process_message(conversation_id, user_query)
    
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

        # Determine approval intent from user message
        user_approval = self._classify_user_approval(user_message)

        # Update latest workflow state approval if applicable
        latest_state = self.db_manager.get_latest_workflow_state(conversation_id)
        if latest_state and user_approval in ("yes", "no"):
            self.db_manager.update_workflow_approval(latest_state["id"], user_approval)

        # Get conversation history
        messages = self.db_manager.get_conversation_messages(conversation_id)

        # Handle interruptions: answer the spontaneous question, then ask to resume
        if (
            latest_state
            and latest_state.get('stage') in ('source_planning', 'structure_proposal', 'structure_refinement')
            and user_approval == "unknown"
        ):
            response = self.gpt_service.generate_conversational_response(
                stage='interruption',
                user_message=user_message,
                conversation_history=messages,
                previous_request=latest_state.get('user_input')
            )

            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id,
                stage='interruption',
                user_input=user_message,
                gpt_response=response
            )

            return {
                'response': response,
                'stage': 'interruption',
                'stage_number': 2,
                'awaiting_approval': True,
                'stage_description': self._get_stage_description('interruption')
            }

        workflow_state = self._determine_workflow_stage(conversation_id, latest_state, user_approval)

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
            'stage': workflow_state['stage'],
            'stage_number': workflow_state['stage_number'],
            'awaiting_approval': True,
            'stage_description': self._get_stage_description(workflow_state['stage'])
        }
    
    def _determine_workflow_stage(
        self,
        conversation_id: int,
        latest_state: Dict[str, Any],
        user_approval: str
    ) -> Dict[str, Any]:
        """
        Determine current workflow stage based on latest workflow state and approval.

        Stage progression logic:
        - Stage 1 (source_planning): Ask source scope and confirm approach
        - Stage 2 (structure_proposal): Propose answer outline and confirm
        - Stage 2b (structure_refinement): If user requests changes, re-propose outline
        - Stage 3 (final_answer): Provide final answer with sources
        """
        if not latest_state:
            return {'stage': 'source_planning', 'stage_number': 1}

        stage = latest_state.get('stage')
        if stage == 'interruption':
            previous_state = self._get_last_non_interruption_state(conversation_id)
            stage = previous_state.get('stage') if previous_state else 'source_planning'

        if stage == 'source_planning':
            if user_approval == 'yes':
                return {'stage': 'structure_proposal', 'stage_number': 2}
            return {'stage': 'source_planning', 'stage_number': 1}

        if stage == 'structure_proposal':
            if user_approval == 'yes':
                return {'stage': 'final_answer', 'stage_number': 3}
            if user_approval == 'no':
                return {'stage': 'structure_refinement', 'stage_number': 2}
            return {'stage': 'structure_proposal', 'stage_number': 2}

        if stage == 'structure_refinement':
            if user_approval == 'yes':
                return {'stage': 'final_answer', 'stage_number': 3}
            return {'stage': 'structure_refinement', 'stage_number': 2}

        if stage == 'final_answer':
            return {'stage': 'source_planning', 'stage_number': 1}

        return {'stage': 'source_planning', 'stage_number': 1}

    def _get_last_non_interruption_state(self, conversation_id: int) -> Dict[str, Any]:
        """Get the latest workflow state excluding interruption entries."""
        history = self.db_manager.get_workflow_history(conversation_id)
        for item in reversed(history):
            if item.get('stage') != 'interruption':
                return item
        return {}

    def _classify_user_approval(self, user_message: str) -> str:
        """Classify user approval intent (yes/no/unknown)."""
        message = user_message.strip().lower()
        yes_patterns = ["예", "네", "응", "그래", "좋아", "okay", "ok", "y", "yes"]
        no_patterns = ["아니", "아니오", "아니요", "싫", "n", "no"]

        if any(token in message for token in yes_patterns):
            return "yes"
        if any(token in message for token in no_patterns):
            return "no"
        return "unknown"
    
    def _get_stage_description(self, stage: str) -> str:
        """Get human-readable description of workflow stage."""
        return self.STAGE_DESCRIPTIONS.get(stage, 'Processing')
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

