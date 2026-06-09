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
                status TEXT DEFAULT 'active',
                condition TEXT DEFAULT 'control',
                autonomy_level TEXT DEFAULT 'low'
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
                tool_name TEXT,
                intervention_type TEXT,
                autonomy_level TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
        ''')

        # Migrations for existing DBs created before newer columns were added
        cursor.execute("PRAGMA table_info(workflow_state)")
        workflow_columns = [row[1] for row in cursor.fetchall()]
        for col in ('source_selection', 'tool_name', 'intervention_type', 'autonomy_level'):
            if col not in workflow_columns:
                cursor.execute(f'ALTER TABLE workflow_state ADD COLUMN {col} TEXT')

        cursor.execute("PRAGMA table_info(conversations)")
        conversation_columns = [row[1] for row in cursor.fetchall()]
        if 'condition' not in conversation_columns:
            cursor.execute("ALTER TABLE conversations ADD COLUMN condition TEXT DEFAULT 'control'")
        if 'autonomy_level' not in conversation_columns:
            cursor.execute("ALTER TABLE conversations ADD COLUMN autonomy_level TEXT DEFAULT 'low'")

        conn.commit()
        conn.close()
    
    def create_conversation(self, condition: str = 'control', autonomy_level: str = 'low') -> int:
        """Create a new conversation and return its ID.

        Args:
            condition: Experimental condition ('control' = user-control group,
                       'auto' = autonomous agent / no-control group)
            autonomy_level: Initial agent autonomy ('low' = pause at each step,
                            'high' = run end-to-end). 'auto' condition is always 'high'.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO conversations (condition, autonomy_level) VALUES (?, ?)',
            (condition, autonomy_level)
        )
        conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return conversation_id

    def get_conversation(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """Get a single conversation row (including condition/autonomy)."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM conversations WHERE id = ?', (conversation_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def set_autonomy_level(self, conversation_id: int, autonomy_level: str):
        """Update the agent autonomy level for a conversation."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE conversations SET autonomy_level = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (autonomy_level, conversation_id)
        )
        conn.commit()
        conn.close()
    
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
            'SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC',
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
        source_selection: Optional[str] = None,
        tool_name: Optional[str] = None,
        intervention_type: Optional[str] = None,
        autonomy_level: Optional[str] = None
    ) -> int:
        """Add a workflow state entry.

        tool_name: which simulated agent tool ran at this step (e.g. 'calorie_calculator').
        intervention_type: user control action ('approve', 'modify', 'interrupt',
                           'raise_autonomy', 'override') — key DV for the control group.
        autonomy_level: agent autonomy in effect when this step was produced.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO workflow_state
               (conversation_id, stage, user_input, gpt_response, user_approval,
                source_selection, tool_name, intervention_type, autonomy_level)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (conversation_id, stage, user_input, gpt_response, user_approval,
             source_selection, tool_name, intervention_type, autonomy_level)
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
            'SELECT * FROM workflow_state WHERE conversation_id = ? ORDER BY id ASC',
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
            'SELECT * FROM workflow_state WHERE conversation_id = ? ORDER BY id DESC LIMIT 1',
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
