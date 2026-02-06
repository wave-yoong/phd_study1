#!/usr/bin/env python3
"""
View user data from the chatbot database.
Shows conversations, messages, and workflow states.
"""

import sqlite3
import sys
from datetime import datetime
from tabulate import tabulate


DB_PATH = "database/chatbot.db"


def get_connection():
    """Get database connection."""
    return sqlite3.connect(DB_PATH)


def show_all_conversations():
    """Show all conversations with summary."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            c.id,
            c.created_at,
            c.updated_at,
            c.status,
            COUNT(DISTINCT m.id) as message_count,
            COUNT(DISTINCT w.id) as workflow_count
        FROM conversations c
        LEFT JOIN messages m ON c.id = m.conversation_id
        LEFT JOIN workflow_state w ON c.id = w.conversation_id
        GROUP BY c.id
        ORDER BY c.updated_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("\n📭 아직 대화 기록이 없습니다.\n")
        return
    
    headers = ["ID", "시작 시간", "마지막 업데이트", "상태", "메시지 수", "워크플로우 수"]
    print("\n" + "="*100)
    print("📊 전체 대화 목록")
    print("="*100)
    print(tabulate(rows, headers=headers, tablefmt="grid"))
    print(f"\n총 {len(rows)}개의 대화\n")


def show_conversation_detail(conversation_id):
    """Show detailed information for a specific conversation."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get conversation info
    cursor.execute('SELECT * FROM conversations WHERE id = ?', (conversation_id,))
    conv = cursor.fetchone()
    
    if not conv:
        print(f"\n❌ 대화 ID {conversation_id}를 찾을 수 없습니다.\n")
        conn.close()
        return
    
    print("\n" + "="*100)
    print(f"💬 대화 #{conversation_id} 상세 정보")
    print("="*100)
    print(f"생성 시간: {conv[1]}")
    print(f"업데이트: {conv[2]}")
    print(f"상태: {conv[3]}")
    
    # Get messages
    print("\n" + "-"*100)
    print("📝 메시지 기록")
    print("-"*100)
    
    cursor.execute('''
        SELECT id, role, content, created_at 
        FROM messages 
        WHERE conversation_id = ? 
        ORDER BY created_at ASC
    ''', (conversation_id,))
    
    messages = cursor.fetchall()
    if messages:
        for msg in messages:
            role_icon = "👤" if msg[1] == "user" else "🤖"
            print(f"\n{role_icon} [{msg[1].upper()}] - {msg[3]}")
            print(f"   {msg[2][:200]}{'...' if len(msg[2]) > 200 else ''}")
    else:
        print("메시지 없음")
    
    # Get workflow states
    print("\n" + "-"*100)
    print("🔄 워크플로우 상태")
    print("-"*100)
    
    cursor.execute('''
        SELECT id, stage, user_approval, created_at 
        FROM workflow_state 
        WHERE conversation_id = ? 
        ORDER BY created_at ASC
    ''', (conversation_id,))
    
    workflows = cursor.fetchall()
    if workflows:
        headers = ["ID", "단계", "승인", "시간"]
        print(tabulate(workflows, headers=headers, tablefmt="grid"))
    else:
        print("워크플로우 기록 없음")
    
    conn.close()
    print("\n")


