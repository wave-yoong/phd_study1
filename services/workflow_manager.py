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
        'final_confirmation',
        'final_answer',
        'post_final_followup',
        'post_final_input',
        'conversation_closed'
    ]

    STAGE_DESCRIPTIONS = {
        'source_planning': 'Understanding your question and planning sources',
        'structure_proposal': 'Proposing answer structure',
        'structure_refinement': 'Refining answer structure',
        'interruption': 'Answering an interruption and confirming resumption',
        'final_confirmation': 'Confirming final answer structure',
        'final_answer': 'Providing final answer',
        'post_final_followup': 'Checking if more information is needed',
        'post_final_input': 'Waiting for additional user instructions',
        'conversation_closed': 'Conversation closed'
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

        latest_state = self.db_manager.get_latest_workflow_state(conversation_id)
        current_stage = latest_state.get('stage') if latest_state else None
        if current_stage == 'interruption':
            previous_state = self._get_last_non_interruption_state(conversation_id)
            current_stage = previous_state.get('stage') if previous_state else 'source_planning'

        # Determine approval intent from user message (stage-aware)
        user_approval = self._classify_user_approval(user_message, current_stage)

        # Post-final follow-up: ask whether user wants additional info/modification
        if current_stage == 'post_final_followup':
            if user_approval == 'yes':
                response = '추가하거나 수정하고자 하시는 내용을 적어주세요.'
                self.db_manager.add_message(conversation_id, 'assistant', response)
                self.db_manager.add_workflow_state(
                    conversation_id=conversation_id,
                    stage='post_final_input',
                    user_input=user_message,
                    gpt_response=response,
                    user_approval='yes'
                )
                return {
                    'response': response,
                    'stage': 'post_final_input',
                    'stage_number': 6,
                    'awaiting_approval': True,
                    'stage_description': self._get_stage_description('post_final_input')
                }

            if user_approval == 'no':
                response = '감사합니다! 새로운 주제로 탐색하길 원하시면 New Chat 를 눌러주세요!'
                self.db_manager.add_message(conversation_id, 'assistant', response)
                self.db_manager.add_workflow_state(
                    conversation_id=conversation_id,
                    stage='conversation_closed',
                    user_input=user_message,
                    gpt_response=response,
                    user_approval='no'
                )
                return {
                    'response': response,
                    'stage': 'conversation_closed',
                    'stage_number': 7,
                    'awaiting_approval': False,
                    'stage_description': self._get_stage_description('conversation_closed')
                }

            response = '정보를 추가로 받길 원하시나요? 예/아니오로 답해주세요.'
            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id,
                stage='post_final_followup',
                user_input=user_message,
                gpt_response=response,
                user_approval='unknown'
            )
            return {
                'response': response,
                'stage': 'post_final_followup',
                'stage_number': 5,
                'awaiting_approval': True,
                'stage_description': self._get_stage_description('post_final_followup')
            }

        # User provided additional instructions after final answer
        if current_stage == 'post_final_input':
            response = self.gpt_service.generate_conversational_response(
                stage='final_answer',
                user_message=user_message,
                conversation_history=self.db_manager.get_conversation_messages(conversation_id)
            )
            response = response + '\n\n정보를 추가로 받길 원하시나요?'

            self.db_manager.add_message(conversation_id, 'assistant', response)
            self.db_manager.add_workflow_state(
                conversation_id=conversation_id,
                stage='post_final_followup',
                user_input=user_message,
                gpt_response=response
            )
            return {
                'response': response,
                'stage': 'post_final_followup',
                'stage_number': 5,
                'awaiting_approval': True,
                'stage_description': self._get_stage_description('post_final_followup')
            }

        # Update latest workflow state approval if applicable
        if latest_state and user_approval in ("yes", "no", "selection"):
            self.db_manager.update_workflow_approval(latest_state["id"], user_approval)
            # Store source selection if in source_planning stage
            if current_stage == 'source_planning' and user_approval == "selection":
                conn = self.db_manager.get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE workflow_state SET source_selection = ? WHERE id = ?',
                    (user_message, latest_state["id"])
                )
                conn.commit()
                conn.close()

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

        # If conversation was explicitly closed, next user message starts a new flow
        if latest_state and latest_state.get('stage') == 'conversation_closed':
            # Reset to source planning for new question
            workflow_state = {'stage': 'source_planning', 'stage_number': 1}
        else:
            workflow_state = self._determine_workflow_stage(conversation_id, latest_state, user_approval)

        # Generate contextual response based on workflow stage
        response = self.gpt_service.generate_conversational_response(
            stage=workflow_state['stage'],
            user_message=user_message,
            conversation_history=messages
        )
        
        # Store assistant response
        self.db_manager.add_message(conversation_id, 'assistant', response)
        
        # After final answer, immediately ask whether user wants additional info
        saved_stage = workflow_state['stage']
        saved_stage_number = workflow_state['stage_number']
        if workflow_state['stage'] == 'final_answer':
            response = response + '\n\n정보를 추가로 받길 원하시나요?'
            saved_stage = 'post_final_followup'
            saved_stage_number = 5

        # Update workflow state
        self.db_manager.add_workflow_state(
            conversation_id=conversation_id,
            stage=saved_stage,
            user_input=user_message,
            gpt_response=response
        )
        
        return {
            'response': response,
            'stage': saved_stage,
            'stage_number': saved_stage_number,
            'awaiting_approval': True,
            'stage_description': self._get_stage_description(saved_stage)
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
            # User selected sources or approved → move to structure proposal
            if user_approval in ('yes', 'selection'):
                return {'stage': 'structure_proposal', 'stage_number': 2}
            return {'stage': 'source_planning', 'stage_number': 1}

        if stage == 'structure_proposal':
            if user_approval == 'yes':
                return {'stage': 'final_answer', 'stage_number': 3}
            if user_approval == 'no':
                return {'stage': 'structure_refinement', 'stage_number': 2}
            # If user provided feedback without clear yes (unknown), treat as refinement request
            return {'stage': 'structure_refinement', 'stage_number': 2}

        if stage == 'structure_refinement':
            if user_approval == 'yes':
                return {'stage': 'final_confirmation', 'stage_number': 3}
            return {'stage': 'structure_refinement', 'stage_number': 2}

        if stage == 'final_confirmation':
            if user_approval == 'yes':
                return {'stage': 'final_answer', 'stage_number': 4}
            if user_approval == 'no':
                return {'stage': 'structure_refinement', 'stage_number': 2}
            return {'stage': 'final_confirmation', 'stage_number': 3}

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

    def _classify_user_approval(self, user_message: str, current_stage: str = None) -> str:
        """
        Classify user approval intent (yes/no/selection/unknown).
        
        Returns:
            'yes': User approves/confirms
            'no': User rejects or wants changes
            'selection': User is making a selection (numbers, lists)
            'unknown': Unclear intent (becomes 'yes' for stage progression)
        """
        message = user_message.strip().lower()
        
        # In refinement stage, only explicit yes should advance.
        # All other inputs are treated as modification feedback.
        if current_stage == 'structure_refinement':
            yes_patterns_refine = ["예", "네", "응", "그래", "좋아", "okay", "ok", "y", "yes", "진행", "맞아", "동의"]
            if any(token in message for token in yes_patterns_refine):
                return "yes"
            return "no"

        # Check for explicit rejections first
        no_patterns = ["아니", "아니오", "아니요", "싫", "변경", "수정", "바꿔", "다시", "n", "no"]
        if any(token in message for token in no_patterns):
            return "no"
        
        # Number-based selection is only valid during source planning stage
        import re
        has_numbers = bool(re.search(r'\d', message))
        selection_keywords = ["선택", "번", "원해", "하겠", "부탁"]
        has_selection = any(keyword in message for keyword in selection_keywords)
        if current_stage in (None, 'source_planning') and (has_numbers or has_selection):
            return "selection"
        
        # Check for structure modification requests (should be treated as "no")
        # Only applies when there are no numbers (i.e., not a source selection)
        modification_patterns = [
            "위주로", "중심으로", "중심으", "먼저", "우선", "대신", "만 ",
            "추가", "빼고", "빼줘", "제외", "말고", "포함", "넣어",
            "순서", "바꿔", "바꿔서", "바꿔줘"
        ]
        if any(pattern in message for pattern in modification_patterns):
            return "no"
        
        # Check for explicit approvals (must come after modification check)
        yes_patterns = ["예", "네", "응", "그래", "좋아", "okay", "ok", "y", "yes", "진행", "맞아", "동의"]
        # Only return yes if approval word appears without modification patterns
        if any(token in message for token in yes_patterns):
            return "yes"
        
        # (selection check already handled above)
        
        # If unclear but user provided a meaningful response, treat as unknown (not auto-yes)
        # This prevents unintended progression when user provides feedback
        return "unknown"

    def _get_stage_description(self, stage: str) -> str:
        """Get human-readable description of workflow stage."""
        return self.STAGE_DESCRIPTIONS.get(stage, 'Processing')

