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
import pandas as pd
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
    
    # Initialize session state - ensure one participant per session
    if 'participant_id' not in st.session_state:
        st.session_state.participant_id = str(uuid.uuid4())
        st.session_state.participant_created = False
    
    if 'consent_given' not in st.session_state:
        st.session_state.consent_given = False
    
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
    
    # Study flow management - now includes consent
    if not st.session_state.consent_given:
        show_consent_form()
        return
    elif not st.session_state.questionnaire_completed:
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

def show_consent_form():
    """Display consent form and information"""
    st.header("Research Participation Consent")
    
    st.markdown("""
    ### Critical Thinking in Conversational AI Systems
    
    Welcome and thank you for considering taking part in this online study.
    
    Before you decide we would like you to understand why the research is being done and what it would involve for you. Please contact one of the investigators using the contact details below if you have any questions.
    
    The purpose of this study is to gain information relating to how people engage in critical thinking discussions with AI chatbots. The study aims to improve AI systems for educational purposes.
    
    This study is part of a student research project supported by Loughborough University. The study will be undertaken by [Student name] and supervised by [Supervisor name].
    
    You will be asked to complete an anonymous online study, which should take no longer than 15 minutes to complete. You do not need to do anything before completing the study. This is a low risk activity and no disadvantages or risks have been identified in association with participating.
    
    You must be over the age of 18 and have the capacity to fully understand and consent to this research.
    
    Loughborough University will be using information/data from you to undertake this study and will act as the data controller for this study. This means that the University is responsible for looking after your information and using it properly. No identifiable personal information will be collected and so your participation in the study will be confidential. The anonymous data will be used in student dissertations. No individual will be identifiable in any report, presentation, or publication. All information will be securely stored on the University computer systems. Anonymised data will be retained until the final project marks have been verified.
    
    After you have read this information and asked any questions you may have, if you are happy to participate, please read the consent section and confirm your consent by checking the tick boxes below. You can withdraw from the study at any time by closing the browser. However, as the study is anonymous once you have submitted the study it will not be possible to withdraw your data from the study.
    
    **Contact Details:**  
    [Tutor name] (Responsible Investigator), School of [Department], Loughborough University, Loughborough, Leicestershire, LE11 3TU, [email]@lboro.ac.uk, 01509 [number]  
    [Student name] (Main investigator), School of [Department], Loughborough University, Loughborough, Leicestershire, LE11 3TU, [email]@student.lboro.ac.uk
    
    **What if I am not happy with how the research was conducted?**  
    If you are not happy with how the research was conducted, please contact the Secretary of the Ethics Review Sub-Committee, Research & Innovation Office, Hazlerigg Building, Loughborough University, Epinal Way, Loughborough, LE11 3TU. Tel: 01509 222423. Email: researchpolicy@lboro.ac.uk
    
    The University also has policies relating to Research Misconduct and Whistle Blowing which are available online at https://www.lboro.ac.uk/internal/research-ethics-integrity/research-integrity/
    
    If you require any further information regarding the General Data Protection Regulations, please see: https://www.lboro.ac.uk/privacy/research-privacy/
    
    ---
    """)
    
    with st.form("consent_form"):
        st.subheader("Informed Consent")
        
        st.markdown("**Please read each statement carefully and tick the boxes to confirm your understanding:**")
        
        consent_1 = st.checkbox("The purpose and details of this study have been explained to me.")
        
        consent_2 = st.checkbox("I understand that this study is designed to further scientific knowledge and that all procedures have received a favourable decision from the Loughborough University Ethics Review Sub-Committee.")
        
        consent_3 = st.checkbox("I have read and understood the information sheet and this consent form.")
        
        consent_4 = st.checkbox("I have had an opportunity to ask questions about my participation.")
        
        consent_5 = st.checkbox("I understand that taking part in the survey is anonymous, only non-identifying demographic information will be collected, e.g. gender.")
        
        consent_6 = st.checkbox("I understand that this questionnaire includes sensitive questions about critical thinking and AI interactions.")
        
        consent_7 = st.checkbox("I understand that I am under no obligation to take part in the study and can withdraw during the survey by closing the browser but will not be able to withdraw once my responses have been submitted.")
        
        consent_8 = st.checkbox("I understand that information I provide will be used for the student's dissertation.")
        
        st.markdown("---")
        st.subheader("Consent to Participate")
        
        final_consent = st.checkbox("**I voluntarily agree to take part in this study.**", key="final_consent")
        
        col1, col2 = st.columns(2)
        
        with col1:
            agree_button = st.form_submit_button("Begin Study", type="primary")
        
        with col2:
            decline_button = st.form_submit_button("I Do Not Consent - Exit", type="secondary")
        
        if decline_button:
            st.error("Thank you for your time. You may close this browser tab.")
            st.stop()
        
        if agree_button:
            all_consents = all([consent_1, consent_2, consent_3, consent_4, consent_5, 
                               consent_6, consent_7, consent_8, final_consent])
            
            if all_consents:
                st.session_state.consent_given = True
                st.rerun()
            else:
                st.error("Please tick all consent boxes to proceed with the study.")

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
            # Create participant record in database when questionnaire is submitted
            if not st.session_state.get('participant_created', False):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('''INSERT OR IGNORE INTO participants (id, start_time, status) 
                             VALUES (?, ?, ?)''', (st.session_state.participant_id, datetime.now(), 'active'))
                conn.commit()
                conn.close()
                st.session_state.participant_created = True
            
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
            
            # Save questionnaire responses to database
            save_questionnaire_responses(st.session_state.participant_data)
            
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

