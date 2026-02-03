#!/usr/bin/env python3
"""
Run the Flask chatbot application.
Supports both production mode (with OpenAI API) and demo mode (with mock responses).
"""

import os
import sys

# Add parent directory to path to allow imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Determine service to use
USE_AZURE = os.getenv('USE_AZURE', 'true').lower() == 'true'
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
DEMO_MODE = os.getenv('DEMO_MODE', 'false').lower() == 'true'

# Logging
if USE_AZURE:
    print(f"Azure OpenAI configured: {'yes' if AZURE_OPENAI_API_KEY else 'no'}")
    print(f"Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT', 'Not set')}")
    print(f"Deployment: {os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'Not set')}")
else:
    print(f"OpenAI API Key present: {'yes' if OPENAI_API_KEY else 'no'}")

# If no API key and not in demo mode, enable demo mode automatically
if not (AZURE_OPENAI_API_KEY if USE_AZURE else OPENAI_API_KEY) and not DEMO_MODE:
    print("⚠️  No API key found. Running in DEMO MODE.")
    if USE_AZURE:
        print("   Set AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME in .env to use Azure OpenAI.")
    else:
        print("   Set OPENAI_API_KEY in .env to use OpenAI API.")
    DEMO_MODE = True

# Import appropriate GPT service
if DEMO_MODE:
    from services.mock_gpt_service import MockGPTService as GPTService
    print("🎭 Running in DEMO MODE with mock responses")
else:
    from services.gpt_service import GPTService
    if USE_AZURE:
        print("🚀 Running with Azure OpenAI API")
    else:
        print("🚀 Running with OpenAI API")

from services.workflow_manager import WorkflowManager
from database.db_manager import DBManager

app = Flask(__name__, 
            template_folder='../frontend',
            static_folder='../frontend')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize services
db_manager = DBManager(os.getenv('DATABASE_PATH', 'database/chatbot.db'))
if DEMO_MODE:
    gpt_service = GPTService()
else:
    gpt_service = GPTService(
        api_key=AZURE_OPENAI_API_KEY if USE_AZURE else OPENAI_API_KEY,
        use_azure=USE_AZURE
    )
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
            'awaiting_approval': result['awaiting_approval'],
            'demo_mode': DEMO_MODE,
            'service': 'Azure OpenAI' if USE_AZURE and not DEMO_MODE else ('OpenAI' if not DEMO_MODE else 'Mock')
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
    service_type = 'Azure OpenAI' if USE_AZURE and not DEMO_MODE else ('OpenAI' if not DEMO_MODE else 'Mock')
    return jsonify({
        'status': 'healthy',
        'service': 'Flask Chatbot with 3-Stage Workflow',
        'service_type': service_type,
        'demo_mode': DEMO_MODE
    })


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Flask 3-Stage Chatbot Server")
    print("=" * 60)
    if DEMO_MODE:
        print(f"Mode: DEMO (Mock Responses)")
    elif USE_AZURE:
        print(f"Mode: PRODUCTION (Azure OpenAI API)")
    else:
        print(f"Mode: PRODUCTION (OpenAI API)")
    print(f"URL: http://localhost:5000")
    print("=" * 60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
