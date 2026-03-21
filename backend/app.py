import os
from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
from services.mock_gpt_service import MockGPTService
from services.workflow_manager import WorkflowManager
from database.db_manager import DBManager

# Load environment variables
load_dotenv()

app = Flask(__name__, 
            template_folder='../frontend',
            static_folder='../frontend')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize services
db_manager = DBManager(os.getenv('DATABASE_PATH', 'database/chatbot.db'))
gpt_service = MockGPTService()  # Using mock service for testing
workflow_manager = WorkflowManager(gpt_service, db_manager)


def _build_choices_for_stage(stage: str):
    """Return frontend-friendly selectable choices by workflow stage."""
    if stage == 'source_planning':
        return [
            {'id': '1', 'label': '학술 논문', 'value': '1번 학술 논문으로 진행해줘'},
            {'id': '2', 'label': '정부/공신력 기관', 'value': '2번 정부/공신력 기관 자료로 진행해줘'},
            {'id': '3', 'label': '뉴스', 'value': '3번 뉴스 자료로 진행해줘'},
            {'id': '4', 'label': '블로그/소셜', 'value': '4번 블로그 및 소셜 미디어 자료로 진행해줘'},
            {'id': 'custom', 'label': '기타 (직접 입력)', 'value': ''}
        ]

    if stage in ('structure_proposal', 'final_confirmation', 'interruption'):
        return [
            {'id': 'yes', 'label': '예', 'value': '예'},
            {'id': 'no', 'label': '아니오/수정 요청', 'value': '아니오, 수정하고 싶어'}
        ]

    return []


@app.route('/')
def index():
    """Serve the main chatbot interface."""
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    """Handle favicon requests."""
    return '', 204


@app.route('/api/start', methods=['POST'])
def start_conversation():
    """Start a new conversation and workflow."""
    data = request.get_json()
    user_query = data.get('query', '').strip()
    
    if not user_query:
        return jsonify({'error': 'Query is required'}), 400
    
    # Create new conversation
    conversation_id = db_manager.create_conversation()
    session['conversation_id'] = conversation_id
    
    try:
        # Start workflow
        result = workflow_manager.start_workflow(conversation_id, user_query)
        
        return jsonify({
            'conversation_id': conversation_id,
            'stage': result['stage'],
            'stage_number': result['stage_number'],
            'stage_description': result['stage_description'],
            'response': result['response'],
            'awaiting_approval': result['awaiting_approval'],
            'choices': _build_choices_for_stage(result.get('stage'))
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """Continue conversation."""
    data = request.get_json()
    user_message = data.get('message', '').strip()
    conversation_id = session.get('conversation_id')
    
    if not conversation_id:
        return jsonify({'error': 'No active conversation'}), 400
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
    
    try:
        result = workflow_manager.process_message(conversation_id, user_message)
        
        return jsonify({
            'response': result['response'],
            'stage': result.get('stage'),
            'stage_number': result.get('stage_number'),
            'awaiting_approval': result.get('awaiting_approval', False),
            'choices': _build_choices_for_stage(result.get('stage'))
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/approve', methods=['POST'])
def approve_stage():
    """Process user approval for current stage."""
    data = request.get_json()
    approval = data.get('approval', '').strip().lower()
    conversation_id = session.get('conversation_id')
    
    if not conversation_id:
        return jsonify({'error': 'No active conversation'}), 400
    
    if approval not in ['y', 'n']:
        return jsonify({'error': 'Approval must be "y" or "n"'}), 400
    
    try:
        result = workflow_manager.process_approval(conversation_id, approval)

        result['choices'] = _build_choices_for_stage(result.get('stage'))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/history', methods=['GET'])
def get_history():
    """Get conversation history."""
    conversation_id = session.get('conversation_id')
    
    if not conversation_id:
        return jsonify({'messages': [], 'workflow_history': []})
    
    try:
        messages = db_manager.get_conversation_messages(conversation_id)
        workflow_history = db_manager.get_workflow_history(conversation_id)
        
        return jsonify({
            'messages': messages,
            'workflow_history': workflow_history
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    """Reset the current conversation."""
    session.pop('conversation_id', None)
    return jsonify({'message': 'Conversation reset successfully'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