def create_conversation_flow_csv():
    """Create a formatted CSV with conversation flows for each participant"""
    conn = sqlite3.connect(DB_PATH)
    
    # Get all participants with their data
    participants_query = """
    SELECT p.id, p.start_time, p.status,
           q.age, q.education, q.ct_experience,
           q.facione_critical_thinking_score, q.completion_time,
           q.post_q1_easy_to_use, q.post_q2_felt_confident, q.post_q3_use_again,
           q.post_q4_engaging, q.post_q5_natural_flow, q.post_q6_disengagement,
           q.post_q7_encouraged_reflection, q.post_q8_multiple_perspectives,
           q.post_q9_critical_thinking_ways, q.post_q10_learned_something,
           q.post_q11_design_support, q.post_q12_confusion, q.post_q13_application,
           q.post_q14_improvements, q.post_q15_valuable, q.post_q16_recommend,
           q.post_q17_other_comments
    FROM participants p
    LEFT JOIN questionnaire_responses q ON p.id = q.participant_id
    ORDER BY p.start_time
    """
    
    participants_df = pd.read_sql_query(participants_query, conn)
    
    # Create formatted conversation flow data
    conversation_flows = []
    
    for _, participant in participants_df.iterrows():
        participant_id = participant['id']
        short_id = participant_id[:8] + '...'
        
        # Get conversations for this participant
        conv_query = """
        SELECT user_message, ai_response, timestamp
        FROM conversations 
        WHERE participant_id = ? 
        ORDER BY timestamp
        """
        conversations = pd.read_sql_query(conv_query, conn, params=[participant_id])
        
        # Get scenario for this participant  
        scenario_query = """
        SELECT scenario_text, initial_question
        FROM study_scenarios 
        WHERE participant_id = ?
        """
        scenario_result = pd.read_sql_query(scenario_query, conn, params=[participant_id])
        scenario = scenario_result['scenario_text'].iloc[0] if not scenario_result.empty else "No scenario recorded"
        initial_question = scenario_result['initial_question'].iloc[0] if not scenario_result.empty else "No question recorded"
        
        # Build conversation flow
        conversation_text = f"SCENARIO: {scenario}\n\nINITIAL QUESTION: {initial_question}\n\n"
        
        exchange_count = 0
        for _, conv in conversations.iterrows():
            if pd.notna(conv['user_message']):
                exchange_count += 1
                conversation_text += f"EXCHANGE {exchange_count}:\n"
                conversation_text += f"Student: {conv['user_message']}\n"
                conversation_text += f"AI: {conv['ai_response']}\n\n"
        
        # Add to flow data
        flow_row = {
            'participant_id': participant_id,
            'short_id': short_id,
            'start_time': participant['start_time'],
            'end_time': participant.get('completion_time'),
            'status': participant['status'],
            'total_exchanges': exchange_count,
            'age': participant.get('age'),
            'education': participant.get('education'),
            'ct_experience': participant.get('ct_experience'),
            'facione_score': participant.get('facione_critical_thinking_score'),
            'full_conversation_flow': conversation_text,
            'post_q1_easy_to_use': participant.get('post_q1_easy_to_use'),
            'post_q2_felt_confident': participant.get('post_q2_felt_confident'),
            'post_q3_use_again': participant.get('post_q3_use_again'),
            'post_q4_engaging': participant.get('post_q4_engaging'),
            'post_q5_natural_flow': participant.get('post_q5_natural_flow'),
            'post_q6_disengagement': participant.get('post_q6_disengagement'),
            'post_q7_encouraged_reflection': participant.get('post_q7_encouraged_reflection'),
            'post_q8_multiple_perspectives': participant.get('post_q8_multiple_perspectives'),
            'post_q9_critical_thinking_ways': participant.get('post_q9_critical_thinking_ways'),
            'post_q10_learned_something': participant.get('post_q10_learned_something'),
            'post_q11_design_support': participant.get('post_q11_design_support'),
            'post_q12_confusion': participant.get('post_q12_confusion'),
            'post_q13_application': participant.get('post_q13_application'),
            'post_q14_improvements': participant.get('post_q14_improvements'),
            'post_q15_valuable': participant.get('post_q15_valuable'),
            'post_q16_recommend': participant.get('post_q16_recommend'),
            'post_q17_other_comments': participant.get('post_q17_other_comments')
        }
        conversation_flows.append(flow_row)
    
    conn.close()
    return pd.DataFrame(conversation_flows)

