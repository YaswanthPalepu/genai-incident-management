from fastapi import APIRouter, HTTPException
from models import UserQuery, SessionEndRequest
from services.llm_service import (
    handle_user_query,
    get_session_incident_id,
    get_session_status,
    clear_session_data
)
import logging
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/chat")
async def chat_with_ai(user_query: UserQuery):
    """
    Main chat endpoint using pure LLM intelligence
    """
    session_id = user_query.session_id or str(uuid.uuid4())
    query = user_query.query.strip()
    
    logger.info(f"Chat request - Session: {session_id}, Query: {query}")
    
    try:
        # Single intelligent function handles everything using LLM
        response, incident_id, status, status_changed = await handle_user_query(query, session_id)
        
        # **FIXED: Only include incident info when it's newly created or status changes**
        # Get previous status to detect changes
        #previous_status = get_session_status(session_id)
        
        # Format final response - only show incident info when relevant
        final_response = response
        show_incident_info = (  
            incident_id and 
            (status_changed or "created" in response.lower() or "incident" in response.lower())
        )
        
        if show_incident_info:
            final_response = f"{response}\n\n🆔 **Incident ID:** {incident_id}\n📊 **Status:** {status}"
        
        return {
            "success": True,
            "session_id": session_id,
            "incident_id": incident_id,
            "response": final_response,
            "status": status,
            "show_incident_info": show_incident_info  # Frontend can use this to show/hide incident bar
        }
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return {
            "success": False,
            "session_id": session_id,
            "incident_id": None,
            "response": "I encountered an error. Please try again.",
            "status": "Error",
            "show_incident_info": False
        }

@router.post("/end_session")
async def end_session(session_data: SessionEndRequest):
    """End session and cleanup"""
    session_id = session_data.session_id
    
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID required")
    
    logger.info(f"Ending session: {session_id}")
    
    # Get final incident status before clearing
    incident_id = get_session_incident_id(session_id)
    status = get_session_status(session_id)
    
    await clear_session_data(session_id)
    
    return {
        "success": True,
        "message": "Session ended successfully",
        "session_id": session_id,
        "final_incident_id": incident_id,
        "final_status": status
    }

@router.get("/session_status/{session_id}")
async def get_session_status(session_id: str):
    """Get current session status"""
    incident_id = get_session_incident_id(session_id)
    status = get_session_status(session_id)
    
    return {
        "success": True,
        "session_id": session_id,
        "incident_id": incident_id,
        "status": status
    }