import os
import random
from flask import Flask, request, jsonify, render_template, session
from dotenv import load_dotenv
from database.db_manager import DBManager
from services.hiring_workflow_manager import CANDIDATES as HIRING_CANDIDATES

# Load environment variables
load_dotenv()

app = Flask(__name__,
            template_folder='../frontend',
            static_folder='../frontend')
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# ---------------------------------------------------------------------------
# Which study/agent version to serve. Versions of the user-control agent live
# in this repo:
#   - 'stock' (V2, default): stock-report agent with EXECUTION-VERSION control.
#     The agent offers 2-3 versions (length / model / time trade-offs) and the
#     user picks which to run; the final report is identical regardless.
#     Conditions: 'version' vs 'auto'.
#   - 'hiring' (V1): hiring-decision agent with DECISIONAL control
#     ("deciding WHAT to do"), selectable option cards. Conditions: 'decision' vs 'auto'.
#   - 'finance': earlier V1 draft (finance allocation), also decisional control.
#   - 'diet'   : the earlier diet/exercise agent with PROCESS control.
#     Conditions: 'control' vs 'auto'.
# Select with the STUDY env var.
# ---------------------------------------------------------------------------
DEFAULT_STUDY = os.getenv('STUDY', 'stock').strip().lower() or 'stock'

STUDY_CONFIG = {
    'stock': {
        'title': 'AI 증시 분석 보고서 에이전트',
        'control_condition': 'version',
        'scenario': (
            "당신은 투자 참고용으로 최신 증시 분석 보고서가 필요합니다. AI 에이전트가 "
            "'2026년 1분기 국내·해외 증시 현황' 보고서를 대신 작성해 줍니다. "
            "에이전트와 대화하며 보고서를 받아 보세요."
        ),
        'placeholder': '예: 2026년 1분기 국내·해외 증시 현황 보고서 작성해줘',
        'starter': '2026년 1분기 국내·해외 증시 현황 보고서를 작성해줘',
        'suggestions': [
            '2026년 1분기 국내·해외 증시 현황 보고서를 작성해줘',
        ],
    },
    'hiring': {
        'title': 'AI 채용 결정 에이전트',
        'control_condition': 'decision',
        'scenario': (
            "당신은 한 IT 회사의 채용 담당자입니다. 마케팅팀 신입 1명을 뽑는데, 아래 5명이 최종 검토 "
            "대상으로 올라왔습니다. AI 채용 에이전트가 지원자들의 서류·실무 과제·면접 기록을 분석해 "
            "정리해 줍니다. 에이전트와 대화하며 최종 합격자를 결정해 주세요."
        ),
        'placeholder': '예: 지원자들 분석해줘 / 어떤 기준으로 뽑아야 할까?',
        'starter': '마케팅팀 신입을 뽑으려고 해요. 지원자들 분석해줘',
        'candidates': HIRING_CANDIDATES,
        'suggestions': [
            '지원자 5명을 강점·약점 중심으로 비교해줘',
            '어떤 기준으로 뽑아야 할지부터 알려줘',
            '실무에 바로 투입할 사람이 필요해. 누가 맞을까?',
            '성장 잠재력을 가장 중요하게 보고 싶어',
        ],
    },
    'finance': {
        'title': 'AI 재무 배분 에이전트',
        'control_condition': 'decision',
        'scenario': (
            "당신은 매달 일정한 여윳돈이 생깁니다. AI 재무 에이전트가 당신의 재무 상황을 "
            "분석해, 이 여윳돈을 부채 상환·비상금·투자에 어떻게 배분할지 함께 계획합니다. "
            "에이전트와 대화하며 앞으로의 자산 배분 계획을 세워 주세요."
        ),
        'placeholder': '예: 매달 남는 여윳돈을 어떻게 배분할지 계획하고 싶어요',
        'starter': '매달 남는 여윳돈을 어떻게 배분할지 계획하고 싶어요',
    },
    'diet': {
        'title': 'AI 다이어트 플래너 에이전트',
        'control_condition': 'control',
        'scenario': (
            "당신은 2주 뒤 5kg 감량을 목표로 다이어트를 하고 있습니다. "
            "당신의 AI 에이전트는 목표 체중을 위해 운동과 식단 계획을 대신 짜줍니다. "
            "AI 에이전트와 대화하면서 2주의 식단과 운동 및 일상을 계획해 주세요."
        ),
        'placeholder': '예: 2주 뒤 5kg 감량 목표예요. 식단과 운동 계획 짜줘',
        'starter': '2주 뒤 5kg 감량 목표예요. 식단과 운동 계획 짜줘',
    },
}

