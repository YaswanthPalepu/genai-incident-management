from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import GOOGLE_API_KEY
from db.chromadb import hybrid_search_kb
from db.mongodb import create_incident, update_incident, get_incident
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm = None
_conversation_history = {}
_session_data = {}  # Unified session storage

executor = ThreadPoolExecutor(max_workers=5)

def get_llm():
    global llm
    if llm is None:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GOOGLE_API_KEY,
            temperature=0.1
        )
    return llm

async def analyze_query_and_route(query: str, session_id: str) -> dict:
    """
    LLM analyzes query and determines the complete routing and action plan
    """
    llm_instance = get_llm()
    
    analysis_prompt = f"""You are an intelligent IT Incident Management System. Analyze the user's query and determine the complete action plan.

User Query: "{query}"

Available Actions:
1. DIRECT_RESPONSE - For greetings, farewells, irrelevant topics (respond directly)
2. KB_SEARCH - For IT incidents that need knowledge base search
3. INCIDENT_CREATION - For IT incidents with no KB match

Analysis Instructions:
- If it's greeting/farewell: respond naturally and mark as DIRECT_RESPONSE
- If it's irrelevant to IT incidents: politely redirect and mark as DIRECT_RESPONSE  
- If it's IT incident: analyze if we should search KB first
- Be intelligent about context - understand the user's real issue

RESPONSE FORMAT (STRICT JSON):
{{
    "action": "DIRECT_RESPONSE" | "KB_SEARCH" | "INCIDENT_CREATION",
    "reasoning": "brief explanation of your analysis",
    "is_it_related": true/false,
    "response_guidance": "if DIRECT_RESPONSE, guide how to respond naturally"
}}

Respond ONLY with valid JSON, no other text."""

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=analysis_prompt),
                HumanMessage(content="Analyze and route this query")
            ])
        )
        
        response_text = response.content.strip()
        analysis = json.loads(response_text)
        logger.info(f"Query analysis: {analysis}")
        return analysis
    
    except Exception as e:
        logger.error(f"Error in query analysis: {e}")
        # Default to KB search for IT incidents
        return {
            "action": "KB_SEARCH",
            "reasoning": "Analysis failed, defaulting to KB search",
            "is_it_related": True,
            "response_guidance": ""
        }

async def handle_direct_response(query: str, session_id: str, analysis: dict) -> str:
    """
    Handle greetings, farewells, and irrelevant queries directly via LLM
    """
    llm_instance = get_llm()
    
    direct_response_prompt = f"""You are an IT support assistant. Respond to the user appropriately based on the context.

User Query: "{query}"

Context: {analysis.get('response_guidance', 'Respond naturally and appropriately')}

Guidelines:
- If greeting: respond warmly and ask how you can help with IT issues
- If farewell: respond politely and offer future help
- If irrelevant: politely explain you only handle IT incidents and offer redirect
- Keep responses concise and professional

Respond directly to the user query:"""

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=direct_response_prompt),
                HumanMessage(content=query)
            ])
        )
        
        return response.content.strip()
    
    except Exception as e:
        logger.error(f"Error in direct response: {e}")
        return "I understand. How can I help you with IT issues today?"

