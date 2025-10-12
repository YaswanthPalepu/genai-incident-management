from db.chromadb import load_and_vectorize_kb
from config import KB_FILE_PATH
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_knowledge_base_file(new_kb_content: str):
    """Updates the knowledge_base.txt file and re-vectorizes it."""
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(KB_FILE_PATH), exist_ok=True)
        
        with open(KB_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(new_kb_content)
        
        # Re-load and re-vectorize after update
        load_and_vectorize_kb()
        logger.info("Knowledge base file updated and re-vectorized successfully.")
        return True
    except Exception as e:
        logger.error(f"Error updating knowledge base file: {e}")
        return False

def get_knowledge_base_content():
    """Reads and returns the current content of the knowledge_base.txt file."""
    try:
        if not os.path.exists(KB_FILE_PATH):
            logger.warning(f"Knowledge base file not found at {KB_FILE_PATH}")
            return "Knowledge base file not found. Please upload a knowledge base file."
        
        with open(KB_FILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            logger.info(f"Successfully read knowledge base file ({len(content)} characters)")
            return content
    except FileNotFoundError:
        logger.error(f"Knowledge base file not found: {KB_FILE_PATH}")
        return "Knowledge base file not found."
    except Exception as e:
        logger.error(f"Error reading knowledge base file: {e}")
        return "Error reading knowledge base content."

def validate_kb_content(kb_content: str) -> bool:
    """Validate knowledge base content format"""
    if not kb_content or not kb_content.strip():
        return False
    
    # Basic validation - check if content has some structure
    lines = kb_content.strip().split('\n')
    non_empty_lines = [line for line in lines if line.strip()]
    
    if len(non_empty_lines) < 3:
        logger.warning("Knowledge base content seems too short")
        return False
    
    # Check for common KB patterns
    has_kb_patterns = any(
        pattern in kb_content.upper() 
        for pattern in ['KB_ID', 'USE CASE', 'SOLUTION', 'REQUIRED INFO']
    )
    
    if not has_kb_patterns:
        logger.warning("Knowledge base content doesn't contain common patterns")
    
    return True