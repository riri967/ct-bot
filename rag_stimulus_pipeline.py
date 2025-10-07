"""
Compact RAG Pipeline with Stimulus Generation
A retrieval-augmented generation system that pulls from multiple sources
to create critical thinking scenarios for educational purposes.
"""

import requests
import json
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
import urllib.parse

# API keys handled by api_utils.py

@dataclass
class Doc:
    """Document container for retrieved content"""
    text: str
    title: str
    url: str
    source: str
    published: Optional[str] = None

class BaseRetriever:
    """Base class for API retrievers"""
    def __init__(self, source_name: str):
        self.source_name = source_name
    
    def retrieve(self, query: str, limit: int = 5) -> List[Doc]:
        try:
            return self._fetch_docs(query, limit)
        except Exception as e:
            print(f"{self.source_name} retrieval error: {e}")
            return self._fallback_docs(query)
    
    def _fetch_docs(self, query: str, limit: int) -> List[Doc]:
        raise NotImplementedError
    
    def _fallback_docs(self, query: str) -> List[Doc]:
        raise NotImplementedError

class OpenAlexRetriever(BaseRetriever):
    """Retrieve scholarly papers from OpenAlex API (free, no authentication required)"""
    
    def __init__(self):
        super().__init__("OpenAlex")
        self.base_url = "https://api.openalex.org/works"
    
    def _fetch_docs(self, query: str, limit: int = 5) -> List[Doc]:
        """Fetch real academic papers from OpenAlex API"""
        params = {
            'search': query, 'per_page': min(limit, 25),
            'sort': 'cited_by_count:desc', 'filter': 'is_oa:true'
        }
        
        response = requests.get(self.base_url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        docs = []
        for work in data.get('results', []):
            abstract = work.get('abstract_inverted_index')
            if abstract:
                words = [''] * max(max(positions) for positions in abstract.values()) if abstract else []
                for word, positions in abstract.items():
                    for pos in positions:
                        if pos < len(words):
                            words[pos] = word
                text = ' '.join(words).strip()[:1000]
            else:
                text = work.get('title', '')[:1000]
            
            if text.strip():
                docs.append(Doc(
                    text=text, title=work.get('title', 'Untitled Research Paper'),
                    url=work.get('doi') or work.get('id', ''), source='OpenAlex',
                    published=work.get('publication_date')
                ))
                if len(docs) >= limit:
                    break
        
        return docs
    
    def _fallback_docs(self, query: str) -> List[Doc]:
        """Fallback academic content when API fails"""
        return [Doc(
            text=f"Recent academic research on {query} examines multiple perspectives and methodological approaches to understanding this complex topic.",
            title=f"Academic Research: {query}",
            url="https://openalex.org",
            source="OpenAlex",
            published="2024-01-01"
        )]

class WikipediaRetriever:
    """Retrieve content from Wikipedia MediaWiki API"""
    
    def __init__(self):
        self.base_url = "https://en.wikipedia.org/api/rest_v1/page/summary/"
        self.search_url = "https://en.wikipedia.org/w/api.php"
        self.headers = {
            'User-Agent': 'RAG-Educational-System/1.0 (https://example.com/contact; research@example.com)',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate'
        }
    
    def retrieve(self, query: str, limit: int = 3) -> List[Doc]:
        """Fetch Wikipedia articles related to query"""
        try:
            # First, search for relevant pages
            search_params = {
                'action': 'query',
                'format': 'json',
                'list': 'search',
                'srsearch': query,
                'srlimit': limit
            }
            
            import time
            time.sleep(1)  # Rate limiting delay
            
            search_response = requests.get(self.search_url, params=search_params, headers=self.headers, timeout=15)
            
            if search_response.status_code == 403:
                print("Wikipedia API access forbidden (403) - likely IP blocked")
                return self._fallback_docs(query)
            
            search_response.raise_for_status()
            search_data = search_response.json()
            
            docs = []
            for page in search_data.get('query', {}).get('search', []):
                title = page['title']
                
                # Get page summary with rate limiting
                time.sleep(0.5)  # Additional delay between requests
                summary_response = requests.get(f"{self.base_url}{title}", headers=self.headers, timeout=15)
                
                if summary_response.status_code == 403:
                    continue  # Skip this page if blocked
                elif summary_response.status_code == 200:
                    summary_data = summary_response.json()
                    
                    doc = Doc(
                        text=summary_data.get('extract', '')[:1000],
                        title=title,
                        url=summary_data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                        source='Wikipedia',
                        published=summary_data.get('timestamp')
                    )
                    docs.append(doc)
            
            return docs
            
        except Exception as e:
            print(f"Wikipedia retrieval error: {e}")
            return self._fallback_docs(query)
    
    def _fallback_docs(self, query: str) -> List[Doc]:
        """Enhanced fallback Wikipedia content when API is blocked"""
        # Provide more substantial fallback content based on common topics
        fallback_content = {
            'surveillance': "Surveillance technology involves systematic observation for security, law enforcement, or monitoring purposes. Modern systems include CCTV networks, facial recognition, and digital tracking. Key ethical concerns include privacy rights, data protection, proportionality of monitoring, and potential for misuse or discriminatory targeting.",
            'privacy': "Privacy rights encompass individuals' control over personal information and freedom from unwanted observation. Digital privacy involves data protection, consent mechanisms, and transparency in data collection. Balancing privacy with security, public safety, and technological advancement remains a key policy challenge.",
            'algorithm': "Algorithmic systems use computational methods to process data and make decisions. Applications include recommendation systems, automated hiring, credit scoring, and predictive policing. Key concerns include bias, transparency, accountability, and fairness in automated decision-making processes.",
            'monitoring': "Monitoring systems track behaviour, performance, or compliance across various contexts including workplace, education, and public spaces. Technologies include activity tracking, performance analytics, and behavioural analysis. Ethical considerations include consent, proportionality, and impact on human autonomy.",
            'technology': "Technology implementation in public and private sectors involves adopting new systems for efficiency, security, or service delivery. Considerations include cost-benefit analysis, stakeholder impact, privacy implications, and long-term societal effects of technological change."
        }
        
        # Find most relevant fallback content
        content = fallback_content.get('technology')  # default
        for key, text in fallback_content.items():
            if key in query.lower():
                content = text
                break
        
        return [Doc(
            text=content,
            title=f"Background: {query.title()}",
            url="https://wikipedia.org",
            source="Wikipedia"
        )]

class GDELTRetriever:
    """Retrieve real news data from GDELT Project API (free, no authentication required)"""
    
    def __init__(self):
        self.base_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    
    def retrieve(self, query: str, limit: int = 5) -> List[Doc]:
        """Fetch real news articles from GDELT API"""
        try:
            params = {
                'query': query,
                'mode': 'artlist',
                'maxrecords': min(limit, 250),  # GDELT limit
                'format': 'json',
                'sort': 'hybridrel'  # Most relevant articles
            }
            
            response = requests.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            docs = []
            articles = data.get('articles', [])
            
            for article in articles[:limit]:
                title = article.get('title', '')
                url = article.get('url', '')
                domain = article.get('domain', '')
                date = article.get('seendate', datetime.now().strftime('%Y%m%dT%H%M%SZ'))
                
                # Use title as text content (GDELT doesn't provide full text)
                text = title[:1000] if title else f"News article about {query}"
                
                if not text.strip():
                    continue
                
                doc = Doc(
                    text=text,
                    title=title or f"News: {query}",
                    url=url,
                    source='GDELT',
                    published=date
                )
                docs.append(doc)
            
            return docs if docs else self._fallback_docs(query)
            
        except Exception as e:
            print(f"GDELT API error: {e}")
            return self._fallback_docs(query)
    
    def _fallback_docs(self, query: str) -> List[Doc]:
        """Fallback news content when API fails"""
        return [Doc(
            text=f"Recent news coverage of {query} includes various perspectives from different stakeholders and ongoing developments in the field.",
            title=f"News: {query}",
            url="https://gdeltproject.org",
            source="GDELT",
            published=datetime.now().isoformat()
        )]

class GovUKRetriever:
    """Retrieve content from GOV.UK Content API"""
    
    def __init__(self):
        self.base_url = "https://www.gov.uk/api/search.json"
    
    def retrieve(self, query: str, limit: int = 3) -> List[Doc]:
        """Fetch UK government content related to query"""
        try:
            params = {
                'q': query,
                'count': limit,
                'order': '-public_timestamp'
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            docs = []
            for result in data.get('results', []):
                doc = Doc(
                    text=(result.get('description', '') or result.get('title', ''))[:1000],
                    title=result.get('title', 'Untitled'),
                    url=f"https://www.gov.uk{result.get('link', '')}",
                    source='GOV.UK',
                    published=result.get('public_timestamp')
                )
                docs.append(doc)
            
            return docs
            
        except Exception as e:
            print(f"GOV.UK retrieval error: {e}")
            return self._fallback_docs(query)
    
    def _fallback_docs(self, query: str) -> List[Doc]:
        """Fallback government content"""
        return [Doc(
            text=f"UK government policy on {query} involves multiple departments and stakeholders with various regulatory and implementation considerations.",
            title=f"GOV.UK: {query}",
            url="https://gov.uk",
            source="GOV.UK"
        )]

class DocumentRetriever:
    """Router that calls all retrievers and merges results"""
    
    def __init__(self):
        self.retrievers = {
            'openalex': OpenAlexRetriever(),
            'wikipedia': WikipediaRetriever(),
            'gdelt': GDELTRetriever(),
            'govuk': GovUKRetriever()
        }
    
    def retrieve(self, query: str) -> List[Doc]:
        """Retrieve documents from all sources"""
        all_docs = []
        
        for name, retriever in self.retrievers.items():
            try:
                docs = retriever.retrieve(query)
                all_docs.extend(docs)
                print(f"Retrieved {len(docs)} documents from {name}")
            except Exception as e:
                print(f"{name} retrieval failed: {e}")
        
        return all_docs

class RAGVectorStore:
    """Chroma-based vector store for document embeddings with cloud compatibility"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.initialized = False
        
        try:
            # Try cloud-compatible ChromaDB initialization
            import tempfile
            import os
            
            # Use temporary directory for cloud deployment
            temp_dir = tempfile.mkdtemp(prefix='chromadb_')
            
            self.client = chromadb.PersistentClient(path=temp_dir)
            self.collection = self.client.get_or_create_collection(
                name="rag_documents",
                metadata={"hnsw:space": "cosine"}
            )
            self.initialized = True
            print(f"ChromaDB initialized successfully with temp directory: {temp_dir}")
            
        except Exception as e:
            print(f"ChromaDB initialization failed: {e}")
            print("RAG will use fallback mode without vector search")
            self.initialized = False
    
    def _get_embedding(self, text: str) -> List[float]:
        """Placeholder embedding function - TODO: Integrate OpenAI embeddings"""
        # Simple hash-based embedding for demo (replace with actual embeddings)
        import hashlib
        hash_obj = hashlib.md5(text.encode())
        hash_hex = hash_obj.hexdigest()
        # Convert to 384-dimensional vector (ChromaDB default)
        embedding = [float(int(hash_hex[i:i+2], 16)) / 255.0 for i in range(0, min(len(hash_hex), 96), 2)]
        # Pad to 384 dimensions
        embedding.extend([0.0] * (384 - len(embedding)))
        return embedding[:384]
    
    def index_docs(self, docs: List[Doc]) -> None:
        """Embed and store documents in vector database"""
        if not docs or not self.initialized:
            if not self.initialized:
                print("Vector store not initialized - skipping document indexing")
            return
        
        documents = []
        metadatas = []
        ids = []
        embeddings = []
        
        for i, doc in enumerate(docs):
            if doc.text.strip():  # Only index documents with content
                documents.append(doc.text)
                metadatas.append({
                    'title': doc.title,
                    'url': doc.url,
                    'source': doc.source,
                    'published': doc.published or ''
                })
                ids.append(f"doc_{i}_{hash(doc.text)}")
                embeddings.append(self._get_embedding(doc.text))
        
        if documents:
            try:
                self.collection.add(
                    documents=documents,
                    metadatas=metadatas,
                    ids=ids,
                    embeddings=embeddings
                )
                print(f"Indexed {len(documents)} documents")
            except Exception as e:
                print(f"Document indexing failed: {e}")
                self.initialized = False
    
    def query(self, question: str, top_k: int = 5) -> List[Dict]:
        """Query vector store for relevant documents"""
        if not self.initialized:
            print("Vector store not initialized - returning empty results")
            return []
            
        try:
            results = self.collection.query(
                query_embeddings=[self._get_embedding(question)],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            
            relevant_docs = []
            if results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    relevant_docs.append({
                        'text': doc,
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else 0.0
                    })
            
            return relevant_docs
            
        except Exception as e:
            print(f"Query error: {e}")
            return []

class RAGSystem:
    """Complete RAG system combining retrieval and generation with cloud fallbacks"""
    
    def __init__(self):
        self.retriever = DocumentRetriever()
        self.vectorstore = RAGVectorStore()
        self.rag_operational = self.vectorstore.initialized
        
        # Use dedicated API key for stimulus generation
        try:
            from api_utils import get_model_with_retry
            self.model = get_model_with_retry(
                model_name="gemini-2.0-flash",
                purpose='stimulus_generation',
                temperature=0.7,
                top_p=0.9,
                top_k=50,
                max_output_tokens=2048
            )
            print(f"RAG system initialized - Vector store operational: {self.rag_operational}")
        except Exception as e:
            print(f"RAG model initialization failed: {e}")
            self.model = None
            self.rag_operational = False
    
    def query_rag(self, question: str) -> List[Dict]:
        """Main RAG query function: retrieve, index, and return relevant documents"""
        print(f"Processing RAG query: {question} (operational: {self.rag_operational})")
        
        # Retrieve documents from external sources
        docs = self.retriever.retrieve(question)
        print(f"Retrieved {len(docs)} documents from external APIs")
        
        if not self.rag_operational:
            # Return documents without vector search when ChromaDB unavailable
            if docs:
                return [{
                    'text': doc.text,
                    'metadata': {
                        'title': doc.title,
                        'url': doc.url,
                        'source': doc.source,
                        'published': doc.published or ''
                    }
                } for doc in docs[:5]]  # Return top 5 docs
            else:
                print("No external docs retrieved and vector store unavailable - using fallback")
                return self._get_fallback_docs(question)
        
        # Normal RAG pipeline when vector store is operational
        self.vectorstore.index_docs(docs)
        relevant_docs = self.vectorstore.query(question, top_k=5)
        
        return relevant_docs if relevant_docs else self._get_fallback_docs(question)
    
    def _get_fallback_docs(self, question: str) -> List[Dict]:
        """Provide fallback documents when RAG system fails"""
        return [{
            'text': f"This scenario explores the complex considerations around {question}, involving multiple stakeholders with different priorities and evidence-based positions that warrant careful critical analysis.",
            'metadata': {
                'title': f"Critical Thinking Scenario: {question}",
                'url': 'fallback://scenario',
                'source': 'Educational Content',
                'published': '2024-01-01'
            }
        }]
    
    def generate_answer(self, question: str, context_docs: List[Dict]) -> str:
        """Generate answer using LLM with retrieved context"""
        if not context_docs:
            context = "No relevant documents found."
        else:
            context_parts = []
            for i, doc in enumerate(context_docs):
                source = doc.get('metadata', {}).get('source', 'Unknown')
                title = doc.get('metadata', {}).get('title', 'Untitled')
                text = doc.get('text', '')[:500]  # Truncate for context window
                context_parts.append(f"[{i+1}] {source} - {title}: {text}")
            
            context = "\n\n".join(context_parts)
        
        prompt = f"""Based on the following context, provide a comprehensive answer to the question.
Include citations to the sources where relevant.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""
        
        try:
            from api_utils import generate_with_retry
            response_text = generate_with_retry(self.model, prompt)
            return response_text
        except Exception as e:
            return f"Error generating response: {e}"

def generate_stimulus(topic: str, rag_system: RAGSystem) -> str:
    """Generate concrete situational stimulus based on topic using RAG with fallbacks"""
    print(f"Generating situation-based stimulus for: {topic} (RAG operational: {rag_system.rag_operational})")
    
    # Try to retrieve contextual information
    context_docs = rag_system.query_rag(topic) if rag_system else []
    
    # Build context for stimulus generation
    context_summary = []
    real_world_context = False
    
    if context_docs:
        for doc in context_docs[:3]:  # Use top 3 most relevant
            source = doc.get('metadata', {}).get('source', 'Source')
            text = doc.get('text', '')[:150]
            if source not in ['Educational Content', 'fallback']:
                real_world_context = True
            context_summary.append(f"{source}: {text}")
    
    context_text = "\n".join(context_summary) if context_summary else f"Exploring real-world considerations around {topic}"
    
    print(f"Using {'real-world' if real_world_context else 'fallback'} context for stimulus generation")
    
    # Create more focused context to avoid nonsensical combinations
    focused_context = ""
    if context_docs and real_world_context:
        # Filter context for relevance to main topic
        relevant_parts = []
        topic_keywords = topic.lower().split()
        
        for doc in context_docs[:2]:  # Use only top 2 most relevant
            source = doc.get('metadata', {}).get('source', 'Source')
            text = doc.get('text', '')[:200]  
            
            # Check if document is actually relevant to main topic
            relevance_score = sum(1 for keyword in topic_keywords if keyword in text.lower())
            if relevance_score > 0 or source in ['OpenAlex', 'GOV.UK']:  # Prioritize academic/policy sources
                relevant_parts.append(f"{source}: {text}")
        
        focused_context = "\n".join(relevant_parts) if relevant_parts else f"Contemporary {topic} considerations"
    else:
        focused_context = f"Current policy and ethical considerations around {topic}"

    stimulus_prompt = f"""Write a realistic policy/ethical scenario about {topic}.

CONTEXT: {focused_context}

Create a coherent scenario (180-220 words) featuring:
- One specific organization making a decision about {topic}
- Clear stakeholders with different positions 
- Realistic details (costs, timeframes, names)
- A focused ethical/policy dilemma

Requirements:
- Stay focused on the main topic: {topic}
- Write like a news report - factual and neutral
- No commentary or questions
- Start directly with the scenario"""
    
    # Check if RAG model is available
    if not rag_system or not rag_system.model:
        print("RAG model unavailable - using hardcoded fallback scenario")
        return _get_fallback_scenario(topic)
    
    try:
        from api_utils import generate_with_retry
        response_text = generate_with_retry(rag_system.model, stimulus_prompt)
        # Clean up any unwanted prefixes
        response_text = response_text.strip()
        if response_text.upper().startswith('SCENARIO:'):
            response_text = response_text[9:].strip()
        # Remove common AI meta-commentary
        if response_text.lower().startswith(("here's", "okay", "here is")):
            lines = response_text.split('\n')
            if len(lines) > 1:
                response_text = '\n'.join(lines[1:]).strip()
        
        print(f"Generated stimulus successfully ({'with' if real_world_context else 'without'} real-world context)")
        return response_text
        
    except Exception as e:
        print(f"Stimulus generation failed: {e} - using fallback scenario")
        return _get_fallback_scenario(topic)

def _get_fallback_scenario(topic: str) -> str:
    """Provide hardcoded fallback scenario when all systems fail"""
    concept = topic.split()[0] if topic else "technology"
    return f"""The Smart City Surveillance Dilemma

GreenVale City Council has approved a £15 million smart city project that would install 2,000 AI-powered cameras throughout the town. The system, developed by SecureWatch Technologies, promises to reduce crime by 40% through facial recognition and behaviour analysis.

Councillor Sarah Martinez argues the technology will make streets safer for families and help police respond faster to incidents. The cameras can detect fights, identify wanted criminals, and even spot people in distress. "We have a duty to protect our residents," she says, pointing to recent muggings in the town centre.

However, local privacy group Citizens for Digital Rights calls it "mass surveillance dressed up as safety." They worry the system will track innocent people's daily movements and could discriminate against minorities. Shop owner David Chen supports the cameras but questions the £300,000 annual operating costs when the town library faces closure due to budget cuts.

The technology company insists their AI is unbiased and data will be anonymised after 30 days, but critics note the firm was recently fined for data breaches in two other cities. Meanwhile, residents are split - older residents generally support enhanced security, while younger people worry about privacy erosion."""

def generate_stimulus_with_question(topic: str, rag_system: RAGSystem) -> str:
    """Generate stimulus with AI-generated initial Socratic question for chatbot initialization"""
    # Get the stimulus scenario
    stimulus = generate_stimulus(topic, rag_system)
    
    # Generate relevant Socratic question using Gemini API
    question_prompt = f"""Write one Socratic question about this scenario:

{stimulus}

Write only a single question sentence that encourages critical thinking about assumptions, reasoning, or trade-offs. No extra text."""
    
    try:
        # Use dedicated API key for question generation
        from api_utils import get_model_with_retry, generate_with_retry
        question_model = get_model_with_retry(
            model_name="gemini-2.0-flash",
            purpose='question_generation',
            temperature=0.4,
            top_p=0.9,
            top_k=50,
            max_output_tokens=2048
        )
        question = generate_with_retry(question_model, question_prompt).strip()
        
        # Clean up any unwanted text from the question
        question = question.replace("Question:", "").replace("QUESTION:", "").strip()
        if question.startswith('"') and question.endswith('"'):
            question = question[1:-1].strip()
        
        return f"{stimulus}\n\n{question}"
    except Exception as e:
        # Fallback question if generation fails
        return f"{stimulus}\n\nWhat assumptions might be driving the different positions you see here?"

def run_pipeline(user_input: str) -> Dict:
    """Complete pipeline: retrieve context and generate stimulus"""
    rag_system = RAGSystem()
    
    # Get RAG context
    context_docs = rag_system.query_rag(user_input)
    
    # Generate stimulus
    stimulus = generate_stimulus(user_input, rag_system)
    
    return {
        'context': context_docs,
        'stimulus': stimulus,
        'topic': user_input
    }

if __name__ == "__main__":
    print("Starting RAG Stimulus Pipeline Demo\n")
    
    # Sample queries
    test_queries = [
        "climate policy UK",
        "gene editing ethics"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"QUERY: {query}")
        print('='*60)
        
        try:
            result = run_pipeline(query)
            
            print(f"\nCONTEXT ({len(result['context'])} documents):")
            for i, doc in enumerate(result['context'][:2]):  # Show first 2
                source = doc.get('metadata', {}).get('source', 'Unknown')
                title = doc.get('metadata', {}).get('title', 'Untitled')
                print(f"  {i+1}. [{source}] {title}")
            
            print(f"\nGENERATED STIMULUS:")
            print(result['stimulus'])
            
        except Exception as e:
            print(f"Pipeline error: {e}")
        
        print(f"\n{'-'*60}")
    
    print("\nRAG Pipeline Demo Complete")
    print("\nTODO: Replace API key placeholders with actual credentials")
    print("TODO: Integrate OpenAI embeddings for better semantic search")
    print("TODO: Add error handling and retry logic for external APIs")