import os
from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
from services.gpt_service import GPTService
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
gpt_service = GPTService(os.getenv('OPENAI_API_KEY'))
workflow_manager = WorkflowManager(gpt_service, db_manager)


@app.route('/')
def index():
    """Serve the main chatbot interface."""
    return render_template('index.html')


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
            'awaiting_approval': result['awaiting_approval']
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


@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """Get all conversations."""
    try:
        conversations = db_manager.get_all_conversations()
        return jsonify({'conversations': conversations})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset_conversation():
    """Reset the current conversation."""
    session.pop('conversation_id', None)
    return jsonify({'message': 'Conversation reset successfully'})


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'Flask Chatbot with 3-Stage Workflow'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
