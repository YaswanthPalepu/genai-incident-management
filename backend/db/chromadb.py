# backend/db/chromadb.py - FIXED VERSION
import chromadb
from sentence_transformers import SentenceTransformer
from config import CHROMA_PATH, KB_FILE_PATH
import re
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)

def get_or_create_collection():
    """Safely get or create collection with proper error handling"""
    client = get_chroma_client()
    try:
        # Try to get existing collection first
        collection = client.get_collection("knowledge_base")
        logger.info("Using existing collection: knowledge_base")
        return collection
    except Exception as e:
        logger.info("Creating new collection: knowledge_base")
        # Create new collection
        collection = client.create_collection(
            name="knowledge_base",
            metadata={"description": "IT Incident Management Knowledge Base"}
        )
        return collection

def parse_knowledge_base():
    """Parse KB file into chunks based on KB_ID"""
    try:
        with open(KB_FILE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        chunks = []
        current_chunk = []
        kb_id = None
        
        lines = content.split('\n')
        
        for line in lines:
            # Check for KB_ID pattern
            kb_id_match = re.search(r'\[KB_ID:\s*(\d+)\]', line)
            
            if kb_id_match:
                # Save previous chunk if exists
                if current_chunk and kb_id:
                    chunk_text = '\n'.join(current_chunk)
                    if chunk_text.strip():
                        chunks.append({
                            'kb_id': kb_id,
                            'content': chunk_text
                        })
                
                # Start new chunk
                kb_id = int(kb_id_match.group(1))
                current_chunk = [line]
            else:
                if kb_id is not None:
                    current_chunk.append(line)
        
        # Add last chunk
        if current_chunk and kb_id:
            chunk_text = '\n'.join(current_chunk)
            if chunk_text.strip():
                chunks.append({
                    'kb_id': kb_id,
                    'content': chunk_text
                })
        
        logger.info(f"Parsed {len(chunks)} KB chunks")
        return chunks
    except Exception as e:
        logger.error(f"Error parsing knowledge base: {e}")
        return []

def load_and_vectorize_kb():
    """Load and vectorize KB chunks"""
    try:
        collection = get_or_create_collection()
        
        # Clear existing data safely
        try:
            # Get all existing documents first
            existing_data = collection.get()
            if existing_data['ids']:
                collection.delete(ids=existing_data['ids'])
                logger.info(f"Cleared {len(existing_data['ids'])} existing documents")
        except Exception as e:
            logger.warning(f"Could not clear existing data: {e}")
        
        chunks = parse_knowledge_base()
        
        if not chunks:
            logger.warning("No chunks found in knowledge base")
            return
        
        # Prepare data for batch insertion
        documents = []
        metadatas = []
        ids = []
        embeddings = []
        
        for chunk in chunks:
            kb_id = chunk['kb_id']
            content = chunk['content']
            
            # Create embedding
            embedding = embedding_model.encode(content).tolist()
            
            documents.append(content)
            metadatas.append({"kb_id": kb_id})
            ids.append(f"kb_{kb_id}")
            embeddings.append(embedding)
        
        # Batch insert all documents
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )
        
        logger.info(f"Successfully vectorized {len(chunks)} KB chunks")
        
    except Exception as e:
        logger.error(f"Error vectorizing knowledge base: {e}")
        raise

def hybrid_search_kb(query: str, n_results: int = 3):
    """
    Hybrid search: Combines semantic and keyword search with fixed weights
    """
    # Fixed weights - you can adjust these internally
    semantic_weight = 0.7
    keyword_weight = 0.3
    
    try:
        collection = get_or_create_collection()
        
        # Get semantic results
        query_embedding = embedding_model.encode(query).tolist()
        semantic_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results * 2,  # Get more for re-ranking
            include=["documents", "distances", "metadatas"]
        )
        
        hybrid_results = []
        
        if semantic_results['documents'] and semantic_results['documents'][0]:
            for i, doc in enumerate(semantic_results['documents'][0]):
                distance = semantic_results['distances'][0][i]
                metadata = semantic_results['metadatas'][0][i]
                
                # Semantic score
                semantic_score = 1 - (distance / 2) if distance <= 2 else 0
                
                # Keyword score
                keyword_score = simple_keyword_match(query, doc)
                
                # Combined score
                hybrid_score = (semantic_weight * semantic_score + 
                              keyword_weight * keyword_score)
                
                hybrid_results.append({
                    'kb_id': metadata['kb_id'],
                    'content': doc,
                    'similarity': hybrid_score,  # Keep 'similarity' for compatibility
                    'semantic_score': semantic_score,
                    'keyword_score': keyword_score,
                    'distance': distance
                })
        
        # Sort by hybrid score and return top results
        hybrid_results.sort(key=lambda x: x['similarity'], reverse=True)
        final_results = hybrid_results[:n_results]
        
        logger.info(f"Hybrid search for '{query}' returned {len(final_results)} results")
        return final_results

    except Exception as e:
        logger.error(f"Error in hybrid search: {e}")
        return []

def simple_keyword_match(query: str, document: str) -> float:
    """Simple keyword matching score"""
    query_terms = [term.lower() for term in query.split() if len(term) > 2]
    doc_lower = document.lower()
    
    if not query_terms:
        return 0.0
    
    matches = sum(1 for term in query_terms if term in doc_lower)
    return matches / len(query_terms)

def get_kb_chunk_by_id(kb_id: int):
    """Get specific KB chunk by ID"""
    try:
        collection = get_or_create_collection()
        
        result = collection.get(ids=[f"kb_{kb_id}"])
        
        if result['documents']:
            return {
                'kb_id': kb_id,
                'content': result['documents'][0]
            }
        return None
    except Exception as e:
        logger.error(f"Error getting KB chunk: {e}")
        return None

def clear_knowledge_base():
    """Clear the entire knowledge base"""
    try:
        client = get_chroma_client()
        client.delete_collection("knowledge_base")
        logger.info("Knowledge base cleared successfully")
        return True
    except Exception as e:
        logger.error(f"Error clearing knowledge base: {e}")
        return False