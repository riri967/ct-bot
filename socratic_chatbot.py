"""
Socratic Questioning Chatbot for Human Study System
RAG-enhanced version with real-world content integration
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import json
import random
import google.generativeai as genai
from rag_stimulus_pipeline import RAGSystem, generate_stimulus_with_question
from academic_topic_generator import seed_concepts, make_topics, simple_select, SITUATIONS

class SocraticConversationAgent:
    """Socratic dialogue agent with adaptive questioning and RAG integration"""
    
    def __init__(self, api_key: str):
        # Use dedicated API key for Socratic responses
        from api_utils import get_model_with_retry
        self.model = get_model_with_retry(
            model_name="gemini-2.0-flash",
            purpose='socratic_responses',
            temperature=0.4,
            top_p=0.9,
            top_k=50,
            max_output_tokens=2048
        )
        self.paul_elder_coverage = {
            "purpose": 0, "questions": 0, "information": 0, "inference": 0,
            "concepts": 0, "assumptions": 0, "implications": 0, "point_of_view": 0
        }
        self.conversation_phase = "beginning"
        
        # Initialize RAG system for real-world content
        try:
            self.rag_system = RAGSystem()
            print("RAG system initialized for real-world content integration")
        except Exception as e:
            print(f"RAG initialization failed: {e}. Using fallback content generation.")
            self.rag_system = None
        
        # Current conversation context for RAG
        self.current_topic = None
        self.rag_context = []
    
    def generate_opening(self, topic_hint: str = None) -> str:
        """Generate engaging Socratic opening using academic topic generator + RAG content"""
        
        # Generate academic topics if no hint provided
        if not topic_hint:
            try:
                print("Generating academic topics...")
                concepts = seed_concepts()
                print(f"Found concepts: {concepts[:3]}...")
                
                # Generate concrete situational topics
                situational_topics = make_topics(concepts[:5], SITUATIONS[:8], limit=20)
                selected_topics = simple_select(situational_topics, k=3)
                
                # Pick one topic for this session
                topic_hint = random.choice(selected_topics)
                print(f"Selected situational topic: {topic_hint}")
                
            except Exception as e:
                print(f"Academic topic generation failed: {e}")
                # Fallback to predefined topics
                fallback_topics = [
                    "ethics in AI", "privacy in social media", "accountability in healthcare",
                    "justice in education", "transparency in government"
                ]
                topic_hint = random.choice(fallback_topics)
        
        self.current_topic = topic_hint
        
        # Use RAG system to generate stimulus with question
        if self.rag_system:
            try:
                print(f"Generating RAG stimulus for: {topic_hint}")
                # Use the enhanced stimulus generator that includes initial question
                stimulus_with_question = generate_stimulus_with_question(topic_hint, self.rag_system)
                
                if stimulus_with_question and len(stimulus_with_question.strip()) > 50:
                    self.paul_elder_coverage["questions"] += 1
                    return stimulus_with_question
                
            except Exception as e:
                print(f"RAG stimulus generation failed: {e}")
        
        # Fallback to traditional approach if RAG fails
        return self._generate_fallback_opening(topic_hint)
    
    def _generate_fallback_opening(self, topic: str) -> str:
        """Generate fallback opening when RAG is unavailable"""
        scenario_prompt = f"""Write a realistic news-style scenario about {topic}. 

Write ONLY the scenario content (150-200 words) that describes:
- A specific organization, location, or case study
- The dilemma or decision being faced
- Different stakeholders with conflicting viewpoints
- Concrete details and realistic circumstances

Do not include any introduction, commentary, or questions. Start directly with the scenario."""

        question_prompt = f"""Write a single Socratic question about {topic}.

Requirements:
- One sentence only
- Thought-provoking and specific
- Encourages critical thinking about assumptions or reasoning
- Natural conversational tone

