"""
Mock travel service (demo mode, no API key). Mirrors TravelGPTService's methods
so the travel study runs end-to-end without an LLM. The intake is a lightweight
rule-based approximation (extracts fields from user text); the itinerary is a
style-based template. Real conversational quality requires the LLM service.
"""

import re
from typing import List, Dict, Any


COMPANION_MAP = [
    (re.compile(r'연인|여자친구|남자친구|여친|남친|커플|애인'), '연인'),
    (re.compile(r'가족|부모|엄마|아빠|아이|아기|자녀|딸|아들'), '가족'),
    (re.compile(r'배우자|아내|와이프|남편|부부'), '배우자'),
    (re.compile(r'친구|동료|지인'), '친구'),
    (re.compile(r'혼자|나홀로|혼행'), '혼자'),
]
STYLE_MAP = [
    (re.compile(r'휴양|휴식|힐링|여유|느긋|쉬'), ('여유로운 휴양', 'relax')),
    (re.compile(r'맛집|미식|먹|음식|식도락'), ('맛집 탐방', 'food')),
    (re.compile(r'액티비티|활동|체험|모험|스포츠|레포츠'), ('액티비티 중심', 'active')),
    (re.compile(r'관광|명소|구경|투어|랜드마크|볼거리'), ('알찬 관광', 'tour')),
    (re.compile(r'쇼핑'), ('쇼핑 중심', 'shopping')),
]
STYLE_POOLS = {
    'relax': ['해변·리조트에서 휴식', '스파·마사지로 재충전', '전망 좋은 카페에서 여유', '노을 감상 산책'],
    'food': ['로컬 맛집 투어', '전통시장 먹거리 탐방', '유명 디저트 카페', '현지 미식 코스'],
    'active': ['체험 액티비티(트레킹·자전거 등)', '테마파크·투어 프로그램', '자연 속 야외 활동', '인기 체험 프로그램'],
    'tour': ['대표 랜드마크 관광', '전망대·박물관 방문', '시내 도보 투어', '인기 명소 탐방'],
    'shopping': ['대형 쇼핑몰·아웃렛', '로컬 편집숍·시장', '기념품 쇼핑', '카페 거리 산책'],
    'balanced': ['대표 명소 관광', '인근 산책·카페', '로컬 체험 한 가지', '여유로운 자유 시간'],
}


