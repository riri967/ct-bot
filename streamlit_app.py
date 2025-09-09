"""
Streamlit Critical Thinking Study Interface
Integrates Academic Topic Generator -> RAG -> Socratic Chatbot
"""

# Fix for ChromaDB SQLite compatibility on Streamlit Cloud
import sys
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import streamlit as st
import sqlite3
import uuid
import json
from datetime import datetime
from socratic_chatbot import SimplifiedOrchestrator
from api_utils import get_model_with_retry, generate_with_retry
import os

# Configuration
from config import GEMINI_API_KEY, DATABASE_PATH

API_KEY = GEMINI_API_KEY
DB_PATH = DATABASE_PATH

def init_database():
    """Initialize SQLite database with comprehensive tables"""
    conn = sqlite3.connect(DB_PATH)
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

def save_message(participant_id, user_msg, ai_msg):
    """Save conversation to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO conversations (participant_id, user_message, ai_response, timestamp)
                 VALUES (?, ?, ?, ?)''', (participant_id, user_msg, ai_msg, datetime.now()))
    conn.commit()
    conn.close()

def save_scenario(participant_id, scenario, question):
    """Save generated scenario to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO study_scenarios (participant_id, scenario_text, initial_question, generation_timestamp)
                 VALUES (?, ?, ?, ?)''', (participant_id, scenario, question, datetime.now()))
    conn.commit()
    conn.close()

def save_questionnaire_responses(participant_data):
    """Save all questionnaire responses to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Extract participant ID
    participant_id = st.session_state.participant_id
    
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
        participant_data.get('age'),
        participant_data.get('education'),
        participant_data.get('ct_experience'),
        participant_data.get('post_q1_easy_to_use'),
        participant_data.get('post_q2_felt_confident'),
        participant_data.get('post_q3_use_again'),
        participant_data.get('post_q4_engaging'),
        participant_data.get('post_q5_natural_flow'),
        participant_data.get('post_q6_disengagement'),
        participant_data.get('post_q7_encouraged_reflection'),
        participant_data.get('post_q8_multiple_perspectives'),
        participant_data.get('post_q9_critical_thinking_ways'),
        participant_data.get('post_q10_learned_something'),
        participant_data.get('post_q11_design_support'),
        participant_data.get('post_q12_confusion'),
        participant_data.get('post_q13_application'),
        participant_data.get('post_q14_improvements'),
        participant_data.get('post_q15_valuable'),
        participant_data.get('post_q16_recommend'),
        participant_data.get('post_q17_other_comments'),
        participant_data.get('facione_critical_thinking_score'),
        datetime.now()
    ))
    
    # Update participant end time
    c.execute('''UPDATE participants SET end_time = ?, status = 'completed' WHERE id = ?''',
              (datetime.now(), participant_id))
    
    conn.commit()
    conn.close()

def get_conversation_history(participant_id):
    """Retrieve conversation history"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT user_message, ai_response FROM conversations 
                 WHERE participant_id = ? ORDER BY timestamp''', (participant_id,))
    messages = c.fetchall()
    conn.close()
    return messages

