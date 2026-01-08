# Flask 3-Stage Chatbot

A Flask-based chatbot application with a 3-stage confirmation workflow for PhD Study 1 - Effect of User Control.

## Features

- **3-Stage Workflow**: Every user query goes through three stages with approval requirements:
  1. **Source Check**: Validates information sources
  2. **Content Structure**: Organizes the response framework
  3. **Final Approval**: Delivers the complete answer

- **User Control**: Users must approve (y) or reject (n) each stage before proceeding
- **Conversation History**: All interactions are saved to SQLite database
- **Modern UI**: Clean, responsive web interface
- **OpenAI Integration**: Uses GPT-3.5-turbo for intelligent responses

## Project Structure

```
phd_study1/
├── backend/
│   └── app.py                    # Main Flask application
├── services/
│   ├── workflow_manager.py       # 3-stage workflow logic
│   └── gpt_service.py           # OpenAI API integration
├── database/
│   └── db_manager.py            # SQLite database manager
├── frontend/
│   └── index.html               # Web UI
├── .env.example                 # Environment variables template
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Database Schema

### Tables

1. **conversations**: Tracks conversation sessions
   - `id`, `created_at`, `updated_at`, `status`

2. **messages**: Stores all messages in conversations
   - `id`, `conversation_id`, `role`, `content`, `created_at`

3. **workflow_state**: Records workflow stage progression
   - `id`, `conversation_id`, `stage`, `user_input`, `gpt_response`, `user_approval`, `created_at`

## Installation

1. **Clone the repository**:
   ```bash
   cd /home/runner/work/phd_study1/phd_study1
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_actual_api_key_here
   FLASK_SECRET_KEY=your_secret_key_here
   DATABASE_PATH=database/chatbot.db
   ```

## Usage

1. **Start the Flask server**:
   ```bash
   cd backend
   python app.py
   ```

2. **Access the application**:
   - Open your browser to `http://localhost:5000`

3. **Using the chatbot**:
   - Enter a query in the input field
   - Review the Stage 1 (Source Check) response
   - Click "Approve (y)" to proceed or "Reject (n)" to restart
   - Continue through Stage 2 (Content Structure)
   - Complete with Stage 3 (Final Approval)

## API Endpoints

- `GET /` - Main chatbot interface
- `POST /api/start` - Start a new conversation with a query
- `POST /api/approve` - Approve or reject current stage
- `GET /api/history` - Get conversation history
- `GET /api/conversations` - Get all conversations
- `POST /api/reset` - Reset current conversation
- `GET /health` - Health check endpoint

## Development

The application uses:
- **Flask 3.0.0** - Web framework
- **OpenAI 1.6.1** - GPT API client
- **python-dotenv 1.0.0** - Environment variable management
- **SQLite3** - Database (built into Python)

## Configuration

Environment variables (`.env`):
- `OPENAI_API_KEY` - Your OpenAI API key (required)
- `FLASK_SECRET_KEY` - Flask session secret (required for production)
- `DATABASE_PATH` - Path to SQLite database (default: `database/chatbot.db`)

## How It Works

1. **User submits a query** → Creates a new conversation in the database
2. **Stage 1: Source Check** → GPT generates a response focused on sources
3. **User approves/rejects** → Recorded in workflow_state table
4. **Stage 2: Content Structure** → GPT creates structured outline based on approved sources
5. **User approves/rejects** → Recorded in workflow_state table
6. **Stage 3: Final Approval** → GPT delivers complete answer
7. **User approves** → Workflow completed, conversation marked as complete

If the user rejects at any stage, they can restart with a new query.

## License

This project is part of PhD Study 1 research on the Effect of User Control.
