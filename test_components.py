#!/usr/bin/env python3
"""
Simple test script to verify the chatbot components work correctly.
This tests the database and workflow logic without requiring OpenAI API.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_manager import DBManager


def test_database():
    """Test database operations."""
    print("Testing Database Manager...")
    
    # Use a test database
    db = DBManager('database/test_chatbot.db')
    
    # Test creating a conversation
    conv_id = db.create_conversation()
    print(f"✓ Created conversation with ID: {conv_id}")
    
    # Test adding messages
    msg_id1 = db.add_message(conv_id, 'user', 'What is AI?')
    print(f"✓ Added user message with ID: {msg_id1}")
    
    msg_id2 = db.add_message(conv_id, 'assistant', 'AI is artificial intelligence...')
    print(f"✓ Added assistant message with ID: {msg_id2}")
    
    # Test retrieving messages
    messages = db.get_conversation_messages(conv_id)
    assert len(messages) == 2, "Should have 2 messages"
    print(f"✓ Retrieved {len(messages)} messages")
    
    # Test workflow state
    state_id = db.add_workflow_state(
        conversation_id=conv_id,
        stage='source_check',
        user_input='What is AI?',
        gpt_response='AI is...',
        user_approval='y'
    )
    print(f"✓ Added workflow state with ID: {state_id}")
    
    # Test retrieving workflow history
    history = db.get_workflow_history(conv_id)
    assert len(history) == 1, "Should have 1 workflow state"
    print(f"✓ Retrieved {len(history)} workflow states")
    
    # Test getting latest workflow state
    latest = db.get_latest_workflow_state(conv_id)
    assert latest is not None, "Should have a latest state"
    assert latest['stage'] == 'source_check', "Stage should be source_check"
    print(f"✓ Retrieved latest workflow state: {latest['stage']}")
    
    # Test updating conversation status
    db.update_conversation_status(conv_id, 'completed')
    print(f"✓ Updated conversation status to 'completed'")
    
    # Test getting all conversations
    conversations = db.get_all_conversations()
    assert len(conversations) > 0, "Should have at least 1 conversation"
    print(f"✓ Retrieved {len(conversations)} conversations")
    
    print("\n✅ All database tests passed!")
    
    # Cleanup
    import os
    if os.path.exists('database/test_chatbot.db'):
        os.remove('database/test_chatbot.db')
        print("✓ Cleaned up test database")


def test_workflow_stages():
    """Test workflow manager stages."""
    print("\nTesting Workflow Manager...")
    
    from services.workflow_manager import WorkflowManager
    
    # Check that stages are properly defined
    assert len(WorkflowManager.STAGES) == 3, "Should have 3 stages"
    print(f"✓ Workflow has {len(WorkflowManager.STAGES)} stages")
    
    for i, stage in enumerate(WorkflowManager.STAGES, 1):
        desc = WorkflowManager.STAGE_DESCRIPTIONS.get(stage)
        print(f"  Stage {i}: {stage} - {desc}")
    
    print("✅ Workflow configuration is correct!")


def test_imports():
    """Test that all modules can be imported."""
    print("\nTesting Module Imports...")
    
    try:
        from database.db_manager import DBManager
        print("✓ database.db_manager imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import database.db_manager: {e}")
        return False
    
    try:
        from services.gpt_service import GPTService
        print("✓ services.gpt_service imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import services.gpt_service: {e}")
        return False
    
    try:
        from services.workflow_manager import WorkflowManager
        print("✓ services.workflow_manager imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import services.workflow_manager: {e}")
        return False
    
    print("✅ All modules imported successfully!")
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("Flask 3-Stage Chatbot - Component Tests")
    print("=" * 60)
    
    if not test_imports():
        sys.exit(1)
    
    test_workflow_stages()
    test_database()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
    print("\nThe chatbot components are working correctly.")
    print("To run the full application:")
    print("  1. Copy .env.example to .env")
    print("  2. Add your OPENAI_API_KEY to .env")
    print("  3. Run: cd backend && python app.py")
    print("  4. Open http://localhost:5000 in your browser")