def score_conversation_facione(scenario, question, conversation_history):
    """Score the entire conversation using Facione framework"""
    
    FACIONE_SYSTEM_PROMPT = """You are a highly trained expert in educational assessment, specialising in evaluating critical thinking using the Facione framework.

**Scoring Instructions**  
Assign a floating-point score between **1.0 and 4.0** (e.g., 1.3, 2.8, 3.9).  
Use the **full scoring range**, not just middle values.  
Decimal scores are mandatory (e.g., 2.1, 3.4), not just 1.0, 2.0, etc.

**Facione Critical Thinking Rubric**
- **4.0 — Strong**: Sophisticated reasoning across most of the six Facione skills; insightful, balanced, and justified.
- **3.0 — Acceptable**: Competent demonstration of reasoning with some gaps; mostly justified.
- **2.0 — Unacceptable**: Weak logic, missing key perspectives, limited justification.
- **1.0 — Weak**: Biased, unjustified, or fallacious reasoning; little or no critical thinking demonstrated.

You return only floating-point scores in strict JSON format:
{"ai_score": 3.7}

Be analytical, thoughtful, and fair. You play a vital role in nurturing students' critical thinking potential."""

    # Build conversation text
    conversation_text = f"Original Scenario: {scenario}\nInitial Question: {question}\n\nConversation:\n"
    
    for i, (user_msg, ai_msg) in enumerate(conversation_history, 1):
        if user_msg:  # Skip empty user messages
            conversation_text += f"Student {i}: {user_msg}\nEducator {i}: {ai_msg}\n\n"
    
    user_prompt = f"""You are a qualified academic marker trained in evaluating critical thinking in student writing.

**CONVERSATION CONTEXT:**
This was a Socratic dialogue about critical thinking. The student engaged with an AI tutor discussing a real-world ethical dilemma.

**FULL CONVERSATION TO EVALUATE:**
\"\"\"{conversation_text}\"\"\"

**Your Task**:  
Evaluate this student's demonstration of critical thinking throughout the conversation using the Facione framework. Score from **1.0 to 4.0**, using **floating-point precision** (e.g., 2.3, 3.8).

**Assess Based on These Six Facione Skills**:
1. **Interpretation** – Does the student accurately comprehend and explain the meaning of information?
2. **Analysis** – Do they identify relationships between ideas and break down arguments logically?
3. **Evaluation** – Do they assess the credibility of claims and the quality of reasoning?
4. **Inference** – Do they draw well-supported conclusions and avoid fallacies?
5. **Explanation** – Do they clearly communicate reasons and justifications?
6. **Self-Regulation** – Do they show awareness of their own reasoning and consider alternative perspectives?

**Focus on the student's responses only**, not the educator's questions.

Rubric:
- **4 — Strong**: Accurately interprets evidence and arguments; identifies key pro/con claims; analyses alternative viewpoints; draws warranted, non-fallacious conclusions; justifies reasoning clearly; follows evidence fairly.
- **3 — Acceptable**: Mostly interprets evidence accurately; identifies relevant arguments; offers some evaluation of alternatives; draws mostly valid conclusions; justifies some reasoning; generally fair.
- **2 — Unacceptable**: Misinterprets evidence; misses or ignores key counterarguments; evaluates alternatives superficially; draws weak or fallacious conclusions; provides limited justification; defends views based on preconceptions.
- **1 — Weak**: Biased or closed-minded reasoning; ignores alternatives; uses irrelevant or fallacious arguments; fails to justify claims; clings to unsupported views.

Output Format:
Return only:
{{"ai_score": <float>}}
e.g.:
{{"ai_score": 2.6}}

No explanation. No labels. Just the JSON."""

    try:
        # Use existing API setup
        model = get_model_with_retry(
            model_name="gemini-2.0-flash",
            purpose='stimulus_generation',
            temperature=0.1,
            top_p=0.9,
            top_k=50,
            max_output_tokens=1024
        )
        
        response = generate_with_retry(model, f"{FACIONE_SYSTEM_PROMPT}\n\n{user_prompt}")
        
        # Parse JSON response
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:-3].strip()
        elif response.startswith('```'):
            response = response[3:-3].strip()
            
        score_data = json.loads(response)
        return float(score_data.get("ai_score", 2.5))
        
    except Exception as e:
        print(f"Facione scoring error: {e}")
        return 2.5  # Default neutral score if scoring fails

