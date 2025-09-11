"""
Academic Topic Generator for Critical Thinking Stimuli
Builds on existing RAG system to generate scholarly grounded topics and dilemma scenarios.
"""

import re
import json
import hashlib
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from collections import defaultdict

# Import existing RAG functions (assumed to exist)
from rag_stimulus_pipeline import DocumentRetriever, RAGSystem

# 1) CONFIG
BASE_CONCEPTS = []  # Empty by default, populated by seed_concepts()

SITUATIONS = [
    "school surveillance policy", "workplace monitoring ethics", "NHS data sharing policy",
    "social media algorithm transparency", "police body camera implementation", 
    "university AI admissions system", "council budget allocation priorities",
    "housing algorithm fairness review", "banking AI credit decisions",
    "transport data privacy concerns", "hospital resource allocation system",
    "voting technology security debate", "employee performance monitoring",
    "court AI evidence evaluation", "education technology privacy"
]

def seed_concepts() -> List[str]:
    """Extract academic concepts from RAG retrieval if BASE_CONCEPTS is empty"""
    if BASE_CONCEPTS:
        return BASE_CONCEPTS
    
    retriever = DocumentRetriever()
    query = "critical thinking ethics policy education technology environment health justice privacy AI"
    docs = retriever.retrieve(query)
    
    # Extract noun phrases from titles
    concepts = set()
    for doc in docs:
        title = doc.title.lower()
        # Simple regex for 1-3 word noun phrases (capitalized or technical terms)
        phrases = re.findall(r'\b(?:[A-Z][a-z]*(?:\s+[A-Z][a-z]*){0,2}|[a-z]+(?:ing|tion|ity|ics|ism))\b', title)
        for phrase in phrases:
            clean = re.sub(r'[^\w\s]', '', phrase.strip().lower())
            if 3 <= len(clean) <= 25 and clean not in ['the', 'and', 'for', 'with']:
                concepts.add(clean)
    
    # Deduplicate and keep top 20
    concept_list = sorted(list(concepts))[:20]
    return concept_list if concept_list else ['ethics', 'policy', 'technology', 'justice', 'privacy']

# 2) TOPIC GENERATION
def make_topics(concepts: List[str], situations: List[str], limit: int = 60) -> List[str]:
    """Generate specific situational topics instead of abstract concept x context"""
    # Use predefined concrete situations for more relatable scenarios
    topics = situations.copy()
    
    # Add some concept-based variations for variety
    for concept in concepts[:3]:  # Just top 3 concepts
        for situation in situations[:5]:  # Top 5 situations
            if concept.lower() in situation.lower():
                continue  # Skip if concept already in situation
            topics.append(f"{situation} involving {concept}")
    
    # Deduplicate and truncate
    unique_topics = list(dict.fromkeys(topics))
    return unique_topics[:limit]

# 3) TOPIC EXPANSION
def expand_topic(topic: str) -> List[str]:
    """Generate query variants for comprehensive retrieval"""
    concept, context = topic.split(" in ", 1)
    
    queries = [
        f"{concept} definition background",
        f"{concept} {context} current issues UK",
        f"{concept} policy law regulation UK",
        f"{concept} stakeholders concerns {context}",
        f"{concept} ethics risks {context}",
        f"{concept} case studies examples UK",
        f"{concept} debate controversy {context}"
    ]
    return queries

# 4) SIMPLE SELECTION (removed scoring for proof of concept)
def simple_select(topics: List[str], k: int = 8) -> List[str]:
    """Simple selection - just take first k topics for proof of concept"""
    print(f"Selecting {k} topics from {len(topics)} candidates")
    selected = topics[:k]
    print(f"Selected topics: {selected}")
    return selected

# 5) STIMULUS GENERATION
def generate_stimulus(topic: str, rag_system: RAGSystem) -> Dict[str, Any]:
    """Generate structured critical thinking stimulus for topic"""
    print(f"\n--- Generating stimulus for: {topic} ---")
    
    queries = expand_topic(topic)[:3]  # Reduced for proof of concept
    print(f"Using queries: {queries}")
    
    # Collect documents
    all_docs = []
    seen_urls = set()
    
    for query in queries:
        print(f"Querying: {query}")
        docs = rag_system.query_rag(query)
        print(f"Retrieved {len(docs)} documents")
        
        for doc in docs:
            url = doc.get('metadata', {}).get('url', '')
            if url not in seen_urls:
                all_docs.append(doc)
                seen_urls.add(url)
    
    print(f"Total unique documents: {len(all_docs)}")
    
    # Select up to 3 most relevant docs for proof of concept
    selected_docs = all_docs[:3]
    
    # Create context notes
    context_notes = []
    for doc in selected_docs:
        meta = doc.get('metadata', {})
        title = meta.get('title', 'Untitled')[:60]
        source = meta.get('source', 'Unknown')
        date = meta.get('published', 'Unknown date')[:10]  # Just date part
        context_notes.append(f"• {source}: {title} ({date})")
    
    context_text = "\n".join(context_notes)
    print(f"Context notes:\n{context_text}")
    
    # Simple fallback structure for proof of concept
    return {
        'topic': topic,
        'scenario': f'Recent developments in {topic} have created debate among stakeholders. Some argue for immediate implementation of new policies, while others call for more cautious approaches. Different perspectives exist on how to balance innovation, safety, and ethical considerations in this area.',
        'positions': [
            f'Rapid progress in {topic} requires bold policy changes and immediate action.',
            f'A cautious, evidence-based approach to {topic} is necessary to avoid unintended consequences.'
        ],
        'questions': [
            'What key terms and concepts need clearer definition in this debate?',
            'What evidence supports each position and how reliable is it?', 
            'What underlying assumptions are being made by each side?',
            'What would be the long-term implications of each approach?'
        ],
        'sources': [{'title': doc.get('metadata', {}).get('title', 'Unknown'), 
                    'source': doc.get('metadata', {}).get('source', 'Unknown'),
                    'date': doc.get('metadata', {}).get('published', 'Unknown')[:10],
                    'url': doc.get('metadata', {}).get('url', '')} for doc in selected_docs]
    }