async def handle_kb_search_and_incident(query: str, session_id: str) -> tuple:
    """
    Handle IT incidents with KB search and intelligent incident management
    Returns: (response_text, incident_id, status, kb_chunk)
    """
    # Initialize session data if not exists
    if session_id not in _session_data:
        _session_data[session_id] = {
            'kb_searched': False,
            'kb_chunk': None,
            'incident_id': None,
            'status': 'New',
            'conversation_state': 'initial',
            'required_info_gathered': False,
            'current_solution_step': 0,
            'total_solution_steps': 0
        }
    
    session = _session_data[session_id]
    incident_id = session.get('incident_id')
    kb_chunk = session.get('kb_chunk')
    
    # Step 1: Search KB if not already done
    if not session['kb_searched']:
        logger.info(f"Performing KB search for session {session_id}")
        search_results = hybrid_search_kb(query, n_results=3)
        
        if search_results and search_results[0]['similarity'] > 0.4:
            kb_chunk = {
                'kb_id': search_results[0]['kb_id'],
                'content': search_results[0]['content'],
                'similarity': search_results[0]['similarity']
            }
            session['kb_chunk'] = kb_chunk
            session['kb_searched'] = True
            logger.info(f"KB match found: {kb_chunk['kb_id']}")
        else:
            session['kb_searched'] = True
            session['kb_chunk'] = None
            logger.info("No KB match found")
    
    kb_chunk = session.get('kb_chunk')
    
    # Step 2: Create incident if doesn't exist
    if not incident_id:
        incident_id = f"INC{datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4].upper()}"
        session['incident_id'] = incident_id
        
        # Determine initial status
        if not kb_chunk:
            status = "Pending Admin Review"
            kb_ref = "No KB Match"
        else:
            status = "Pending Information"
            kb_ref = f"KB_{kb_chunk['kb_id']}"
        
        session['status'] = status
        
        # Create incident in MongoDB
        incident_data = {
            "incident_id": incident_id,
            "user_demand": query,
            "status": status,
            "kb_reference": kb_ref,
            "additional_info": [{"sender": "User", "text": query, "timestamp": datetime.utcnow().isoformat()}],
            "created_on": datetime.utcnow(),
            "updated_on": datetime.utcnow()
        }
        
        await create_incident(incident_data)
        logger.info(f"Created incident {incident_id} with status {status}")
    
    # Step 3: Get LLM response with current context
    llm_response = await get_incident_response(
        query=query,
        session_id=session_id,
        incident_id=incident_id,
        kb_chunk=kb_chunk,
        current_state=session
    )
    
    # Step 4: Update session state based on LLM response analysis
    await update_session_state(session_id, llm_response, query)
    
    # Step 5: Update incident in MongoDB
    await update_incident_in_db(session_id, query, llm_response)
    
    return llm_response, incident_id, session['status'], kb_chunk

async def get_incident_response(query: str, session_id: str, incident_id: str, kb_chunk: dict, current_state: dict) -> str:
    """
    Get intelligent LLM response for incident management
    """
    llm_instance = get_llm()
    
    # Build context from session state
    status = current_state['status']
    conversation_state = current_state['conversation_state']
    kb_content = kb_chunk['content'] if kb_chunk else "No knowledge base match found."
    
    incident_prompt = f"""You are an IT Incident Management AI Assistant. Manage this incident intelligently.

INCIDENT CONTEXT:
- Incident ID: {incident_id}
- Current Status: {status}
- Conversation State: {conversation_state}
- KB Available: {'Yes' if kb_chunk else 'No'}

KNOWLEDGE BASE CONTENT (if available):
{kb_content}

USER'S LATEST QUERY:
"{query}"

INTELLIGENT INCIDENT MANAGEMENT FLOW:

1. IF NO KB MATCH (Pending Admin Review):
   - Inform user that specialized admin support is needed
   - Assure them they'll be contacted soon
   - Do NOT try to solve the issue yourself

2. IF KB MATCH FOUND:
   - PHASE 1: Required Information Gathering (Status: Pending Information)
     * Analyze what specific information is needed from the KB content
     * Ask for ONE piece of information at a time
     * Wait for user to provide each required information
   
   - PHASE 2: Solution Execution (Status: In Progress)  
     * Provide solution steps ONE at a time from KB
     * After each step, wait for user confirmation before proceeding
     * Explain each step clearly and help troubleshoot if needed
   
   - PHASE 3: Resolution Verification (Status: Resolved/Open)
     * After all steps, ask if issue is resolved
     * If yes: mark resolved, if no: mark open for further help

3. CONVERSATION MANAGEMENT:
   - Be natural and conversational
   - Show current incident ID and status in responses
   - Track where we are in the process intelligently
   - Only ask for information mentioned as required in KB
   - Only provide solution steps that are in KB

RESPOND naturally to the user while managing the incident flow. Include incident ID and status in your response."""

    try:
        # Get conversation history
        history = _conversation_history.get(session_id, [])
        history_text = _format_history(history[-6:])  # Last 6 messages
        
        full_prompt = f"{incident_prompt}\n\nCONVERSATION HISTORY:\n{history_text}"
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=full_prompt),
                HumanMessage(content=query)
            ])
        )
        
        response_text = response.content.strip()
        
        # Update conversation history
        if session_id not in _conversation_history:
            _conversation_history[session_id] = []
        
        _conversation_history[session_id].extend([
            HumanMessage(content=query, name="User"),
            HumanMessage(content=response_text, name="AI")
        ])
        
        # Keep history manageable
        if len(_conversation_history[session_id]) > 20:
            _conversation_history[session_id] = _conversation_history[session_id][-20:]
        
        return response_text
    
    except Exception as e:
        logger.error(f"Error getting incident response: {e}")
        return f"I'm analyzing your issue. Incident {incident_id} is currently {status}. Please bear with me."