class TravelMockService:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or "mock-api-key"
        self.model = "travel-agent (mock)"

    # ------------------------------------------------------------------ #
    def _extract(self, text: str) -> Dict[str, str]:
        got = {}
        m = re.search(r'(\d+)\s*박\s*(\d+)\s*일', text)
        if m:
            got['period'] = f"{m.group(1)}박 {m.group(2)}일"
        else:
            b = re.search(r'(\d+)\s*박', text)
            d = re.search(r'(\d+)\s*일', text)
            if b:
                got['period'] = f"{b.group(1)}박 {int(b.group(1))+1}일"
            elif d:
                n = int(d.group(1))
                got['period'] = (f"{n-1}박 " if n > 1 else "") + f"{n}일"
        for rx, label in COMPANION_MAP:
            if rx.search(text):
                got['companion'] = label
                break
        for rx, (label, _key) in STYLE_MAP:
            if rx.search(text):
                got['style'] = label
                break
        return got

    def _collect(self, history: List[Dict[str, str]]) -> Dict[str, str]:
        trip = {}
        user_texts = [m['content'] for m in history if m['role'] == 'user']
        for t in user_texts:
            for k, v in self._extract(t).items():
                trip.setdefault(k, v)
        # Destination: naive — first user message's leading token minus known words.
        if user_texts:
            for t in user_texts:
                cand = self._dest_candidate(t)
                if cand:
                    trip.setdefault('dest', cand)
                    break
        return trip

    def _dest_candidate(self, s: str):
        t = re.sub(r'(\d+)\s*박\s*(\d+)?\s*일?|(\d+)\s*일|당일', ' ', s)
        for rx, _ in COMPANION_MAP:
            t = rx.sub(' ', t)
        for rx, _ in STYLE_MAP:
            t = rx.sub(' ', t)
        t = re.sub(r'여행|일정|계획|짜|줘|주세요|도와|해줘|가고|가려|가자|싶어|싶|으로|로|에서|에|랑|이랑|과|와|하고|중심|위주|정도|같이|함께|예요|이에요|이야|추천|해|을|를|은|는|이|가|의|[?!.,]', ' ', t)
        toks = [x for x in t.split() if len(x) >= 2]
        return toks[0] if len(toks) == 1 else None

    def intake_turn(self, conversation_history: List[Dict[str, str]], user_message: str) -> Dict[str, Any]:
        trip = self._collect(conversation_history)
        user_turns = sum(1 for m in conversation_history if m['role'] == 'user')
        needed = [k for k in ('dest', 'period', 'companion', 'style') if not trip.get(k)]

        # Defer handling: if user says "아무거나" fill remaining with defaults.
        if re.search(r'아무|모르|알아서|추천|상관없|맡길', user_message) and needed:
            defaults = {'dest': '제주', 'period': '2박 3일', 'companion': '친구', 'style': '알찬 관광'}
            for k in needed:
                trip[k] = defaults[k]
            needed = []

        if not needed or user_turns >= 4:
            for k, dv in {'dest': '제주', 'period': '2박 3일', 'companion': '친구', 'style': '알찬 관광'}.items():
                trip.setdefault(k, dv)
            comp = trip['companion']
            josa = '과' if (ord(comp[-1]) - 0xAC00) % 28 else '와'
            summary = f"정리하면 {trip['dest']} {trip['period']}, {comp}{josa} 함께 '{trip['style']}' 분위기의 여행이네요. 이 정보로 준비할게요."
            return {"text": summary, "ready": True, "trip": trip}

        # Ask for the first missing field.
        q = {
            'dest': "어디로 여행을 떠나시나요? 도시나 지역을 알려주세요.",
            'period': "여행 기간은 어떻게 되나요? (예: 2박 3일)",
            'companion': "누구와 함께 가시나요? (혼자 / 친구 / 연인 / 가족 등)",
            'style': "어떤 분위기의 여행을 원하세요? (휴양 / 관광 / 맛집 / 액티비티 등)",
        }[needed[0]]
        ack = ""
        just = self._extract(user_message)
        if just.get('dest') or self._dest_candidate(user_message):
            pass
        greet = "여행 계획을 도와드릴게요! " if user_turns <= 1 else ""
        return {"text": greet + ack + q, "ready": False, "trip": None}

    def extract_trip(self, conversation_history: List[Dict[str, str]]) -> Dict[str, str]:
        trip = self._collect(conversation_history)
        for k, dv in {'dest': '제주', 'period': '2박 3일', 'companion': '친구', 'style': '알찬 관광'}.items():
            trip.setdefault(k, dv)
        return trip

    def make_itinerary(self, trip: Dict[str, str]) -> str:
        dest = trip.get('dest') or '여행지'
        period = trip.get('period') or '2박 3일'
        style_label = trip.get('style') or '알찬 관광'
        key = 'balanced'
        for rx, (label, k) in STYLE_MAP:
            if rx.search(style_label):
                key = k if k in STYLE_POOLS else 'balanced'
                break
        pool = STYLE_POOLS.get(key, STYLE_POOLS['balanced'])

        m = re.search(r'(\d+)\s*일', period)
        b = re.search(r'(\d+)\s*박', period)
        days = int(m.group(1)) if m else (int(b.group(1)) + 1 if b else 3)
        days = max(1, min(days, 7))

        lines = [f"{dest} {period} 여행 일정표", ""]
        for d in range(1, days + 1):
            lines.append(f"Day {d}")
            if d == 1:
                lines += [f"- 오전: {dest} 도착, 숙소 체크인 후 인근 명소 산책",
                          f"- 점심: {dest} 현지 맛집에서 식사",
                          f"- 오후: {pool[0]}",
                          f"- 저녁: {dest} 야경 감상 또는 로컬 저녁 식사"]
            elif d == days:
                lines += ["- 오전: 여유로운 아침, 카페·기념품 쇼핑",
                          "- 점심: 마지막 현지 식사",
                          f"- 오후: {dest} 출발 및 귀가"]
            else:
                lines += [f"- 오전: {pool[d % len(pool)]}",
                          "- 점심: 로컬 맛집에서 식사",
                          f"- 오후: {pool[(d + 1) % len(pool)]}",
                          f"- 저녁: {pool[(d + 2) % len(pool)]} 후 저녁 식사"]
            lines.append("")
        lines.append("실제 영업시간·요금·예약은 방문 전 확인이 필요합니다.")
        return "\n".join(lines)
