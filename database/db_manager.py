import sqlite3
import os
from datetime import datetime
from typing import Optional, List, Dict, Any


class DBManager:
    """Manages SQLite database operations for the chatbot."""
    
    def __init__(self, db_path: str = "database/chatbot.db"):
        """Initialize database manager and create tables if they don't exist."""
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()
    
    def get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        """Initialize database tables."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        ''')
        
        # Workflow state table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                stage TEXT NOT NULL,
                user_input TEXT,
                gpt_response TEXT,
                user_approval TEXT,
                source_selection TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_conversation(self) -> int:
        """Create a new conversation and return its ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO conversations DEFAULT VALUES')
        conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return conversation_id
    
    def add_message(self, conversation_id: int, role: str, content: str) -> int:
        """Add a message to a conversation."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)',
            (conversation_id, role, content)
        )
        message_id = cursor.lastrowid
        
        # Update conversation's updated_at timestamp
        cursor.execute(
            'UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (conversation_id,)
        )
        
        conn.commit()
        conn.close()
        return message_id
    
    def get_conversation_messages(self, conversation_id: int) -> List[Dict[str, Any]]:
        """Get all messages for a conversation."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC',
            (conversation_id,)
        )
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages
    
    def add_workflow_state(
        self,
        conversation_id: int,
        stage: str,
        user_input: Optional[str] = None,
        gpt_response: Optional[str] = None,
        user_approval: Optional[str] = None,
        source_selection: Optional[str] = None
    ) -> int:
        """Add a workflow state entry."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO workflow_state 
               (conversation_id, stage, user_input, gpt_response, user_approval, source_selection) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (conversation_id, stage, user_input, gpt_response, user_approval, source_selection)
        )
        state_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return state_id
    
    def update_workflow_approval(self, state_id: int, user_approval: str):
        """Update the user approval for a workflow state."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE workflow_state SET user_approval = ? WHERE id = ?',
            (user_approval, state_id)
        )
        conn.commit()
        conn.close()
    
    def get_workflow_history(self, conversation_id: int) -> List[Dict[str, Any]]:
        """Get workflow history for a conversation."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM workflow_state WHERE conversation_id = ? ORDER BY created_at ASC',
            (conversation_id,)
        )
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return history
    
    def get_latest_workflow_state(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """Get the latest workflow state for a conversation."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM workflow_state WHERE conversation_id = ? ORDER BY created_at DESC LIMIT 1',
            (conversation_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def update_conversation_status(self, conversation_id: int, status: str):
        """Update conversation status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE conversations SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (status, conversation_id)
        )
        conn.commit()
        conn.close()
    
    def get_all_conversations(self) -> List[Dict[str, Any]]:
        """Get all conversations."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM conversations ORDER BY updated_at DESC')
        conversations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return conversations
