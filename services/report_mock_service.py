"""
Placeholder service for the stock-report study (PhD Study 1, V2 — execution-version
control).

The report deliverable is intentionally FIXED (see StockReportWorkflowManager),
so no language model is involved and this service is never actually called to
generate content. It exists only so the app's service-building flow and the
/health endpoint have a consistent object with a model name.
"""

from typing import List, Dict, Optional


class ReportMockService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or "mock-api-key"
        self.model = "stock-report-agent (fixed content)"

    def generate_response(self, messages: List[Dict[str, str]], temperature: float = 0.7,
                          max_tokens: int = 900) -> str:
        return "[MOCK] 고정 콘텐츠 스터디입니다."

    def generate_agent_response(self, condition: str, phase: str, user_message: str,
                                conversation_history: List[Dict[str, str]],
                                autonomy_level: str = 'low',
                                override_instruction: Optional[str] = None) -> str:
        # Not used: the workflow supplies all text as fixed strings.
        return "[MOCK] 고정 콘텐츠 스터디입니다."
