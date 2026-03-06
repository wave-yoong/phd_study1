# phd_study1
Effect of User Control

## Flask 3-Stage Chatbot

This repository contains a Flask-based chatbot application with a 3-stage confirmation workflow for studying the effect of user control in AI interactions.

### Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run in demo mode (no API key needed):**
   ```bash
   ./run.sh demo
   ```

3. **Or run with OpenAI API:**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY
   ./run.sh
   ```

4. **Open your browser to:** `http://localhost:5000`

### Features

- **3-Stage Workflow:** Source Check → Content Structure → Final Approval
- **User Control:** Approve or reject at each stage
- **Conversation History:** All interactions saved to SQLite database
- **Demo Mode:** Test without OpenAI API key

See [CHATBOT_README.md](CHATBOT_README.md) for detailed documentation.