def main():
    st.set_page_config(page_title="Critical Thinking Study", layout="centered")
    
    # Check for admin panel access
    query_params = st.query_params
    if query_params.get("admin") == "true":
        show_admin_panel()
        return
    
    # Initialize database
    init_database()
    
    # Initialize session state
    if 'participant_id' not in st.session_state:
        st.session_state.participant_id = str(uuid.uuid4())
        
        # Create participant record
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO participants (id, start_time) 
                     VALUES (?, ?)''', (st.session_state.participant_id, datetime.now()))
        conn.commit()
        conn.close()
    
    if 'orchestrator' not in st.session_state:
        st.session_state.orchestrator = SimplifiedOrchestrator(API_KEY)
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'stimulus_generated' not in st.session_state:
        st.session_state.stimulus_generated = False
    
    if 'questionnaire_completed' not in st.session_state:
        st.session_state.questionnaire_completed = False
    
    if 'participant_data' not in st.session_state:
        st.session_state.participant_data = {}
    
    if 'conversation_ended' not in st.session_state:
        st.session_state.conversation_ended = False
    
    if 'post_questionnaire_completed' not in st.session_state:
        st.session_state.post_questionnaire_completed = False
    
    # Title
    st.title("Critical Thinking Study")
    
    # Study flow management
    if not st.session_state.questionnaire_completed:
        show_pre_questionnaire()
        return
    elif st.session_state.conversation_ended and not st.session_state.post_questionnaire_completed:
        show_post_questionnaire()
        return
    elif st.session_state.post_questionnaire_completed:
        show_thank_you()
        return
    
    # Generate opening stimulus if not done
    if not st.session_state.stimulus_generated:
        with st.spinner("Generating discussion topic..."):
            try:
                opening = st.session_state.orchestrator.start_conversation(
                    student_id=st.session_state.participant_id,
                    session_id=st.session_state.participant_id
                )
                
                # Split stimulus and question (they are separated by double newlines)
                if '\n\n' in opening:
                    parts = opening.split('\n\n', 1)
                    stimulus = parts[0].strip()
                    question = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "What are your initial thoughts?"
                else:
                    # Fallback if no separator found
                    stimulus = opening
                    question = "What are your initial thoughts?"
                
                st.session_state.stimulus = stimulus
                st.session_state.question = question
                st.session_state.stimulus_generated = True
                
                # Save the initial scenario and question to database
                initial_content = f"**SCENARIO:**\n{stimulus}\n\n**QUESTION:**\n{question}"
                save_message(st.session_state.participant_id, None, initial_content)
                
            except Exception as e:
                st.error(f"Error generating topic: {e}")
                st.session_state.stimulus = "Consider a complex ethical dilemma where different stakeholders hold conflicting views based on the same evidence."
                st.session_state.question = "What factors should be considered when evaluating such disagreements?"
                st.session_state.stimulus_generated = True
                
                # Save fallback scenario to database
                initial_content = f"**SCENARIO:**\n{st.session_state.stimulus}\n\n**QUESTION:**\n{st.session_state.question}"
                save_message(st.session_state.participant_id, None, initial_content)
    
    # Chat interface
    st.subheader("Discussion")
    
    # Display conversation history
    messages = get_conversation_history(st.session_state.participant_id)
    
    for user_msg, ai_msg in messages:
        if user_msg:  # Student response
            with st.chat_message("user"):
                st.write(user_msg)
        
        # AI response 
        with st.chat_message("assistant"):
            if "**SCENARIO:**" in ai_msg and "**QUESTION:**" in ai_msg:
                # Split scenario and question for separate boxes
                parts = ai_msg.split("**QUESTION:**")
                scenario_part = parts[0].replace("**SCENARIO:**", "").strip()
                question_part = parts[1].strip() if len(parts) > 1 else ""
                
                st.info(f"**SCENARIO:**\n{scenario_part}")
                st.warning(f"**QUESTION:**\n{question_part}")
            else:
                # Regular AI response
                st.write(ai_msg)
    
    # Chat input
    if prompt := st.chat_input("Enter your response"):
        # Display user message
        st.chat_message("user").write(prompt)
        
        # Get AI response
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            ai_response = loop.run_until_complete(
                st.session_state.orchestrator.handle_student_input(
                    st.session_state.participant_id, prompt
                )
            )
            
            # Display AI response
            st.chat_message("assistant").write(ai_response)
            
            # Save to database
            save_message(st.session_state.participant_id, prompt, ai_response)
            
            # Rerun to update display
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {e}")
            st.chat_message("assistant").write("I apologise, but I'm having difficulty responding. Could you rephrase your question?")
    
    # End study button
    if st.button("End Study", type="secondary"):
        # Score the conversation using Facione framework
        with st.spinner("Evaluating conversation..."):
            try:
                conversation_history = get_conversation_history(st.session_state.participant_id)
                scenario = getattr(st.session_state, 'stimulus', 'No scenario available')
                question = getattr(st.session_state, 'question', 'No question available')
                
                facione_score = score_conversation_facione(scenario, question, conversation_history)
                st.session_state.facione_score = facione_score
                print(f"Facione score for participant {st.session_state.participant_id}: {facione_score}")
                
            except Exception as e:
                print(f"Scoring failed: {e}")
                st.session_state.facione_score = 2.5  # Default fallback
        
        st.session_state.conversation_ended = True
        st.rerun()

def show_pre_questionnaire():
    """Display pre-study questionnaire"""
    st.header("Pre-Study Questionnaire")
    st.write("Please answer these brief questions before we begin the critical thinking discussion.")
    
    with st.form("pre_questionnaire"):
        col1, col2 = st.columns(2)
        
        with col1:
            age = st.number_input("Age", min_value=16, max_value=100, value=25)
            
        with col2:
            education = st.selectbox(
                "Highest Education Level",
                ["GCSE", "A-Level", "BTEC", "Bachelor's", "Master's", "PhD"]
            )
        
        ct_experience = st.selectbox(
            "Your perceived Critical Thinking level",
            ["None", "Some", "Moderate", "Extensive"],
            help="Experience with formal critical thinking training, philosophy courses, debate, etc."
        )
        
        submitted = st.form_submit_button("Continue to Discussion")
        
        if submitted:
            # Save participant data (not to database yet)
            st.session_state.participant_data = {
                'age': age,
                'education': education,
                'ct_experience': ct_experience
            }
            st.session_state.questionnaire_completed = True
            st.rerun()

def show_post_questionnaire():
    """Display post-study questionnaire"""
    st.header("Post-Study Questionnaire")
    st.write("Please share your thoughts about the chatbot experience.")
    
    with st.form("post_questionnaire"):
        st.subheader("Usability")
        q1 = st.select_slider("1. I found the chatbot easy to use.", 
                             options=[1, 2, 3, 4, 5], 
                             format_func=lambda x: f"{x} - {'Strongly Disagree' if x==1 else 'Disagree' if x==2 else 'Neutral' if x==3 else 'Agree' if x==4 else 'Strongly Agree'}")
        
        q2 = st.select_slider("2. I felt confident interacting with the chatbot.", 
                             options=[1, 2, 3, 4, 5], 
                             format_func=lambda x: f"{x} - {'Strongly Disagree' if x==1 else 'Disagree' if x==2 else 'Neutral' if x==3 else 'Agree' if x==4 else 'Strongly Agree'}")
        
        q3 = st.select_slider("3. I would be happy to use this chatbot again.", 
                             options=[1, 2, 3, 4, 5], 
                             format_func=lambda x: f"{x} - {'Strongly Disagree' if x==1 else 'Disagree' if x==2 else 'Neutral' if x==3 else 'Agree' if x==4 else 'Strongly Agree'}")
        
        st.subheader("Engagement")
        q4 = st.select_slider("4. I found the chatbot engaging.", 
                             options=[1, 2, 3, 4, 5], 
                             format_func=lambda x: f"{x} - {'Strongly Disagree' if x==1 else 'Disagree' if x==2 else 'Neutral' if x==3 else 'Agree' if x==4 else 'Strongly Agree'}")
        
        q5 = st.select_slider("5. The flow of conversation felt natural.", 
                             options=[1, 2, 3, 4, 5], 
                             format_func=lambda x: f"{x} - {'Strongly Disagree' if x==1 else 'Disagree' if x==2 else 'Neutral' if x==3 else 'Agree' if x==4 else 'Strongly Agree'}")
        
        q6 = st.text_area("6. Did you ever feel bored, stuck, or disengaged during the chat? Please explain.")
        
        st.subheader("Learning & Critical Thinking")
        q7 = st.select_slider("7. The chatbot encouraged me to reflect on my own thinking.", 
                             options=[1, 2, 3, 4, 5], 
                             format_func=lambda x: f"{x} - {'Strongly Disagree' if x==1 else 'Disagree' if x==2 else 'Neutral' if x==3 else 'Agree' if x==4 else 'Strongly Agree'}")
        
        q8 = st.select_slider("8. The chatbot helped me to consider multiple perspectives.", 
                             options=[1, 2, 3, 4, 5], 
                             format_func=lambda x: f"{x} - {'Strongly Disagree' if x==1 else 'Disagree' if x==2 else 'Neutral' if x==3 else 'Agree' if x==4 else 'Strongly Agree'}")
        
        q9 = st.text_area("9. In what ways, if any, did the chatbot make you think more critically?")
        
        q10 = st.text_area("10. Did you feel you learned something new from the interaction?")
        
        st.subheader("Design & Functionality")
        q11 = st.text_area("11. What aspects of the chatbot design (style, wording, pacing) supported your experience?")
        
        q12 = st.text_area("12. Were there parts of the interaction that felt confusing or unclear?")
        
        st.subheader("Applications")
        q13 = st.selectbox("13. Where do you think this chatbot could be most useful?", 
                          ["Higher education", "Professional training", "School-level education", "Personal development", "Other"])
        
        q14 = st.text_area("14. If you could change one thing to improve the chatbot, what would it be?")
        
        st.subheader("Overall Impression")
        q15 = st.select_slider("15. Overall, I found the chatbot valuable.", 
                              options=[1, 2, 3, 4, 5], 
                              format_func=lambda x: f"{x} - {'Strongly Disagree' if x==1 else 'Disagree' if x==2 else 'Neutral' if x==3 else 'Agree' if x==4 else 'Strongly Agree'}")
        
        q16 = st.select_slider("16. I would recommend this chatbot to others.", 
                              options=[1, 2, 3, 4, 5], 
                              format_func=lambda x: f"{x} - {'Strongly Disagree' if x==1 else 'Disagree' if x==2 else 'Neutral' if x==3 else 'Agree' if x==4 else 'Strongly Agree'}")
        
        q17 = st.text_area("17. Please add any other comments or suggestions.")
        
        submitted = st.form_submit_button("Complete Study")
        
        if submitted:
            # Save post-questionnaire data (not to database yet)
            st.session_state.participant_data.update({
                'post_q1_easy_to_use': q1,
                'post_q2_felt_confident': q2,
                'post_q3_use_again': q3,
                'post_q4_engaging': q4,
                'post_q5_natural_flow': q5,
                'post_q6_disengagement': q6,
                'post_q7_encouraged_reflection': q7,
                'post_q8_multiple_perspectives': q8,
                'post_q9_critical_thinking_ways': q9,
                'post_q10_learned_something': q10,
                'post_q11_design_support': q11,
                'post_q12_confusion': q12,
                'post_q13_application': q13,
                'post_q14_improvements': q14,
                'post_q15_valuable': q15,
                'post_q16_recommend': q16,
                'post_q17_other_comments': q17,
                'facione_critical_thinking_score': getattr(st.session_state, 'facione_score', 2.5)
            })
            st.session_state.post_questionnaire_completed = True
            st.rerun()

def show_thank_you():
    """Display thank you page"""
    st.header("Thank You!")
    st.success("Your participation has been completed successfully.")
    st.balloons()
    
    st.write("Your responses have been recorded. Thank you for contributing to our research on critical thinking and AI-powered educational tools.")
    
    # Debug info (remove for production)
    if st.checkbox("Show debug info", value=False):
        st.subheader("Debug Information")
        facione_score = st.session_state.participant_data.get('facione_critical_thinking_score', 'Not available')
        st.metric("Facione Critical Thinking Score", f"{facione_score:.2f}/4.0" if isinstance(facione_score, (int, float)) else facione_score)
        st.json(st.session_state.participant_data)

def show_admin_panel():
    """Show admin panel for data export - add ?admin=true to URL"""
    st.title("🔧 Study Admin Panel")
    
    # Quick stats
    try:
        conn = sqlite3.connect(DB_PATH)
        
        total_participants = pd.read_sql_query("SELECT COUNT(*) as count FROM participants", conn)['count'][0]
        active_convs = pd.read_sql_query(
            "SELECT COUNT(DISTINCT participant_id) as count FROM conversations WHERE user_message IS NOT NULL", 
            conn
        )['count'][0]
        total_exchanges = pd.read_sql_query(
            "SELECT COUNT(*) as count FROM conversations WHERE user_message IS NOT NULL", 
            conn
        )['count'][0]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Participants", total_participants)
        with col2:
            st.metric("Active Conversations", active_convs)
        with col3:
            st.metric("Total Exchanges", total_exchanges)
        
        st.markdown("---")
        
        # Data export
        if st.button("📥 Export All Data"):
            # Export participants
            participants_df = pd.read_sql_query("SELECT * FROM participants ORDER BY start_time DESC", conn)
            conversations_df = pd.read_sql_query("""
                SELECT * FROM conversations 
                ORDER BY participant_id, timestamp
            """, conn)
            
            # Try to get questionnaire data if it exists
            try:
                questionnaire_df = pd.read_sql_query("SELECT * FROM questionnaire_responses", conn)
            except:
                questionnaire_df = pd.DataFrame()
            
            st.download_button(
                label="⬇️ Download Participants CSV",
                data=participants_df.to_csv(index=False),
                file_name=f"participants_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            st.download_button(
                label="⬇️ Download Conversations CSV",
                data=conversations_df.to_csv(index=False),
                file_name=f"conversations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            if not questionnaire_df.empty:
                st.download_button(
                    label="⬇️ Download Questionnaires CSV",
                    data=questionnaire_df.to_csv(index=False),
                    file_name=f"questionnaires_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        # Recent activity
        st.subheader("📋 Recent Activity")
        recent_df = pd.read_sql_query("""
            SELECT 
                p.id as participant_id,
                p.start_time,
                COUNT(c.id) as total_messages,
                COUNT(CASE WHEN c.user_message IS NOT NULL THEN 1 END) as user_responses
            FROM participants p
            LEFT JOIN conversations c ON p.id = c.participant_id
            GROUP BY p.id, p.start_time
            ORDER BY p.start_time DESC
            LIMIT 20
        """, conn)
        
        # Make participant IDs shorter for display
        recent_df['short_id'] = recent_df['participant_id'].str[:8] + '...'
        display_df = recent_df[['short_id', 'start_time', 'total_messages', 'user_responses']].copy()
        st.dataframe(display_df, use_container_width=True)
        
        # Conversation preview
        st.subheader("💬 Latest Conversations")
        latest_convs = pd.read_sql_query("""
            SELECT 
                SUBSTR(participant_id, 1, 8) || '...' as participant,
                user_message,
                ai_response,
                timestamp
            FROM conversations 
            WHERE user_message IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 10
        """, conn)
        
        for _, row in latest_convs.iterrows():
            with st.expander(f"{row['participant']} - {row['timestamp'][:16]}"):
                st.write("**Student:**", row['user_message'])
                ai_preview = row['ai_response'][:150] + "..." if len(row['ai_response']) > 150 else row['ai_response']
                st.write("**AI:**", ai_preview)
        
        conn.close()
        
    except Exception as e:
        st.error(f"Database error: {e}")
        st.info("Note: This admin panel works with the deployed database. Make sure the database exists and is accessible.")

if __name__ == "__main__":
    main()