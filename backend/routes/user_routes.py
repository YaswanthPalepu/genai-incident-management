from fastapi import APIRouter, HTTPException
from models import UserQuery, Incident, Message
from db.mongodb import create_incident, get_incident, update_incident
from db.chromadb import search_kb
from services.llm_service import get_llm_response, get_session_history, clear_session_history, get_incident_context, set_active_incident, get_active_incident, clear_active_incident
from datetime import datetime
import uuid
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/chat")
async def chat_with_ai(user_query: UserQuery):
    session_id = user_query.session_id or str(uuid.uuid4())
    query = user_query.query.strip()
    
    logger.info(f"Processing query for session {session_id}: {query}")

    # Get current active incident for this session
    current_incident_id = get_active_incident(session_id)
    incident_data = None
    is_new_incident = False
    kb_chunks = []

    # Search KB ONLY when no active incident exists (first message)
    if not current_incident_id:
        kb_results = search_kb(query, n_results=3)
        kb_chunks = [doc for doc, score in kb_results if score < 0.8]
        logger.info(f"KB search found {len(kb_chunks)} chunks for query: {query}")

        # Create incident for IT-related queries (when KB found OR query seems IT-related)
        if kb_chunks or _is_it_related_query(query):
            current_incident_id = f"INC{datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4].upper()}"
            set_active_incident(session_id, current_incident_id)
            is_new_incident = True
            
            # Determine initial status based on KB availability
            initial_status = "Pending Information" if kb_chunks else "Pending Admin Review"
            kb_reference = "KB_MATCH_FOUND" if kb_chunks else "NO_KB_MATCH"
            
            # Create new incident
            new_incident = Incident(
                incident_id=current_incident_id,
                user_demand=query,
                status=initial_status,
                additional_info=[Message(sender="User", text=query).dict()],
                kb_reference=kb_reference
            )
            await create_incident(new_incident.dict())
            incident_data = new_incident.dict()
            logger.info(f"Created new incident {current_incident_id} with status {initial_status}")

    elif current_incident_id:
        # Continue existing incident - DO NOT search KB again
        incident_data = await get_incident(current_incident_id)
        if not incident_data:
            # Incident not found, clear and start fresh
            clear_active_incident(session_id)
            await clear_session_history(session_id)
            current_incident_id = None
        else:
            # Update existing incident with new user message
            incident_data["additional_info"].append(Message(sender="User", text=query).dict())

    # Get LLM response - LLM handles all intelligence
    llm_response, history = await get_llm_response(
        query, 
        session_id, 
        kb_chunks if is_new_incident else [],  # Only pass chunks for new incidents
        incident_id=current_incident_id
    )

    # Update incident with AI response and status
    if current_incident_id:
        if not incident_data:
            incident_data = await get_incident(current_incident_id)
        
        # Add AI response to incident
        incident_data["additional_info"].append(Message(sender="AI", text=llm_response).dict())
        
        # Get status from LLM context analysis
        incident_ctx = get_incident_context(session_id)
        new_status = incident_ctx.get('status', incident_data["status"])
        
        update_data = {
            "additional_info": incident_data["additional_info"],
            "status": new_status,
            "updated_on": datetime.utcnow()
        }
        
        await update_incident(current_incident_id, update_data)
        
        # Ensure incident ID is in response for new incidents
        if is_new_incident and current_incident_id not in llm_response:
            llm_response = f"{llm_response}\n\n🔧 Incident Reference: {current_incident_id}"

        # Also ensure status is visible
        if current_incident_id in llm_response and f"Status: {new_status}" not in llm_response:
            llm_response += f"\n\nCurrent Status: {new_status}"

    return {
        "session_id": session_id,
        "incident_id": current_incident_id,
        "response": llm_response,
        "status": incident_data["status"] if incident_data else None
    }

def _is_it_related_query(query: str) -> bool:
    """Basic check if query seems IT-related"""
    it_keywords = [
        'outlook', 'email', 'vpn', 'wifi', 'network', 'password', 'login',
        'software', 'application', 'computer', 'laptop', 'printer', 'server',
        'error', 'crash', 'not working', 'broken', 'issue', 'problem'
    ]
    
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in it_keywords)

@router.post("/end_session")
async def end_session(session_id: str):
    """Explicitly end a session"""
    incident_id = get_active_incident(session_id)
    
    if incident_id:
        # Update incident status before ending session
        incident_data = await get_incident(incident_id)
        if incident_data and incident_data["status"] != "Resolved":
            await update_incident(incident_id, {
                "status": "Closed", 
                "updated_on": datetime.utcnow()
            })
    
    clear_active_incident(session_id)
    await clear_session_history(session_id)
    
    return {"message": "Session ended successfully"}