# 6) PIPELINE (simplified for proof of concept)
def generate_daily_batch(k: int = 4) -> List[Dict[str, Any]]:
    """Generate batch of k stimuli - simplified for proof of concept"""
    print("=== Starting Daily Batch Generation ===")
    
    rag_system = RAGSystem()
    
    # Get concepts
    print("Step 1: Getting concepts...")
    concepts = seed_concepts()
    print(f"Found concepts: {concepts}")
    
    # Generate topics  
    print(f"\nStep 2: Generating topics from {len(concepts)} concepts and {len(CONTEXTS)} contexts...")
    topics = make_topics(concepts[:3], CONTEXTS[:4], limit=12)  # Smaller for testing
    print(f"Generated {len(topics)} topics")
    
    # Simple selection
    print(f"\nStep 3: Selecting {k} topics...")
    selected_topics = simple_select(topics, k=k)
    
    # Generate stimuli
    print(f"\nStep 4: Generating stimuli for selected topics...")
    stimuli = []
    for topic in selected_topics:
        stimulus = generate_stimulus(topic, rag_system)
        stimuli.append(stimulus)
    
    print(f"\nCompleted generation of {len(stimuli)} stimuli")
    return stimuli

# 8) UTILITIES
def parse_date_safe(date_str: str) -> datetime:
    """Safe date parsing with multiple format attempts"""
    if not date_str:
        return None
    
    formats = ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y%m%dT%H%M%SZ']
    for fmt in formats:
        try:
            return datetime.strptime(date_str[:len(fmt.replace('%', ''))], fmt)
        except:
            continue
    return None

def extract_noun_phrases(text: str) -> List[str]:
    """Extract 1-3 word noun phrases from text"""
    phrases = re.findall(r'\b[A-Z][a-z]*(?:\s+[A-Z][a-z]*){0,2}\b', text)
    return [p.lower() for p in phrases if 3 <= len(p) <= 25]

def llm(prompt: str) -> str:
    """Placeholder LLM function. TODO: Replace with actual Gemini API call"""
    # Fallback JSON response
    return '''{"scenario": "Placeholder scenario", "positions": ["Position A", "Position B"], 
              "questions": ["Question 1", "Question 2", "Question 3", "Question 4"], 
              "sources": []}'''

# 7) MAIN
if __name__ == "__main__":
    print("=== Academic Topic Generator - Proof of Concept ===\n")
    
    batch = generate_daily_batch(k=3)  # Small batch for testing
    
    print("\n" + "="*50)
    print("RESULTS SUMMARY:")
    print("="*50)
    
    # Print compact summaries
    for i, stimulus in enumerate(batch, 1):
        scenario_preview = stimulus.get('scenario', '')[:80] + '...'
        source_count = len(stimulus.get('sources', []))
        print(f"\n{i}. TOPIC: {stimulus['topic']}")
        print(f"   SCENARIO: {scenario_preview}")
        print(f"   SOURCES: {source_count}")
        
        # Show source types
        sources = stimulus.get('sources', [])
        if sources:
            source_types = [s.get('source', 'Unknown') for s in sources]
            print(f"   TYPES: {', '.join(set(source_types))}")
    
    # Print one full stimulus for inspection
    if batch:
        print("\n" + "="*50)
        print("FULL STIMULUS SAMPLE:")
        print("="*50)
        stimulus = batch[0]
        print(f"Topic: {stimulus['topic']}")
        print(f"\nScenario:\n{stimulus['scenario']}")
        print(f"\nPositions:")
        for pos in stimulus.get('positions', []):
            print(f"• {pos}")
        print(f"\nQuestions:")
        for q in stimulus.get('questions', []):
            print(f"• {q}")
        print(f"\nSources ({len(stimulus.get('sources', []))}):")
        for src in stimulus.get('sources', []):
            print(f"• {src.get('source', 'Unknown')}: {src.get('title', 'No title')}")
    
    print("\n=== Proof of Concept Complete ===")