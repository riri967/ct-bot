"""Academic Topic Generator for Critical Thinking Stimuli"""

import re
import random
from typing import List
from rag_stimulus_pipeline import DocumentRetriever

BASE_CONCEPTS = []

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
    docs = retriever.retrieve("critical thinking ethics policy education technology environment health justice privacy AI")
    
    concepts = set()
    for doc in docs:
        phrases = re.findall(r'\b(?:[A-Z][a-z]*(?:\s+[A-Z][a-z]*){0,2}|[a-z]+(?:ing|tion|ity|ics|ism))\b', doc.title.lower())
        for phrase in phrases:
            clean = re.sub(r'[^\w\s]', '', phrase.strip().lower())
            if 3 <= len(clean) <= 25 and clean not in ['the', 'and', 'for', 'with']:
                concepts.add(clean)
    
    return sorted(list(concepts))[:20] if concepts else ['ethics', 'policy', 'technology', 'justice', 'privacy']

def make_topics(concepts: List[str], situations: List[str], limit: int = 60) -> List[str]:
    """Generate specific situational topics"""
    topics = situations.copy()
    for concept in concepts[:3]:
        for situation in situations[:5]:
            if concept.lower() not in situation.lower():
                topics.append(f"{situation} involving {concept}")
    return list(dict.fromkeys(topics))[:limit]

def simple_select(topics: List[str], k: int = 8) -> List[str]:
    """Simple selection - just take first k topics"""
    return topics[:k]