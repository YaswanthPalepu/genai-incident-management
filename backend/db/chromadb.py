import chromadb
from sentence_transformers import SentenceTransformer
from config import CHROMA_PATH, KB_FILE_PATH
import re
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)

def parse_knowledge_base():
    """Parse knowledge base into meaningful chunks"""
    try:
        with open(KB_FILE_PATH, 'r') as f:
            content = f.read()
        
        # Split by KB_ID patterns or major separators
        chunks = []
        current_chunk = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Check for KB_ID pattern or major section starters
            if re.match(r'\[KB_ID:\s*\d+\]', line) or re.match(r'^Use Case:', line, re.IGNORECASE):
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
            elif re.match(r'^-{3,}', line) and i > 0 and i < len(lines) - 1:
                # Check if this is a section separator
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                current_chunk = []
            else:
                current_chunk.append(line)
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return [chunk for chunk in chunks if chunk.strip()]
    except Exception as e:
        logger.error(f"Error parsing knowledge base: {e}")
        return []

def load_and_vectorize_kb():
    """Load and vectorize knowledge base"""
    try:
        client = get_chroma_client()
        collection = client.get_or_create_collection(
            name="knowledge_base",
            metadata={"description": "IT Incident Management Knowledge Base"}
        )
        
        collection.delete(where={})
        
        chunks = parse_knowledge_base()
        
        if not chunks:
            logger.warning("No chunks found in knowledge base")
            return
        
        embeddings = embedding_model.encode(chunks).tolist()
        
        ids = [f"chunk_{i}" for i in range(len(chunks))]
        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings
        )
        
        logger.info(f"Successfully vectorized {len(chunks)} KB chunks")
        
    except Exception as e:
        logger.error(f"Error vectorizing knowledge base: {e}")

def search_kb(query: str, n_results: int = 3):
    """Search knowledge base"""
    try:
        client = get_chroma_client()
        collection = client.get_collection("knowledge_base")
        
        query_embedding = embedding_model.encode([query]).tolist()[0]
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        return list(zip(results['documents'][0], results['distances'][0]))
    except Exception as e:
        logger.error(f"Error searching knowledge base: {e}")
        return []