async def update_session_state(session_id: str, llm_response: str, user_query: str):
    """
    Analyze LLM response and update session state intelligently
    """
    llm_instance = get_llm()
    
    session = _session_data[session_id]
    current_state = session.copy()
    
    state_analysis_prompt = f"""Analyze the AI's response and update the incident state.

Current State:
- Status: {current_state['status']}
- Conversation State: {current_state['conversation_state']}
- Required Info Gathered: {current_state['required_info_gathered']}
- Current Step: {current_state['current_solution_step']}

User Query: "{user_query}"
AI Response: "{llm_response}"

Determine the NEW state based on the conversation flow:

STATUS OPTIONS:
- "Pending Admin Review": No KB match, waiting for admin
- "Pending Information": Gathering required information from user  
- "In Progress": Executing solution steps
- "Resolved": Issue confirmed fixed by user
- "Open": Issue not resolved after solution attempts

CONVERSATION STATE OPTIONS:
- "initial": Just started
- "gathering_info": Asking for required information
- "executing_steps": Providing solution steps
- "verifying_resolution": Checking if issue is fixed
- "completed": Conversation ended

Update the state based on what the AI is doing in the response.

RESPONSE FORMAT (JSON only):
{{
    "status": "new status",
    "conversation_state": "new conversation state", 
    "required_info_gathered": true/false,
    "current_solution_step": number,
    "total_solution_steps": number
}}"""

    try:
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=state_analysis_prompt),
                HumanMessage(content="Update state")
            ])
        )
        
        new_state = json.loads(analysis.content.strip())
        
        # Update session with new state
        session.update(new_state)
        logger.info(f"Updated session state: {new_state}")
    
    except Exception as e:
        logger.error(f"Error updating session state: {e}")
        # Keep current state on error

async def update_incident_in_db(session_id: str, user_query: str, ai_response: str):
    """
    Update incident in MongoDB with latest conversation
    """
    try:
        session = _session_data[session_id]
        incident_id = session['incident_id']
        
        if not incident_id:
            return
        
        # Get current incident
        incident = await get_incident(incident_id)
        if not incident:
            logger.warning(f"Incident {incident_id} not found in DB")
            return
        
        # Update additional info
        additional_info = incident.get('additional_info', [])
        additional_info.extend([
            {"sender": "User", "text": user_query, "timestamp": datetime.utcnow().isoformat()},
            {"sender": "AI", "text": ai_response, "timestamp": datetime.utcnow().isoformat()}
        ])
        
        # Prepare update data
        update_data = {
            "status": session['status'],
            "additional_info": additional_info,
            "updated_on": datetime.utcnow()
        }
        
        # Update in MongoDB
        success = await update_incident(incident_id, update_data)
        if success:
            logger.info(f"Updated incident {incident_id} in DB with status {session['status']}")
        else:
            logger.warning(f"Failed to update incident {incident_id} in DB")
    
    except Exception as e:
        logger.error(f"Error updating incident in DB: {e}")

def _format_history(history: list) -> str:
    """Format conversation history for context"""
    if not history:
        return "No previous conversation"
    
    formatted = []
    for msg in history:
        if hasattr(msg, 'name') and hasattr(msg, 'content'):
            role = "User" if msg.name == "User" else "AI"
            formatted.append(f"{role}: {msg.content[:200]}")
    
    return "\n".join(formatted)

def get_session_incident_id(session_id: str) -> str:
    """Get incident ID for session"""
    session = _session_data.get(session_id, {})
    return session.get('incident_id')

def get_session_status(session_id: str) -> str:
    """Get status for session"""
    session = _session_data.get(session_id, {})
    return session.get('status', 'New')

async def clear_session_data(session_id: str):
    """Clear all session data"""
    if session_id in _conversation_history:
        del _conversation_history[session_id]
    if session_id in _session_data:
        del _session_data[session_id]
    logger.info(f"Cleared session data for {session_id}")