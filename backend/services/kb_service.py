# backend/services/kb_service.py - REFACTORED
from db.chromadb import load_and_vectorize_kb
from config import KB_FILE_PATH
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_knowledge_base_file(new_kb_content: str) -> bool:
    """
    Update knowledge base file and re-vectorize
    """
    try:
        # Validate content
        if not validate_kb_content(new_kb_content):
            logger.warning("KB content validation failed")
            return False
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(KB_FILE_PATH) or '.', exist_ok=True)
        
        # Write to file
        with open(KB_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(new_kb_content)
        
        logger.info(f"KB file updated: {len(new_kb_content)} characters")
        
        # Re-vectorize
        load_and_vectorize_kb()
        logger.info("KB re-vectorized successfully")
        
        return True
    
    except Exception as e:
        logger.error(f"Error updating KB file: {e}")
        return False

def get_knowledge_base_content() -> str:
    """
    Read and return KB file content
    """
    try:
        if not os.path.exists(KB_FILE_PATH):
            logger.warning(f"KB file not found: {KB_FILE_PATH}")
            return ""
        
        with open(KB_FILE_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            logger.info(f"Read KB file: {len(content)} characters")
            return content
    
    except Exception as e:
        logger.error(f"Error reading KB file: {e}")
        return ""

def validate_kb_content(kb_content: str) -> bool:
    """
    Validate KB content structure
    Must have at least one KB_ID entry
    """
    try:
        if not kb_content or not kb_content.strip():
            logger.warning("KB content is empty")
            return False
        
        lines = kb_content.strip().split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if len(non_empty_lines) < 3:
            logger.warning("KB content too short")
            return False
        
        # Check for KB_ID pattern
        has_kb_id = any('[KB_ID:' in line for line in lines)
        
        if not has_kb_id:
            logger.warning("KB content missing [KB_ID:] pattern")
            return False
        
        logger.info("KB content validation passed")
        return True
    
    except Exception as e:
        logger.error(f"Error validating KB: {e}")
        return False
