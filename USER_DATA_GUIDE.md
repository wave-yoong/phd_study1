# 챗봇 사용자 데이터 확인 가이드

## 개요

챗봇의 모든 사용자 데이터는 SQLite 데이터베이스에 저장됩니다.
- **위치**: `/workspaces/phd_study1/database/chatbot.db`
- **저장 데이터**: 대화 내용, 메시지, 워크플로우 상태, 타임스탬프 등

## 데이터베이스 구조

### 1. conversations 테이블
- `id`: 대화 고유 ID
- `created_at`: 대화 시작 시간
- `updated_at`: 마지막 업데이트 시간
- `status`: 대화 상태 (active/completed 등)

### 2. messages 테이블
- `id`: 메시지 고유 ID
- `conversation_id`: 대화 ID (외래키)
- `role`: 역할 (user/assistant)
- `content`: 메시지 내용
- `created_at`: 메시지 생성 시간

### 3. workflow_state 테이블
- `id`: 워크플로우 상태 ID
- `conversation_id`: 대화 ID (외래키)
- `stage`: 워크플로우 단계 (source_planning, structure_proposal, final_answer 등)
- `user_input`: 사용자 입력
- `gpt_response`: GPT 응답
- `user_approval`: 사용자 승인 여부
- `created_at`: 생성 시간

---

## 사용자 데이터 확인 방법

### 방법 1: Python 스크립트 사용 (권장) ⭐

`view_user_data.py` 스크립트를 사용하면 데이터를 쉽게 확인할 수 있습니다.

#### 대화형 모드 (메뉴 방식)
```bash
python view_user_data.py
```

메뉴에서 원하는 작업을 선택:
1. 전체 대화 목록 보기
2. 특정 대화 상세 보기
3. 통계 요약 보기
4. 데이터 CSV로 내보내기
5. 종료

#### 명령줄 모드 (빠른 확인)

**전체 대화 목록 보기**
```bash
python view_user_data.py list
```

**통계 요약 보기**
```bash
python view_user_data.py stats
```
- 총 대화 수
- 총 메시지 수
- 사용자/AI 메시지 비율
- 대화당 평균 메시지 수
- 워크플로우 단계별 분포

**특정 대화 상세 보기**
```bash
python view_user_data.py view <대화ID>
```
예: `python view_user_data.py view 37`

**CSV로 내보내기**
```bash
# 특정 대화만
python view_user_data.py export <대화ID>

# 모든 대화
python view_user_data.py export
```

---

### 방법 2: SQLite 직접 쿼리

데이터베이스를 직접 쿼리할 수도 있습니다.

#### SQLite CLI 사용
```bash
# 데이터베이스 열기
sqlite3 database/chatbot.db

# 테이블 목록 보기
.tables

# 스키마 확인
.schema

# 전체 대화 목록
SELECT * FROM conversations ORDER BY updated_at DESC;

# 특정 대화의 메시지
SELECT role, content, created_at 
FROM messages 
WHERE conversation_id = 37 
ORDER BY created_at;

# 워크플로우 진행 상황
SELECT stage, user_approval, created_at 
FROM workflow_state 
WHERE conversation_id = 37 
ORDER BY created_at;

# 종료
.quit
```

#### Python에서 직접 쿼리
```python
import sqlite3

conn = sqlite3.connect('database/chatbot.db')
cursor = conn.cursor()

# 최근 10개 대화
cursor.execute('''
    SELECT id, created_at, updated_at 
    FROM conversations 
    ORDER BY updated_at DESC 
    LIMIT 10
''')
for row in cursor.fetchall():
    print(row)

conn.close()
```

---

### 방법 3: DB 관리 도구 사용

VS Code 확장 프로그램을 사용하여 GUI로 확인:

1. **SQLite Viewer** 확장 설치
   - VS Code에서 `Ctrl+Shift+X`
   - "SQLite Viewer" 검색 후 설치

2. **사용법**
   - `database/chatbot.db` 파일 클릭
   - 테이블 선택하여 데이터 열람
   - 쿼리 실행 가능

---

## 유용한 쿼리 예제

