"""
Deployment-focused database manager
Prioritizes Supabase for online deployment, SQLite as fallback
"""

import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
import streamlit as st
from config import USE_SUPABASE, get_supabase_url, get_supabase_key, DATABASE_PATH

# Supabase import (only when needed)
if USE_SUPABASE:
    try:
        from supabase import create_client, Client
    except ImportError:
        st.error("Supabase library not installed. Please add 'supabase>=2.0.0' to requirements.txt")
        USE_SUPABASE = False

class DatabaseManager:
    """Handles database operations with Supabase priority for deployment"""
    
    def __init__(self):
        self.use_supabase = USE_SUPABASE
        self.supabase_client = None
        
        if self.use_supabase:
            try:
                self.supabase_client = create_client(get_supabase_url(), get_supabase_key())
                # Verify connection
                self.supabase_client.table('participants').select('id').limit(1).execute()
            except Exception as e:
                st.warning(f"Supabase connection failed: {e}. Falling back to SQLite.")
                self.use_supabase = False
        
        if not self.use_supabase:
            self.init_sqlite_database()
    
    def init_sqlite_database(self):
        """Initialize SQLite database (fallback)"""
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS participants (
            id TEXT PRIMARY KEY,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
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
    
    def create_participant(self, participant_id: str) -> bool:
        """Create new participant"""
        if self.use_supabase:
            try:
                self.supabase_client.table('participants').insert({
                    'id': participant_id,
                    'start_time': datetime.now().isoformat(),
                    'status': 'active'
                }).execute()
                return True
            except Exception as e:
                st.error(f"Failed to create participant in Supabase: {e}")
                return False
        else:
            try:
                conn = sqlite3.connect(DATABASE_PATH)
                c = conn.cursor()
                c.execute('''INSERT OR IGNORE INTO participants (id, start_time) 
                             VALUES (?, ?)''', (participant_id, datetime.now()))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                st.error(f"Failed to create participant in SQLite: {e}")
                return False
    
    def save_conversation(self, participant_id: str, user_message: str, ai_response: str) -> bool:
        """Save conversation"""
        if self.use_supabase:
            try:
                self.supabase_client.table('conversations').insert({
                    'participant_id': participant_id,
                    'user_message': user_message,
                    'ai_response': ai_response,
                    'timestamp': datetime.now().isoformat()
                }).execute()
                return True
            except Exception as e:
                st.error(f"Failed to save conversation to Supabase: {e}")
                return False
        else:
            try:
                conn = sqlite3.connect(DATABASE_PATH)
                c = conn.cursor()
                c.execute('''INSERT INTO conversations (participant_id, user_message, ai_response, timestamp)
                             VALUES (?, ?, ?, ?)''', (participant_id, user_message, ai_response, datetime.now()))
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                st.error(f"Failed to save conversation to SQLite: {e}")
                return False
    
    def save_questionnaire(self, participant_id: str, data: Dict) -> bool:
        """Save questionnaire responses"""
        if self.use_supabase:
            try:
                # Prepare data for Supabase
                supabase_data = {
                    'participant_id': participant_id,
                    'completion_time': datetime.now().isoformat(),
                    **data
                }
                
                self.supabase_client.table('questionnaire_responses').insert(supabase_data).execute()
                
                # Update participant status
                self.supabase_client.table('participants').update({
                    'end_time': datetime.now().isoformat(),
                    'status': 'completed'
                }).eq('id', participant_id).execute()
                
                return True
            except Exception as e:
                st.error(f"Failed to save questionnaire to Supabase: {e}")
                return False
        else:
            try:
                conn = sqlite3.connect(DATABASE_PATH)
                c = conn.cursor()
                
                # Insert questionnaire data
                c.execute('''INSERT INTO questionnaire_responses (
                    participant_id, age, education, ct_experience,
                    post_q1_easy_to_use, post_q2_felt_confident, post_q3_use_again,
                    post_q4_engaging, post_q5_natural_flow, post_q6_disengagement,
                    post_q7_encouraged_reflection, post_q8_multiple_perspectives,
                    post_q9_critical_thinking_ways, post_q10_learned_something,
                    post_q11_design_support, post_q12_confusion, post_q13_application,
                    post_q14_improvements, post_q15_valuable, post_q16_recommend,
                    post_q17_other_comments, facione_critical_thinking_score, completion_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                    participant_id,
                    data.get('age'),
                    data.get('education'),
                    data.get('ct_experience'),
                    data.get('post_q1_easy_to_use'),
                    data.get('post_q2_felt_confident'),
                    data.get('post_q3_use_again'),
                    data.get('post_q4_engaging'),
                    data.get('post_q5_natural_flow'),
                    data.get('post_q6_disengagement'),
                    data.get('post_q7_encouraged_reflection'),
                    data.get('post_q8_multiple_perspectives'),
                    data.get('post_q9_critical_thinking_ways'),
                    data.get('post_q10_learned_something'),
                    data.get('post_q11_design_support'),
                    data.get('post_q12_confusion'),
                    data.get('post_q13_application'),
                    data.get('post_q14_improvements'),
                    data.get('post_q15_valuable'),
                    data.get('post_q16_recommend'),
                    data.get('post_q17_other_comments'),
                    data.get('facione_critical_thinking_score'),
                    datetime.now()
                ))
                
                # Update participant
                c.execute('''UPDATE participants SET end_time = ?, status = 'completed' WHERE id = ?''',
                          (datetime.now(), participant_id))
                
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                st.error(f"Failed to save questionnaire to SQLite: {e}")
                return False
    
    def get_admin_stats(self) -> Dict:
        """Get statistics for admin panel"""
        if self.use_supabase:
            try:
                participants = self.supabase_client.table('participants').select('id').execute().data
                conversations = self.supabase_client.table('conversations').select('participant_id').execute().data
                active_conversations = len(set(conv['participant_id'] for conv in conversations if conv.get('participant_id')))
                
                return {
                    'total_participants': len(participants),
                    'active_conversations': active_conversations,
                    'total_exchanges': len(conversations),
                    'database_type': 'Supabase'
                }
            except Exception as e:
                st.error(f"Failed to get Supabase stats: {e}")
                return {'error': str(e), 'database_type': 'Supabase (Error)'}
        else:
            try:
                conn = sqlite3.connect(DATABASE_PATH)
                stats = {
                    'total_participants': pd.read_sql_query("SELECT COUNT(*) as count FROM participants", conn)['count'][0],
                    'active_conversations': pd.read_sql_query(
                        "SELECT COUNT(DISTINCT participant_id) as count FROM conversations WHERE user_message IS NOT NULL", 
                        conn
                    )['count'][0],
                    'total_exchanges': pd.read_sql_query(
                        "SELECT COUNT(*) as count FROM conversations WHERE user_message IS NOT NULL", 
                        conn
                    )['count'][0],
                    'database_type': 'SQLite'
                }
                conn.close()
                return stats
            except Exception as e:
                return {'error': str(e), 'database_type': 'SQLite (Error)'}
    
    def export_data(self) -> Dict[str, pd.DataFrame]:
        """Export all data for admin download"""
        if self.use_supabase:
            try:
                participants_data = self.supabase_client.table('participants').select('*').execute().data
                conversations_data = self.supabase_client.table('conversations').select('*').execute().data
                questionnaire_data = self.supabase_client.table('questionnaire_responses').select('*').execute().data
                
                return {
                    'participants': pd.DataFrame(participants_data),
                    'conversations': pd.DataFrame(conversations_data),
                    'questionnaires': pd.DataFrame(questionnaire_data)
                }
            except Exception as e:
                st.error(f"Failed to export Supabase data: {e}")
                return {}
        else:
            try:
                conn = sqlite3.connect(DATABASE_PATH)
                
                participants_df = pd.read_sql_query("SELECT * FROM participants ORDER BY start_time DESC", conn)
                conversations_df = pd.read_sql_query("SELECT * FROM conversations ORDER BY participant_id, timestamp", conn)
                
                try:
                    questionnaire_df = pd.read_sql_query("SELECT * FROM questionnaire_responses", conn)
                except:
                    questionnaire_df = pd.DataFrame()
                
                conn.close()
                
                return {
                    'participants': participants_df,
                    'conversations': conversations_df,
                    'questionnaires': questionnaire_df
                }
            except Exception as e:
                st.error(f"Failed to export SQLite data: {e}")
                return {}

# Global database manager instance
db_manager = DatabaseManager()