def create_post_study_stats_csv():
    """Create CSV with post-study questionnaire responses and conversation stats"""
    conn = sqlite3.connect(DB_PATH)
    
    # Get participants with questionnaire responses and conversation stats
    query = """
    SELECT p.id, p.start_time, p.status,
           q.age, q.education, q.ct_experience,
           q.facione_critical_thinking_score, q.completion_time,
           q.post_q1_easy_to_use, q.post_q2_felt_confident, q.post_q3_use_again,
           q.post_q4_engaging, q.post_q5_natural_flow, q.post_q6_disengagement,
           q.post_q7_encouraged_reflection, q.post_q8_multiple_perspectives,
           q.post_q9_critical_thinking_ways, q.post_q10_learned_something,
           q.post_q11_design_support, q.post_q12_confusion, q.post_q13_application,
           q.post_q14_improvements, q.post_q15_valuable, q.post_q16_recommend,
           q.post_q17_other_comments,
           COUNT(c.user_message) as total_exchanges,
           ROUND((julianday(q.completion_time) - julianday(p.start_time)) * 24 * 60, 2) as session_duration_minutes
    FROM participants p
    LEFT JOIN questionnaire_responses q ON p.id = q.participant_id
    LEFT JOIN conversations c ON p.id = c.participant_id AND c.user_message IS NOT NULL
    WHERE q.participant_id IS NOT NULL
    GROUP BY p.id
    ORDER BY p.start_time
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def show_admin_panel():
    """Show admin panel for data export - add ?admin=true to URL"""
    st.title("🔧 Study Admin Panel")
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📊 Data Export", "💬 Conversation Viewer", "🧹 Cleanup"])
    
    with tab1:
        # Export options
        st.subheader("📥 Download Study Data")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📋 Post-Study Questionnaires + Stats", type="primary"):
                try:
                    df = create_post_study_stats_csv()
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download Post-Study Data CSV",
                        data=csv,
                        file_name=f"post_study_questionnaires_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    st.success(f"✅ Generated CSV with {len(df)} completed participants")
                except Exception as e:
                    st.error(f"Error creating post-study CSV: {e}")
        
        with col2:
            if st.button("💬 Conversation Flow Export", type="primary"):
                try:
                    df = create_conversation_flow_csv()
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download Conversation Flow CSV",
                        data=csv,
                        file_name=f"conversation_flows_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    st.success(f"✅ Generated conversation flow CSV with {len(df)} participants")
                except Exception as e:
                    st.error(f"Error creating conversation flow CSV: {e}")
        
        with col3:
            if st.button("📊 Raw Data Tables", type="secondary"):
                try:
                    conn = sqlite3.connect(DB_PATH)
                    tables = ['participants', 'conversations', 'questionnaire_responses', 'study_scenarios']
                    
                    for table in tables:
                        try:
                            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                            csv = df.to_csv(index=False)
                            st.download_button(
                                label=f"Download {table}.csv",
                                data=csv,
                                file_name=f"{table}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                                key=f"download_{table}"
                            )
                        except Exception as e:
                            st.write(f"⚠️ {table}: {e}")
                    
                    conn.close()
                    st.success("✅ Raw data tables ready for download")
                except Exception as e:
                    st.error(f"Error creating raw data exports: {e}")
    
    with tab2:
        st.subheader("💬 Individual Conversation Histories")
        
        # Get list of participants with conversations
        try:
            conn = sqlite3.connect(DB_PATH)
            participants_query = """
            SELECT DISTINCT p.id, p.start_time, q.age, q.education, 
                   COUNT(c.user_message) as exchanges,
                   q.facione_critical_thinking_score
            FROM participants p
            LEFT JOIN questionnaire_responses q ON p.id = q.participant_id
            LEFT JOIN conversations c ON p.id = c.participant_id AND c.user_message IS NOT NULL
            WHERE q.participant_id IS NOT NULL
            GROUP BY p.id
            ORDER BY p.start_time DESC
            """
            participants_df = pd.read_sql_query(participants_query, conn)
            
            if not participants_df.empty:
                # Create selectbox options
                options = []
                for _, row in participants_df.iterrows():
                    short_id = row['id'][:8] + '...'
                    score = f"{row['facione_critical_thinking_score']:.1f}" if pd.notna(row['facione_critical_thinking_score']) else "N/A"
                    options.append(f"{short_id} | {row['exchanges']} exchanges | Score: {score} | {row['start_time']}")
                
                selected = st.selectbox("Select participant to view conversation:", 
                                      options, 
                                      key="participant_selector")
                
                if selected:
                    # Extract participant ID from selection
                    participant_idx = options.index(selected)
                    participant_id = participants_df.iloc[participant_idx]['id']
                    
                    # Get full conversation
                    conv_query = """
                    SELECT user_message, ai_response, timestamp
                    FROM conversations 
                    WHERE participant_id = ? 
                    ORDER BY timestamp
                    """
                    conversations = pd.read_sql_query(conv_query, conn, params=[participant_id])
                    
                    # Get scenario
                    scenario_query = """
                    SELECT scenario_text, initial_question
                    FROM study_scenarios 
                    WHERE participant_id = ?
                    """
                    scenario_result = pd.read_sql_query(scenario_query, conn, params=[participant_id])
                    
                    # Display conversation
                    if not scenario_result.empty:
                        st.subheader("🎯 Discussion Scenario")
                        st.write(scenario_result['scenario_text'].iloc[0])
                        st.write(f"**Initial Question:** {scenario_result['initial_question'].iloc[0]}")
                        st.divider()
                    
                    st.subheader("💬 Conversation History")
                    
                    exchange_count = 0
                    for _, conv in conversations.iterrows():
                        if pd.notna(conv['user_message']):
                            exchange_count += 1
                            st.write(f"**Exchange {exchange_count}** _{conv['timestamp']}_")
                            
                            with st.container():
                                st.markdown(f"**👤 Student:** {conv['user_message']}")
                                st.markdown(f"**🤖 AI:** {conv['ai_response']}")
                            st.divider()
                    
                    if exchange_count == 0:
                        st.info("No conversation exchanges found for this participant.")
            else:
                st.info("No completed participants found.")
            
            conn.close()
            
        except Exception as e:
            st.error(f"Error loading conversations: {e}")
    
    with tab3:
        st.subheader("🧹 Database Cleanup")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Remove Empty Participants", type="secondary"):
                conn = sqlite3.connect(DB_PATH)
                # Remove participants with no questionnaire responses and no conversations
                result = conn.execute('''
                    DELETE FROM participants 
                    WHERE id NOT IN (SELECT DISTINCT participant_id FROM questionnaire_responses)
                    AND id NOT IN (SELECT DISTINCT participant_id FROM conversations WHERE user_message IS NOT NULL)
                ''')
                deleted_count = result.rowcount
                conn.commit()
                conn.close()
                st.success(f"Removed {deleted_count} empty participant records")
                st.rerun()
        
        with col2:
            # Show count of empty participants
            conn = sqlite3.connect(DB_PATH)
            empty_count = pd.read_sql_query('''
                SELECT COUNT(*) as count FROM participants 
                WHERE id NOT IN (SELECT DISTINCT participant_id FROM questionnaire_responses)
                AND id NOT IN (SELECT DISTINCT participant_id FROM conversations WHERE user_message IS NOT NULL)
            ''', conn)['count'][0]
            conn.close()
            st.metric("Empty Participants", empty_count)
        
        # Quick stats for cleanup tab
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
            completed_questionnaires = pd.read_sql_query(
                "SELECT COUNT(*) as count FROM questionnaire_responses", 
                conn
            )['count'][0]
            
            st.divider()
            st.subheader("📈 Database Overview")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Participants", total_participants)
            with col2:
                st.metric("Active Conversations", active_convs)
            with col3:
                st.metric("Total Exchanges", total_exchanges)
            with col4:
                st.metric("Completed Questionnaires", completed_questionnaires)
            
            conn.close()
            
        except Exception as e:
            st.error(f"Error loading stats: {e}")
    
    # Add stats to first tab too
    with tab1:
        st.divider()
        st.subheader("📈 Study Overview")
        try:
            conn = sqlite3.connect(DB_PATH)
            
            total_participants = pd.read_sql_query("SELECT COUNT(*) as count FROM participants", conn)['count'][0]
            completed_questionnaires = pd.read_sql_query("SELECT COUNT(*) as count FROM questionnaire_responses", conn)['count'][0]
            total_exchanges = pd.read_sql_query("SELECT COUNT(*) as count FROM conversations WHERE user_message IS NOT NULL", conn)['count'][0]
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Registered", total_participants)
            with col2:
                st.metric("Completed Studies", completed_questionnaires)
            with col3:
                st.metric("Total Exchanges", total_exchanges)
            
            conn.close()
        except Exception as e:
            st.error(f"Error loading overview: {e}")

if __name__ == "__main__":
    main()