Write only the question sentence with no extra text:"""

        try:
            from api_utils import generate_with_retry
            
            # Generate scenario
            scenario = generate_with_retry(self.model, scenario_prompt).strip()
            
            # Clean up scenario - remove any meta-commentary
            if scenario.lower().startswith(("here's", "okay", "here is")):
                lines = scenario.split('\n')
                if len(lines) > 1:
                    scenario = '\n'.join(lines[1:]).strip()
            
            # Generate question
            question = generate_with_retry(self.model, question_prompt).strip()
            question = question.replace("Question:", "").replace("QUESTION:", "").strip()
            if question.startswith('"') and question.endswith('"'):
                question = question[1:-1].strip()
            
            self.paul_elder_coverage["questions"] += 1
            return f"{scenario}\n\n{question}"
            
        except Exception as e:
            # Hardcoded fallback with proper format
            scenario = f"Consider a complex ethical dilemma involving {topic} where different stakeholders hold conflicting views based on the same evidence, each presenting reasonable arguments for their position."
            question = "What assumptions might be driving the different positions you see here?"
            return f"{scenario}\n\n{question}"
    
    def respond_to_student(self, student_response: str, conversation_context: str) -> str:
        """Generate adaptive Socratic response with RAG context awareness"""
        
        # Determine conversation phase based on exchange count
        exchange_count = self.paul_elder_coverage["questions"]
        
        if exchange_count <= 3:
            phase = "beginning"
            phase_guidance = "Use open, exploratory questions. Keep questions accessible. Create safe environment for exploration."
        elif exchange_count <= 8:
            phase = "middle"  
            phase_guidance = "Use focused, probing questions. Challenge assumptions systematically. Develop critical thinking skills."
        else:
            phase = "end"
            phase_guidance = "Use integrative, reflective questions. Promote synthesis and metacognition."
        
        # Choose Socratic technique based on phase with variety
        techniques = {
            "beginning": ["clarification", "personal_relevance", "example_seeking", "curiosity_building", "assumption_probing"],
            "middle": ["assumption_probing", "evidence_examination", "perspective_taking", "clarification", "meta_questioning"],
            "end": ["synthesis_building", "meta_questioning", "reflection", "perspective_taking", "evidence_examination"]
        }
        
        # Avoid overusing implication_exploration which leads to "how would this play out" questions
        available_techniques = [t for t in techniques[phase] if t != "implication_exploration" or random.random() < 0.3]
        technique = random.choice(available_techniques if available_techniques else techniques[phase])
        
        # Choose Paul-Elder focus (balance coverage)
        paul_elder_elements = ["purpose", "questions", "information", "inference", 
                             "concepts", "assumptions", "implications", "point_of_view"]
        least_covered = min(self.paul_elder_coverage.items(), key=lambda x: x[1])[0]
        
        # Build context from RAG if available
        rag_context_text = ""
        if self.rag_context and self.current_topic:
            context_parts = []
            for doc in self.rag_context[:2]:  # Use top 2 most relevant
                source = doc.get('metadata', {}).get('source', 'Source')
                title = doc.get('metadata', {}).get('title', 'Context')
                context_parts.append(f"[{source}: {title}]")
            rag_context_text = f"\nREAL-WORLD CONTEXT: {' | '.join(context_parts)}"
        
        response_prompt = f"""You are a skilled Socratic educator in dialogue with a thoughtful student. Generate a natural, engaging response that develops their critical thinking.

CONVERSATION PHASE: {phase}
PHASE GUIDANCE: {phase_guidance}

STUDENT RESPONSE: "{student_response}"
CONVERSATION CONTEXT: {conversation_context}
TOPIC FOCUS: {self.current_topic or 'general critical thinking'}{rag_context_text}

SOCRATIC TECHNIQUE: {technique}
- clarification: "What do you mean when you say...?" or "Help me understand your thinking about..."
- assumption_probing: "What are you taking for granted here?" or "What if that assumption doesn't hold?"  
- evidence_examination: "What evidence supports that view?" or "How reliable is that source?"
- perspective_taking: "How might [stakeholder] see this differently?" or "What would the other side argue?"
- implication_exploration: "If that's true, what follows?" or "What are the broader consequences?"
- personal_relevance: "Have you experienced something similar?" or "How does this connect to your life?"
- example_seeking: "Can you give me a specific instance?" or "What would that look like in practice?"
- curiosity_building: "What puzzles you most about this?" or "What would you want to investigate?"
- synthesis_building: "How do these ideas connect?" or "What patterns do you see?"
- meta_questioning: "How did you arrive at that conclusion?" or "What's your thinking process here?"
- reflection: "What have you learned about your own reasoning?" or "How has your view shifted?"