def show_statistics():
    """Show overall statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total conversations
    cursor.execute('SELECT COUNT(*) FROM conversations')
    total_convs = cursor.fetchone()[0]
    
    # Total messages
    cursor.execute('SELECT COUNT(*) FROM messages')
    total_msgs = cursor.fetchone()[0]
    
    # User vs Assistant messages
    cursor.execute('SELECT role, COUNT(*) FROM messages GROUP BY role')
    role_counts = dict(cursor.fetchall())
    
    # Average messages per conversation
    cursor.execute('''
        SELECT AVG(msg_count) FROM (
            SELECT COUNT(*) as msg_count 
            FROM messages 
            GROUP BY conversation_id
        )
    ''')
    avg_msgs = cursor.fetchone()[0] or 0
    
    # Most recent activity
    cursor.execute('SELECT MAX(updated_at) FROM conversations')
    last_activity = cursor.fetchone()[0]
    
    # Stage distribution
    cursor.execute('SELECT stage, COUNT(*) FROM workflow_state GROUP BY stage')
    stage_counts = cursor.fetchall()
    
    conn.close()
    
    print("\n" + "="*100)
    print("📈 통계 요약")
    print("="*100)
    print(f"총 대화 수: {total_convs}")
    print(f"총 메시지 수: {total_msgs}")
    print(f"  - 사용자 메시지: {role_counts.get('user', 0)}")
    print(f"  - AI 응답: {role_counts.get('assistant', 0)}")
    print(f"대화당 평균 메시지: {avg_msgs:.1f}")
    print(f"마지막 활동: {last_activity or 'N/A'}")
    
    if stage_counts:
        print("\n워크플로우 단계별 분포:")
        for stage, count in stage_counts:
            print(f"  - {stage}: {count}")
    
    print("\n")


def export_to_csv(conversation_id=None):
    """Export data to CSV."""
    import csv
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    if conversation_id:
        filename = f"conversation_{conversation_id}_{timestamp}.csv"
        cursor.execute('''
            SELECT m.id, m.conversation_id, m.role, m.content, m.created_at
            FROM messages m
            WHERE m.conversation_id = ?
            ORDER BY m.created_at ASC
        ''', (conversation_id,))
    else:
        filename = f"all_conversations_{timestamp}.csv"
        cursor.execute('''
            SELECT m.id, m.conversation_id, m.role, m.content, m.created_at
            FROM messages m
            ORDER BY m.conversation_id, m.created_at ASC
        ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print(f"\n❌내보낼 데이터가 없습니다.\n")
        return
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', '대화ID', '역할', '내용', '시간'])
        writer.writerows(rows)
    
    print(f"\n✅ 데이터를 {filename}로 내보냈습니다. ({len(rows)}개 메시지)\n")


def interactive_menu():
    """Interactive menu for viewing data."""
    while True:
        print("\n" + "="*100)
        print("🔍 챗봇 사용자 데이터 뷰어")
        print("="*100)
        print("1. 전체 대화 목록 보기")
        print("2. 특정 대화 상세 보기")
        print("3. 통계 요약 보기")
        print("4. 데이터 CSV로 내보내기")
        print("5. 종료")
        print("-"*100)
        
        choice = input("선택하세요 (1-5): ").strip()
        
        if choice == '1':
            show_all_conversations()
        
        elif choice == '2':
            show_all_conversations()
            try:
                conv_id = int(input("\n대화 ID를 입력하세요: ").strip())
                show_conversation_detail(conv_id)
            except ValueError:
                print("\n❌ 올바른 숫자를 입력하세요.\n")
        
        elif choice == '3':
            show_statistics()
        
        elif choice == '4':
            print("\n1. 특정 대화만 내보내기")
            print("2. 모든 대화 내보내기")
            export_choice = input("선택하세요 (1-2): ").strip()
            
            if export_choice == '1':
                try:
                    conv_id = int(input("대화 ID를 입력하세요: ").strip())
                    export_to_csv(conv_id)
                except ValueError:
                    print("\n❌ 올바른 숫자를 입력하세요.\n")
            elif export_choice == '2':
                export_to_csv()
        
        elif choice == '5':
            print("\n👋 프로그램을 종료합니다.\n")
            break
        
        else:
            print("\n❌ 1-5 사이의 숫자를 입력하세요.\n")


def main():
    """Main function."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'list':
            show_all_conversations()
        
        elif command == 'stats':
            show_statistics()
        
        elif command == 'view' and len(sys.argv) > 2:
            try:
                conv_id = int(sys.argv[2])
                show_conversation_detail(conv_id)
            except ValueError:
                print("Usage: python view_user_data.py view <conversation_id>")
        
        elif command == 'export':
            conv_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
            export_to_csv(conv_id)
        
        else:
            print("Usage:")
            print("  python view_user_data.py              # Interactive mode")
            print("  python view_user_data.py list         # Show all conversations")
            print("  python view_user_data.py stats        # Show statistics")
            print("  python view_user_data.py view <id>    # Show conversation detail")
            print("  python view_user_data.py export [id]  # Export to CSV")
    
    else:
        # Interactive mode
        interactive_menu()


if __name__ == "__main__":
    main()
