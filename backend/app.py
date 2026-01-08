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


@app.route('/')
def index():
    """Serve the main chatbot interface."""
    return render_template('index.html')


@app.route('/api/start', methods=['POST'])
def start_conversation():
    """Start a new conversation."""
    data = request.get_json()
    user_message = data.get('message', '').strip()
    
    if not user_message:
        session['conversation_id'] = conversation_id
    
    try:
        # Start workflow with initial message
        result = workflow_manager.process_message(conversation_id, user_message)
        
        return jsonify({
            'conversation_id': conversation_id,
            'response': result['response']
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
            'response': result['response']
        })
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
    return jsonify({'status': 'reset'})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
