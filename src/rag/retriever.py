import os
import logging

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'knowledge'))

def get_sop_content(sop_name: str) -> str:
    """
    Retrieves the content of a specific SOP markdown file.
    For this hackathon prototype, a simple file read is sufficient instead of a full vector DB.
    """
    filepath = os.path.join(KNOWLEDGE_DIR, f"{sop_name}.md")
    
    if not os.path.exists(filepath):
        logger.error(f"SOP file not found: {filepath}")
        return "SOP not available."
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading SOP {sop_name}: {e}")
        return f"Error reading SOP: {e}"
