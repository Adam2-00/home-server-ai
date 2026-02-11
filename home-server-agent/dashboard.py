#!/usr/bin/env python3
"""
Status Dashboard for Home Server Setup Agent
View session status and logs.
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path


def show_dashboard(db_path: str = "state.db"):
    """Show status dashboard."""
    path = Path(db_path)
    
    if not path.exists():
        print("No state database found. Run setup first.")
        return
    
    # Check if file is readable and is a valid SQLite DB
    try:
        with open(path, 'rb') as f:
            header = f.read(16)
            if not header.startswith(b'SQLite format 3'):
                print(f"⚠️  {db_path} is not a valid SQLite database.")
                return
    except (IOError, PermissionError) as e:
        print(f"❌ Cannot read {db_path}: {e}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verify tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        if 'sessions' not in tables:
            print("⚠️  Database exists but has no sessions table.")
            conn.close()
            return
        
        # Get all sessions
        cursor.execute('''
            SELECT session_id, status, current_step, created_at, updated_at 
            FROM sessions 
            ORDER BY updated_at DESC
        ''')
        sessions = cursor.fetchall()
        
        if not sessions:
            print("No sessions found. Run setup to create one.")
            conn.close()
            return
        
        print("\n" + "="*70)
        print("  📊 Home Server Setup - Session Dashboard")
        print("="*70)
        print()
        
        for session in sessions:
            session_id, status, current_step, created_at, updated_at = session
            
            # Get step count
            cursor.execute('''
                SELECT COUNT(DISTINCT step_number) FROM execution_state 
                WHERE session_id = ? AND status = 'completed'
            ''', (session_id,))
            completed = cursor.fetchone()[0]
            
            # Status emoji
            status_emoji = {
                'completed': '✅',
                'failed': '❌',
                'in_progress': '⏳'
            }.get(status, '❓')
            
            print(f"{status_emoji} Session: {session_id}")
            print(f"   Status: {status}")
            print(f"   Steps completed: {completed}")
            print(f"   Created: {created_at}")
            print(f"   Last updated: {updated_at}")
            print()
        
        print("To resume a session:")
        print("  python main.py --resume <session_id>")
        print()
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def show_session_details(session_id: str, db_path: str = "state.db"):
    """Show detailed information about a specific session."""
    import sys
    path = Path(db_path)
    
    if not path.exists():
        print(f"❌ No state database found.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get session info
        cursor.execute('''
            SELECT * FROM sessions WHERE session_id = ?
        ''', (session_id,))
        session = cursor.fetchone()
        
        if not session:
            print(f"❌ Session {session_id} not found.")
            print(f"   Run 'python dashboard.py' to see available sessions.")
            conn.close()
            return
        
        # Parse session data safely
        def safe_json_loads(data, default=None):
            if not data:
                return default or {}
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return default or {}
        
        hardware = safe_json_loads(session[2] if len(session) > 2 else None)
        requirements = safe_json_loads(session[3] if len(session) > 3 else None)
        plan = safe_json_loads(session[4] if len(session) > 4 else None)
        
        print("\n" + "="*70)
        print(f"  📋 Session Details: {session_id}")
        print("="*70)
        
        print("\n📊 Hardware Profile:")
        print(f"   CPU: {hardware.get('cpu_model', 'Unknown')} ({hardware.get('cpu_cores', '?')} cores)")
        print(f"   RAM: {hardware.get('ram_gb', '?')} GB")
        print(f"   OS: {hardware.get('distro', 'Unknown')} {hardware.get('distro_version', '')}")
        
        print("\n📝 Requirements:")
        print(f"   Use cases: {', '.join(requirements.get('use_cases', []))}")
        print(f"   Components: {', '.join(k for k, v in requirements.items() if v and k.startswith('want_'))}")
        
        print("\n📋 Plan:")
        print(f"   Title: {plan.get('title', 'Unknown')}")
        print(f"   Steps: {len(plan.get('steps', []))}")
        print(f"   Est. time: {plan.get('estimated_time_minutes', '?')} minutes")
        
        # Get execution details
        cursor.execute('''
            SELECT step_number, step_name, status, timestamp 
            FROM execution_state 
            WHERE session_id = ? 
            ORDER BY step_number
        ''', (session_id,))
        steps = cursor.fetchall()
        
        if steps:
            print("\n🔍 Execution Log:")
            for step in steps:
                step_num, step_name, status, timestamp = step
                status_emoji = {'completed': '✅', 'failed': '❌'}.get(status, '⏳')
                print(f"   {status_emoji} Step {step_num}: {step_name} ({status})")
        
        print()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        show_session_details(sys.argv[1])
    else:
        show_dashboard()
