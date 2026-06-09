import os
import sys
import random

# Allow running this file directly (e.g. `python backend/app.py` or VS Code's
# Run button) by ensuring the repository root is on sys.path for package imports.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
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


def _build_gpt_service():
    """Use the real LLM if configured, otherwise fall back to the mock agent.

    Set USE_MOCK_GPT=1 to force demo mode regardless of credentials.
    """
    if os.getenv('USE_MOCK_GPT', '').strip() in ('1', 'true', 'True'):
        from services.mock_gpt_service import MockGPTService
        return MockGPTService()

    try:
        from services.gpt_service import GPTService
        if os.getenv('AZURE_OPENAI_ENDPOINT'):
            return GPTService(use_azure=True)
        if os.getenv('OPENAI_API_KEY'):
            return GPTService(use_azure=False)
    except Exception as e:  # pragma: no cover - configuration fallback
        print(f"Falling back to mock GPT service: {e}")

    from services.mock_gpt_service import MockGPTService
    return MockGPTService()


gpt_service = _build_gpt_service()
workflow_manager = WorkflowManager(gpt_service, db_manager)


# Experimental condition labels.
CONDITION_CONTROL = 'control'   # user-control group
CONDITION_AUTO = 'auto'         # autonomous agent / no-control group


def _normalize_condition(raw: str) -> str:
    """Map incoming group labels to a canonical condition, or '' if unspecified."""
    value = (raw or '').strip().lower()
    if value in ('control', 'user_control', 'user-control', 'uc', 'high', '1'):
        return CONDITION_CONTROL
    if value in ('auto', 'autonomous', 'no_control', 'no-control', 'nc', 'low', '0'):
        return CONDITION_AUTO
    return ''


def _assign_condition(requested: str) -> str:
    """Use the requested condition if valid, otherwise random assignment."""
    normalized = _normalize_condition(requested)
    if normalized:
        return normalized
    return random.choice([CONDITION_CONTROL, CONDITION_AUTO])


def _build_choices(result: dict) -> list:
    """Build clickable control affordances. Only the control group gets levers."""
    if result.get('condition') != CONDITION_CONTROL:
        return []

    if result.get('post_plan'):
        return [
            {'id': 'override', 'label': '항목 수정 요청', 'value': ''},
            {'id': 'done', 'label': '이대로 확정', 'value': '이대로 좋아, 확정할게'},
        ]

    if result.get('resumable'):
        return [
            {'id': 'resume', 'label': '계속 진행', 'value': '계속 진행해줘'},
            {'id': 'modify', 'label': '수정해서 진행', 'value': ''},
        ]

    if result.get('controls_enabled'):
        return [
            {'id': 'approve', 'label': '승인하고 계속', 'value': '예, 계속 진행해줘'},
            {'id': 'modify', 'label': '이 항목 수정', 'value': ''},
            {'id': 'autonomy', 'label': '알아서 끝까지 진행', 'value': '알아서 끝까지 진행해줘'},
            {'id': 'interrupt', 'label': '중단', 'value': '잠깐 중단해줘'},
        ]

    return []


def _serialize(result: dict, **extra) -> dict:
    payload = {
        'response': result['response'],
        'stage': result.get('stage'),
        'stage_description': result.get('stage_description'),
        'condition': result.get('condition'),
        'autonomy_level': result.get('autonomy_level'),
        'agent_actions': result.get('agent_actions', []),
        'awaiting_input': result.get('awaiting_input', True),
        'choices': _build_choices(result),
    }
    payload.update(extra)
    return payload


@app.route('/')
def index():
    """Serve the main agent interface."""
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/api/start', methods=['POST'])
def start_conversation():
    """Start a new conversation, assigning an experimental condition."""
    data = request.get_json() or {}
    user_query = data.get('query', '').strip()

    if not user_query:
        return jsonify({'error': 'Query is required'}), 400

    requested = data.get('condition') or data.get('group') or request.args.get('group', '')
    condition = _assign_condition(requested)
    autonomy = 'high' if condition == CONDITION_AUTO else 'low'

    conversation_id = db_manager.create_conversation(condition=condition, autonomy_level=autonomy)
    session['conversation_id'] = conversation_id

    try:
        result = workflow_manager.start_workflow(conversation_id, user_query)
        return jsonify(_serialize(result, conversation_id=conversation_id))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """Continue the conversation."""
    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    conversation_id = session.get('conversation_id')

    if not conversation_id:
        return jsonify({'error': 'No active conversation'}), 400
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    try:
        result = workflow_manager.process_message(conversation_id, user_message)
        return jsonify(_serialize(result))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/history', methods=['GET'])
def get_history():
    """Get conversation history."""
    conversation_id = session.get('conversation_id')
    if not conversation_id:
        return jsonify({'messages': [], 'workflow_history': []})

    try:
        return jsonify({
            'messages': db_manager.get_conversation_messages(conversation_id),
            'workflow_history': db_manager.get_workflow_history(conversation_id),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    """Reset the current conversation."""
    session.pop('conversation_id', None)
    return jsonify({'message': 'Conversation reset successfully'})


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'gpt_service': gpt_service.model})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