### 1. 가장 활발한 대화 찾기
```sql
SELECT 
    c.id,
    c.created_at,
    COUNT(m.id) as message_count
FROM conversations c
LEFT JOIN messages m ON c.id = m.conversation_id
GROUP BY c.id
ORDER BY message_count DESC
LIMIT 10;
```

### 2. 시간대별 사용 패턴
```sql
SELECT 
    strftime('%H', created_at) as hour,
    COUNT(*) as message_count
FROM messages
GROUP BY hour
ORDER BY hour;
```

### 3. 평균 대화 시간
```sql
SELECT 
    AVG(julianday(updated_at) - julianday(created_at)) * 24 * 60 as avg_minutes
FROM conversations
WHERE updated_at != created_at;
```

### 4. 워크플로우 완료율
```sql
SELECT 
    stage,
    COUNT(*) as total,
    SUM(CASE WHEN user_approval IN ('yes', 'selection') THEN 1 ELSE 0 END) as approved,
    ROUND(SUM(CASE WHEN user_approval IN ('yes', 'selection') THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as approval_rate
FROM workflow_state
GROUP BY stage;
```

### 5. 사용자 질문 키워드 분석
```sql
SELECT 
    content,
    created_at
FROM messages
WHERE role = 'user'
ORDER BY created_at DESC
LIMIT 20;
```

---

## 데이터 백업

### 전체 데이터베이스 백업
```bash
# 백업 생성
cp database/chatbot.db database/chatbot_backup_$(date +%Y%m%d_%H%M%S).db

# 또는 SQLite dump 사용
sqlite3 database/chatbot.db .dump > backup.sql
```

### 데이터 복원
```bash
# .db 파일에서 복원
cp database/chatbot_backup_20260206_013000.db database/chatbot.db

# .sql 파일에서 복원
sqlite3 database/chatbot.db < backup.sql
```

---

## 데이터 정리

### 오래된 대화 삭제
```python
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('database/chatbot.db')
cursor = conn.cursor()

# 30일 이상 오래된 대화 삭제
thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()

cursor.execute('DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE updated_at < ?)', (thirty_days_ago,))
cursor.execute('DELETE FROM workflow_state WHERE conversation_id IN (SELECT id FROM conversations WHERE updated_at < ?)', (thirty_days_ago,))
cursor.execute('DELETE FROM conversations WHERE updated_at < ?', (thirty_days_ago,))

conn.commit()
conn.close()
```

---

## 데이터 프라이버시 및 보안

### 주의사항
1. **개인정보 보호**: 사용자 입력에 민감한 정보가 포함될 수 있음
2. **접근 제한**: 데이터베이스 파일 권한 관리 필요
3. **정기 백업**: 데이터 손실 방지
4. **GDPR 준수**: 필요시 사용자 데이터 삭제 기능 구현

### 데이터베이스 암호화 (선택사항)
SQLite 암호화를 위해 SQLCipher 사용 고려

---

## 문제 해결

### 데이터베이스 잠김 오류
```bash
# 데이터베이스 무결성 검사
sqlite3 database/chatbot.db "PRAGMA integrity_check;"

# 잠금 해제
fuser -k database/chatbot.db
```

### 손상된 데이터베이스 복구
```bash
# 덤프 및 재생성
sqlite3 database/chatbot.db .dump > temp_dump.sql
mv database/chatbot.db database/chatbot_corrupted.db
sqlite3 database/chatbot_new.db < temp_dump.sql
mv database/chatbot_new.db database/chatbot.db
```

---

## 추가 리소스

- [SQLite 공식 문서](https://www.sqlite.org/docs.html)
- [DB Manager 소스 코드](database/db_manager.py)
- [View User Data 스크립트](view_user_data.py)

---

## 요약

**가장 쉬운 방법**: `python view_user_data.py` 실행 후 대화형 메뉴 사용

**빠른 확인**: 
- `python view_user_data.py stats` - 통계
- `python view_user_data.py list` - 대화 목록
- `python view_user_data.py view <ID>` - 상세 내용

**데이터 내보내기**: `python view_user_data.py export` - CSV 파일 생성
