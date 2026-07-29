import os
import re
import sys
import json
from openai import AzureOpenAI, OpenAI
from typing import List, Dict, Optional, Any


# ---------------------------------------------------------------------------
# Travel-planner agent (PhD Study 1, V2 — execution-version control, LLM-driven).
#
# Unlike the fixed-content stock study, the travel study uses a REAL LLM for a
# natural conversational intake and for generating the itinerary. The control
# manipulation is the same: after intake, the control group picks an execution
# version (length/model/time trade-offs); the itinerary itself is generated ONCE
# from the gathered trip info and reused for every version (output held constant
# per participant). See TravelWorkflowManager.
# ---------------------------------------------------------------------------

READY_MARKER = "<<READY>>"

INTAKE_SYSTEM = """당신은 사용자의 여행 일정을 대신 짜주는 친근한 AI 여행 플래너입니다.
지금은 일정을 만들기 전에, 대화로 자연스럽게 필요한 정보를 수집하는 단계입니다.

파악해야 할 4가지:
1) 여행지 (도시/지역)
2) 기간 (예: 2박 3일)
3) 동행 (누구와 가는지)
4) 여행 스타일/취향 (예: 휴양, 관광, 맛집, 액티비티 등 원하는 분위기나 꼭 하고 싶은 것)

대화 규칙:
- 사용자의 말에 짧게 반응하고, 아직 모르는 것만 물어보세요. 한 번에 1~2개만 질문하세요.
- 이미 말한 정보는 다시 묻지 마세요. 사용자가 한 문장에 여러 개를 말하면 모두 반영하세요.
- 따뜻하고 자연스러운 대화체로. 마크다운 서식(#, *, |, **)은 쓰지 마세요.
- 아직 일정표 자체는 만들지 마세요. 지금은 정보 수집만 합니다.

4가지가 모두 파악되면, 사용자에게 한두 문장으로 짧게 요약해 확인해 주고,
반드시 그 응답의 맨 마지막 줄에 아래 형식을 정확히 출력하세요(이 줄은 시스템 신호이며 사용자에게 그대로 보여도 무방합니다):
<<READY>>{"dest":"여행지","period":"기간","companion":"동행","style":"스타일"}
4가지 중 하나라도 부족하면 <<READY>>를 절대 출력하지 말고 계속 질문하세요."""

EXTRACT_SYSTEM = """다음 대화에서 여행 정보를 추출해 JSON으로만 출력하세요.
형식: {"dest":"","period":"","companion":"","style":""}
알 수 없는 값은 빈 문자열로 두세요. JSON 외의 다른 텍스트는 출력하지 마세요."""

ITINERARY_SYSTEM = """당신은 유능한 AI 여행 플래너입니다. 아래 여행 정보로 실제 일정표를 작성하세요.

여행 정보:
- 여행지: {dest}
- 기간: {period}
- 동행: {companion}
- 스타일/취향: {style}

작성 규칙:
- 기간에 맞춰 Day 1, Day 2 ... 순서로 각 날을 구성하세요.
- 각 날은 오전 / 점심 / 오후 / 저녁으로 나누고, 실제로 있을 법한 대표 명소·맛집·활동을 구체적으로 제안하세요.
- 동선 효율(가까운 곳끼리 묶기)과 동행·스타일을 반영하세요.
- 마크다운 서식(#, *, |, **)은 절대 쓰지 마세요. Day 제목과 하이픈(-) 목록만 사용하세요.
- 맨 마지막에 한 줄로 "실제 영업시간·요금·예약은 방문 전 확인이 필요합니다." 안내를 덧붙이세요."""


class TravelGPTService:
    """LLM-backed travel planner: conversational intake + itinerary generation."""

    def __init__(self, api_key: str = None, use_azure: bool = True):
        self.use_azure = use_azure
        if use_azure:
            self.api_key = api_key or os.getenv('AZURE_OPENAI_API_KEY')
            self.endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
            self.deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
            self.api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
            if not all([self.api_key, self.endpoint, self.deployment]):
                raise ValueError("Azure OpenAI configuration incomplete. Check AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT_NAME")
            try:
                self.client = AzureOpenAI(api_key=self.api_key, api_version=self.api_version, azure_endpoint=self.endpoint)
                self.model = self.deployment
            except Exception as e:
                print(f"Error initializing Azure OpenAI: {e}", file=sys.stderr)
                raise
        else:
            self.api_key = api_key or os.getenv('OPENAI_API_KEY')
            if not self.api_key:
                raise ValueError("OpenAI API key not provided")
            self.client = OpenAI(api_key=self.api_key)
            self.model = "gpt-4o-mini"

    def _chat(self, messages, temperature=0.7, max_tokens=900) -> str:
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        return resp.choices[0].message.content

    # ------------------------------------------------------------------ #
    def intake_turn(self, conversation_history: List[Dict[str, str]], user_message: str) -> Dict[str, Any]:
        """One conversational intake turn. Returns {text, ready, trip}."""
        messages = [{"role": "system", "content": INTAKE_SYSTEM}]
        for m in conversation_history[-13:]:
            messages.append({"role": m['role'], "content": m['content']})
        try:
            raw = self._chat(messages, temperature=0.6, max_tokens=500)
        except Exception as e:
            return {"text": f"(응답 생성 오류: {e})", "ready": False, "trip": None}
        return self._parse_ready(raw)

    def _parse_ready(self, raw: str) -> Dict[str, Any]:
        if READY_MARKER not in raw:
            return {"text": raw.strip(), "ready": False, "trip": None}
        idx = raw.index(READY_MARKER)
        text = raw[:idx].strip()
        tail = raw[idx + len(READY_MARKER):].strip()
        trip = None
        try:
            trip = json.loads(tail)
        except Exception:
            m = re.search(r'\{.*\}', tail, re.S)
            if m:
                try:
                    trip = json.loads(m.group(0))
                except Exception:
                    trip = None
        return {"text": text or "정리했습니다.", "ready": True, "trip": trip}

    def extract_trip(self, conversation_history: List[Dict[str, str]]) -> Dict[str, str]:
        convo = "\n".join(f"{m['role']}: {m['content']}" for m in conversation_history)
        messages = [{"role": "system", "content": EXTRACT_SYSTEM}, {"role": "user", "content": convo}]
        try:
            raw = self._chat(messages, temperature=0, max_tokens=200)
            m = re.search(r'\{.*\}', raw, re.S)
            return json.loads(m.group(0)) if m else {}
        except Exception:
            return {}

    def make_itinerary(self, trip: Dict[str, str]) -> str:
        sys_prompt = ITINERARY_SYSTEM.format(
            dest=trip.get('dest') or '여행지',
            period=trip.get('period') or '2박 3일',
            companion=trip.get('companion') or '',
            style=trip.get('style') or '균형 잡힌',
        )
        messages = [{"role": "system", "content": sys_prompt},
                    {"role": "user", "content": "위 정보로 일정표를 작성해 주세요."}]
        try:
            return self._chat(messages, temperature=0.7, max_tokens=1400)
        except Exception as e:
            return f"(일정 생성 오류: {e})"