PAUL-ELDER FOCUS: {least_covered}
- purpose: Explore goals and intentions
- questions: Help them generate questions
- information: Examine evidence and data  
- inference: Look at conclusions and reasoning
- concepts: Clarify key ideas
- assumptions: Identify what's taken for granted
- implications: Consider consequences
- point_of_view: Examine different perspectives

ESSENTIAL PRINCIPLES:
1. NEVER start with formulaic praise ("That's really...", "Great point...")
2. Begin directly with engagement of their specific ideas
3. Show genuine curiosity about their reasoning
4. Use their exact words and build on their concepts
5. Ask questions that make them think deeper
6. Keep it conversational and natural
7. Challenge them respectfully
8. AVOID repetitive patterns like "How would this play out?" or "Can you describe the situation?"
9. Focus on ONE specific aspect of their response, not broad scenarios
10. Ask about their reasoning process, not just outcomes

EXAMPLES OF DIRECT ENGAGEMENT (vary your approach):
- "You've identified something crucial about..."
- "Following that logic, it seems like..."
- "Your point about X raises the question of..."
- "What you're describing sounds like..."
- "That distinction you're making between X and Y..."
- "The tension you've highlighted between..."
- "When you say [their exact words], what drives that thinking?"
- "I'm curious about how you weighed..."

AVOID THESE REPETITIVE PATTERNS:
- "How do you think this would play out?"
- "Can you describe what might happen?"
- "What would the situation look like?"
- "How would this scenario develop?"

Instead, focus on their specific reasoning, assumptions, or the logic behind their statements.

Create a response that feels like you're genuinely thinking alongside them."""

        try:
            response = self.model.generate_content(response_prompt)
            self.paul_elder_coverage[least_covered] += 1
            return response.text.strip()
        except Exception as e:
            return f"That's an interesting perspective. What led you to that conclusion? Can you help me understand your reasoning?"

class SimplifiedOrchestrator:
    """RAG-enhanced orchestrator for human study integration"""
    
    def __init__(self, api_key: str):
        self.conversation_agent = SocraticConversationAgent(api_key)
        self.conversation_history = []
        self.exchange_count = 0
        self.current_scenario = None
    
    def start_conversation(self, student_id: str, session_id: str, topic_hint: str = None, **kwargs) -> str:
        """Start conversation with integrated Academic Topic Generator → RAG → Socratic opening"""
        print(f"Starting conversation for student {student_id}")
        
        # Generate opening using integrated academic topic generator + RAG system
        # This now includes: academic topic selection → RAG context → stimulus + initial question
        full_opening = self.conversation_agent.generate_opening(topic_hint)
        
        # Log opening
        opening_exchange = {
            "type": "opening",
            "educator_response": full_opening,
            "timestamp": datetime.utcnow().isoformat(),
            "socratic_technique": "academic_rag_opening",
            "topic": self.conversation_agent.current_topic
        }
        
        self.conversation_history.append(opening_exchange)
        self.exchange_count = 0
        
        print(f"Generated opening for topic: {self.conversation_agent.current_topic}")
        return full_opening
    
    
    async def handle_student_input(self, session_id: str, student_response: str) -> str:
        """Handle student input with Socratic response"""
        
        self.exchange_count += 1
        
        # Get conversation context
        context = self._get_conversation_context()
        
        # Generate Socratic response
        educator_response = self.conversation_agent.respond_to_student(
            student_response, context
        )
        
        # Log exchange
        exchange = {
            "type": "dialogue", 
            "student_response": student_response,
            "educator_response": educator_response,
            "timestamp": datetime.utcnow().isoformat(),
            "exchange_number": self.exchange_count
        }
        
        self.conversation_history.append(exchange)
        
        return educator_response
    
    def _get_conversation_context(self, last_n: int = 3) -> str:
        """Get recent conversation context"""
        if len(self.conversation_history) <= 1:
            return "Beginning of conversation."
        
        recent = self.conversation_history[-last_n:]
        context_parts = []
        
        for exchange in recent:
            if exchange["type"] == "opening":
                context_parts.append(f"Opened with: {exchange['educator_response'][:100]}...")
            elif exchange["type"] == "dialogue":
                context_parts.append(f"Student: {exchange['student_response'][:80]}...")
                context_parts.append(f"Educator: {exchange['educator_response'][:80]}...")
        
        return " | ".join(context_parts)