# Initialize services
db_manager = DBManager(os.getenv('DATABASE_PATH', 'database/chatbot.db'))


def _build_gpt_service(study: str):
    """Use the real LLM if configured, otherwise fall back to the mock agent.

    Set USE_MOCK_GPT=1 to force demo mode regardless of credentials.
    """
    force_mock = os.getenv('USE_MOCK_GPT', '').strip() in ('1', 'true', 'True')

    def _load(path):
        module_name, class_name = path.split(':')
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)

    # The stock study uses fixed content (no LLM) — always the placeholder service.
    if study == 'stock':
        return _load('services.report_mock_service:ReportMockService')()

    if study == 'diet':
        real_import = 'services.gpt_service:GPTService'
        mock_import = 'services.mock_gpt_service:MockGPTService'
    elif study == 'finance':
        real_import = 'services.finance_gpt_service:FinanceGPTService'
        mock_import = 'services.finance_mock_service:FinanceMockService'
    else:
        real_import = 'services.hiring_gpt_service:HiringGPTService'
        mock_import = 'services.hiring_mock_service:HiringMockService'

    if force_mock:
        return _load(mock_import)()

    try:
        real_cls = _load(real_import)
        if os.getenv('AZURE_OPENAI_ENDPOINT'):
            return real_cls(use_azure=True)
        if os.getenv('OPENAI_API_KEY'):
            return real_cls(use_azure=False)
    except Exception as e:  # pragma: no cover - configuration fallback
        print(f"Falling back to mock service: {e}")

    return _load(mock_import)()


def _build_workflow(study: str, service):
    if study == 'diet':
        from services.workflow_manager import WorkflowManager
        return WorkflowManager(service, db_manager)
    if study == 'finance':
        from services.finance_workflow_manager import FinanceWorkflowManager
        return FinanceWorkflowManager(service, db_manager)
    if study == 'stock':
        from services.report_workflow_manager import StockReportWorkflowManager
        return StockReportWorkflowManager(service, db_manager)
    from services.hiring_workflow_manager import HiringWorkflowManager
    return HiringWorkflowManager(service, db_manager)


gpt_service = _build_gpt_service(DEFAULT_STUDY)
workflow_manager = _build_workflow(DEFAULT_STUDY, gpt_service)


# Experimental condition labels.
CONDITION_AUTO = 'auto'         # autonomous agent / no-control group


def _control_condition() -> str:
    """The 'user-control' condition label for the active study."""
    return STUDY_CONFIG.get(DEFAULT_STUDY, STUDY_CONFIG['finance'])['control_condition']


def _normalize_condition(raw: str) -> str:
    """Map incoming group labels to a canonical condition, or '' if unspecified."""
    value = (raw or '').strip().lower()
    if value in ('control', 'decision', 'version', 'user_control', 'user-control', 'uc', 'high', '1'):
        return _control_condition()
    if value in ('auto', 'autonomous', 'no_control', 'no-control', 'nc', 'low', '0'):
        return CONDITION_AUTO
    return ''


def _assign_condition(requested: str) -> str:
    """Use the requested condition if valid, otherwise random assignment."""
    normalized = _normalize_condition(requested)
    if normalized:
        return normalized
    return random.choice([_control_condition(), CONDITION_AUTO])


def _build_choices(result: dict) -> list:
    """Build clickable control affordances (diet study / process control).

    The finance study supplies its own decision options in result['choices'];
    this helper only runs when the workflow did not provide any.
    """
    if result.get('condition') != 'control':
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
    # Prefer choices supplied by the workflow (finance decision options);
    # otherwise fall back to the diet study's process-control levers.
    choices = result['choices'] if 'choices' in result else _build_choices(result)
    payload = {
        'response': result['response'],
        'stage': result.get('stage'),
        'stage_description': result.get('stage_description'),
        'condition': result.get('condition'),
        'autonomy_level': result.get('autonomy_level'),
        'agent_actions': result.get('agent_actions', []),
        'awaiting_input': result.get('awaiting_input', True),
        'choices': choices,
        'decision_mode': result.get('decision_mode'),
    }
    payload.update(extra)
    return payload


@app.route('/')
def index():
    """Serve the main agent interface for the active study."""
    cfg = STUDY_CONFIG.get(DEFAULT_STUDY, STUDY_CONFIG['finance'])
    return render_template('index.html', study=DEFAULT_STUDY, cfg=cfg)


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
