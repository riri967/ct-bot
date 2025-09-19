"""
Database Manager - Handles both SQLite (local) and Supabase (cloud) storage
"""

import sqlite3
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List, Any
import streamlit as st
from config import USE_SUPABASE, DATABASE_PATH, get_supabase_url, get_supabase_key

supabase_client = None
if USE_SUPABASE:
    try:
        from supabase import create_client, Client
        supabase_client = create_client(get_supabase_url(), get_supabase_key())
    except ImportError:
        st.error("Supabase not installed. Run: pip install supabase")

class DatabaseManager:
    """Unified database interface for SQLite and Supabase"""
    
    def __init__(self):
        self.use_supabase = USE_SUPABASE and supabase_client is not None
        if not self.use_supabase:
            self.init_sqlite()
    
    def init_sqlite(self):
        """Initialize SQLite database"""
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        # Create tables
        c.execute('''CREATE TABLE IF NOT EXISTS participants (
            id TEXT PRIMARY KEY,
            start_time TIMESTAMP,
            completion_time TIMESTAMP,
            status TEXT DEFAULT 'active'
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id TEXT,
            user_message TEXT,
            ai_response TEXT,
            timestamp TIMESTAMP,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS questionnaire_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id TEXT,
            age INTEGER,
            education TEXT,
            ct_experience TEXT,
            post_q1_easy_to_use INTEGER,
            post_q2_felt_confident INTEGER,
            post_q3_use_again INTEGER,
            post_q4_engaging INTEGER,
            post_q5_natural_flow INTEGER,
            post_q6_disengagement TEXT,
            post_q7_encouraged_reflection INTEGER,
            post_q8_multiple_perspectives INTEGER,
            post_q9_critical_thinking_ways TEXT,
            post_q10_learned_something TEXT,
            post_q11_design_support TEXT,
            post_q12_confusion TEXT,
            post_q13_application TEXT,
            post_q14_improvements TEXT,
            post_q15_valuable INTEGER,
            post_q16_recommend INTEGER,
            post_q17_other_comments TEXT,
            facione_critical_thinking_score REAL,
            completion_time TIMESTAMP,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS study_scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_id TEXT,
            scenario_text TEXT,
            initial_question TEXT,
            generation_timestamp TIMESTAMP,
            FOREIGN KEY (participant_id) REFERENCES participants (id)
        )''')
        
        conn.commit()
        conn.close()
    
    def _execute_db_operation(self, operation_name: str, supabase_op, sqlite_op) -> bool:
        """Helper method to execute database operations with error handling"""
        try:
            if self.use_supabase:
                result = supabase_op()
                return bool(result.data if hasattr(result, 'data') else result)
            else:
                sqlite_op()
                return True
        except Exception as e:
            st.error(f"Error {operation_name}: {e}")
            return False
    
    def add_participant(self, participant_id: str) -> bool:
        """Add new participant"""
        def supabase_op():
            return supabase_client.table('participants').insert({
                'id': participant_id, 'start_time': datetime.now().isoformat(), 'status': 'active'
            }).execute()
        
        def sqlite_op():
            conn = sqlite3.connect(DATABASE_PATH)
            c = conn.cursor()
            c.execute('''INSERT INTO participants (id, start_time, status) VALUES (?, ?, ?)''',
                     (participant_id, datetime.now(), 'active'))
            conn.commit()
            conn.close()
        
        return self._execute_db_operation("adding participant", supabase_op, sqlite_op)
    
    def save_message(self, participant_id: str, user_msg: Optional[str], ai_msg: Optional[str]) -> bool:
        """Save conversation message"""
        try:
            if self.use_supabase:
                result = supabase_client.table('conversations').insert({
                    'participant_id': participant_id,
                    'user_message': user_msg,
                    'ai_response': ai_msg,
                    'timestamp': datetime.now().isoformat()
                }).execute()
                return bool(result.data)
            else:
                conn = sqlite3.connect(DATABASE_PATH)
                c = conn.cursor()
                c.execute('''INSERT INTO conversations (participant_id, user_message, ai_response, timestamp)
                            VALUES (?, ?, ?, ?)''',
                         (participant_id, user_msg, ai_msg, datetime.now()))
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            st.error(f"Error saving message: {e}")
            return False
    
    def save_questionnaire(self, participant_id: str, responses: Dict[str, Any]) -> bool:
        """Save questionnaire responses"""
        try:
            responses['participant_id'] = participant_id
            responses['completion_time'] = datetime.now().isoformat() if self.use_supabase else datetime.now()
            
            if self.use_supabase:
                result = supabase_client.table('questionnaire_responses').insert(responses).execute()
                return bool(result.data)
            else:
                conn = sqlite3.connect(DATABASE_PATH)
                c = conn.cursor()
                
                columns = ', '.join(responses.keys())
                placeholders = ', '.join(['?' for _ in responses])
                
                c.execute(f'''INSERT INTO questionnaire_responses ({columns}) VALUES ({placeholders})''',
                         list(responses.values()))
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            st.error(f"Error saving questionnaire: {e}")
            return False
    
    def update_participant_status(self, participant_id: str, status: str) -> bool:
        """Update participant completion status"""
        try:
            if self.use_supabase:
                result = supabase_client.table('participants').update({
                    'status': status,
                    'completion_time': datetime.now().isoformat()
                }).eq('id', participant_id).execute()
                return bool(result.data)
            else:
                conn = sqlite3.connect(DATABASE_PATH)
                c = conn.cursor()
                c.execute('''UPDATE participants SET completion_time = ?, status = ? WHERE id = ?''',
                         (datetime.now(), status, participant_id))
                conn.commit()
                conn.close()
                return True
        except Exception as e:
            st.error(f"Error updating participant: {e}")
            return False
    
    def get_conversation_history(self, participant_id: str) -> List[tuple]:
        """Get conversation history for a participant"""
        try:
            if self.use_supabase:
                result = supabase_client.table('conversations').select('*').eq('participant_id', participant_id).order('timestamp').execute()
                if result.data:
                    return [(row['user_message'], row['ai_response']) for row in result.data]
                return []
            else:
                conn = sqlite3.connect(DATABASE_PATH)
                c = conn.cursor()
                c.execute('''SELECT user_message, ai_response FROM conversations 
                           WHERE participant_id = ? ORDER BY timestamp''', (participant_id,))
                messages = c.fetchall()
                conn.close()
                return messages
        except Exception as e:
            st.error(f"Error getting conversation history: {e}")
            return []
    
    def export_conversation_flow_csv(self) -> pd.DataFrame:
        """Export conversation flows as CSV"""
        try:
            if self.use_supabase:
                # Get all conversations with participant info
                conversations = supabase_client.table('conversations').select('*').execute()
                participants = supabase_client.table('participants').select('*').execute()
                questionnaires = supabase_client.table('questionnaire_responses').select('*').execute()
                
                if not conversations.data:
                    return pd.DataFrame()
                
                # Convert to DataFrames
                conv_df = pd.DataFrame(conversations.data)
                part_df = pd.DataFrame(participants.data) if participants.data else pd.DataFrame()
                quest_df = pd.DataFrame(questionnaires.data) if questionnaires.data else pd.DataFrame()
                
            else:
                conn = sqlite3.connect(DATABASE_PATH)
                conv_df = pd.read_sql_query('''
                    SELECT c.*, p.start_time as participant_start_time 
                    FROM conversations c 
                    LEFT JOIN participants p ON c.participant_id = p.id 
                    ORDER BY c.participant_id, c.timestamp
                ''', conn)
                quest_df = pd.read_sql_query("SELECT * FROM questionnaire_responses", conn)
                conn.close()
            
            # Filter for actual conversations (not just system messages)
            user_conversations = conv_df[conv_df['user_message'].notna() & (conv_df['user_message'] != '')]
            
            # Add questionnaire data if available
            if not quest_df.empty:
                user_conversations = user_conversations.merge(
                    quest_df[['participant_id', 'facione_critical_thinking_score', 'age', 'education']], 
                    on='participant_id', 
                    how='left'
                )
            
            return user_conversations
            
        except Exception as e:
            st.error(f"Error exporting conversation flow: {e}")
            return pd.DataFrame()

    def get_admin_data(self) -> Dict[str, pd.DataFrame]:
        """Get all data for admin panel"""
        try:
            if self.use_supabase:
                participants = supabase_client.table('participants').select('*').execute()
                conversations = supabase_client.table('conversations').select('*').execute()
                questionnaires = supabase_client.table('questionnaire_responses').select('*').execute()
                
                return {
                    'participants': pd.DataFrame(participants.data if participants.data else []),
                    'conversations': pd.DataFrame(conversations.data if conversations.data else []),
                    'questionnaires': pd.DataFrame(questionnaires.data if questionnaires.data else [])
                }
            else:
                conn = sqlite3.connect(DATABASE_PATH)
                
                participants_df = pd.read_sql_query("SELECT * FROM participants", conn)
                conversations_df = pd.read_sql_query("SELECT * FROM conversations", conn)
                questionnaires_df = pd.read_sql_query("SELECT * FROM questionnaire_responses", conn)
                
                conn.close()
                
                return {
                    'participants': participants_df,
                    'conversations': conversations_df,
                    'questionnaires': questionnaires_df
                }
        except Exception as e:
            st.error(f"Error getting admin data: {e}")
            return {'participants': pd.DataFrame(), 'conversations': pd.DataFrame(), 'questionnaires': pd.DataFrame()}

# Create global instance
db_manager = DatabaseManager()