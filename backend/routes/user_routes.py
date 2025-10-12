from fastapi import APIRouter, HTTPException
from models import UserQuery, SessionEndRequest
from services.llm_service import (
    analyze_query_and_route,
    handle_direct_response,
    handle_kb_search_and_incident,
    get_session_incident_id,
    get_session_status,
    clear_session_data
)
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/chat")
async def chat_with_ai(user_query: UserQuery):
    session_id = user_query.session_id or str(uuid.uuid4())
    query = user_query.query.strip()
    
    logger.info(f"New message - Session: {session_id}, Query: {query[:50]}...")
    
    try:
        # Step 1: Intelligent query analysis by LLM
        analysis = await analyze_query_and_route(query, session_id)
        action = analysis.get('action', 'KB_SEARCH')
        
        logger.info(f"LLM Analysis - Action: {action}, IT Related: {analysis.get('is_it_related')}")
        
        # Step 2: Route based on LLM analysis
        if action == "DIRECT_RESPONSE":
            # LLM handles greetings, farewells, irrelevant topics directly
            response_text = await handle_direct_response(query, session_id, analysis)
            incident_id = None
            status = "No Incident"
            
        else:
            # Handle IT incidents with KB search and incident management
            response_text, incident_id, status, kb_chunk = await handle_kb_search_and_incident(
                query, session_id
            )
        
        # Step 3: Format final response
        final_response = response_text
        
        # Add incident info if exists
        if incident_id:
            final_response += f"\n\n🆔 **Incident ID:** {incident_id}\n📊 **Status:** {status}"
        
        return {
            "success": True,
            "session_id": session_id,
            "incident_id": incident_id,
            "response": final_response,
            "status": status
        }
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return {
            "success": False,
            "session_id": session_id,
            "incident_id": None,
            "response": "I encountered an error. Please try again.",
            "status": "Error"
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