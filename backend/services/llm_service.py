from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import GOOGLE_API_KEY
from db.chromadb import hybrid_search_kb
from db.mongodb import create_incident, update_incident, get_incident
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import uuid
import pytz
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm = None
_conversation_history = {}
_session_data = {}

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

async def handle_user_query(query: str, session_id: str) -> tuple:
    """
    Optimized query handler with CONSOLIDATED LLM calls
    Reduces API calls from 5+ to 2-3 per message
    """
    llm_instance = get_llm()
    
    # Initialize session
    if session_id not in _session_data:
        _session_data[session_id] = {
            'conversation': [],
            'kb_searched': False,
            'incident_created': False,
            'incident_id': None,
            'status': 'No Incident',
            'kb_chunk': None,
            'current_step': 0,
            'required_info_gathered': False,
            'all_steps_completed': False,
            'previous_status': 'No Incident',
            'phase': None,  # 'gathering_info', 'providing_solutions', 'resolution'
        }
    
    session = _session_data[session_id]
    
    # Add user message to conversation
    user_message = {
        'sender': 'User',
        'text': query,
        'timestamp': datetime.now(pytz.UTC).isoformat()
    }
    session['conversation'].append(user_message)
    
    conversation_context = "\n".join([f"{msg['sender']}: {msg['text']}" for msg in session['conversation'][-6:]])
    
    # ========== CONSOLIDATED LLM CALL #1: ANALYZE QUERY & PROVIDE RESPONSE ==========
    # Single LLM call that does: farewell check, off-topic detection, response generation, and state analysis
    system_prompt = f"""You are an intelligent IT Incident Management AI Assistant.

STRICT RULES:
1. ONLY handle IT incidents (computer, software, network, email, hardware, system issues)
2. REJECT non-IT queries: "I specialize only in IT incident management. Please describe any IT issues."
3. For greetings/farewells: respond naturally, don't create incidents
4. NEVER include Incident ID or Status in responses - system handles this

CONVERSATION HISTORY (last 6 messages):
{conversation_context}

CURRENT SESSION STATE:
- Incident Created: {session['incident_created']}
- KB Searched: {session['kb_searched']}
- Status: {session['status']}
- Phase: {session['phase']}
- Required Info Gathered: {session['required_info_gathered']}

KNOWLEDGE BASE CONTENT (if available):
{session['kb_chunk']['content'] if session['kb_chunk'] else 'No KB content'}

RESPONSE INSTRUCTIONS:

1. **ANALYZE THE QUERY** (in your thinking):
   - Is this a farewell? (goodbye, bye, thanks, done, etc.)
   - Is this off-topic during incident handling? (unrelated to current IT issue)
   - Is this IT-related or general knowledge?
   - Is user answering your previous question or being off-topic?

2. **IF FAREWELL**: Respond with friendly goodbye. System will show incident details.

3. **IF OFF-TOPIC DURING INCIDENT**: Redirect user back to your previous question naturally.
   Example: "I appreciate that, but let's focus on your IT issue. Could you answer my previous question about...?"

4. **IF NON-IT QUERY**: Reject with: "I specialize only in IT incident management and cannot help with general questions. Please describe any IT issues you're experiencing."

5. **IF IT INCIDENT WITHOUT KB MATCH** (Status: "Pending Admin Review"):
   - ONLY gather information - do NOT provide solutions
   - Ask ONE question at a time about the issue
   - Be conversational and natural
   - Example: "When did this issue start?" then wait for response

6. **IF IT INCIDENT WITH KB MATCH** (Status: "Pending Information" or "In Progress"):
   - If gathering info phase: Ask required info one at a time from KB
   - If providing solutions phase: Give solution steps one at a time
   - If resolution phase: Ask if issue is resolved
   - Wait for user response before moving forward

BE CONVERSATIONAL, EMPATHETIC, AND NATURAL. Ask ONE question at a time."""

    try:
        # CALL 1: Generate response
        response = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"User message: {query}")
            ])
        )
        
        response_text = response.content.strip()
        
        # Add AI response to conversation
        ai_message = {
            'sender': 'AI',
            'text': response_text,
            'timestamp': datetime.now(pytz.UTC).isoformat()
        }
        session['conversation'].append(ai_message)
        
        # ========== CONSOLIDATED LLM CALL #2: ANALYZE & EXTRACT METADATA ==========
        # Single call that does: incident detection, off-topic check, farewell check, and state updates
        analysis_prompt = f"""Analyze the conversation and extract metadata. Return ONLY valid JSON (no markdown, no extra text).

USER LATEST MESSAGE: "{query}"
AI RESPONSE: "{response_text}"

CURRENT SESSION:
- Incident Created: {session['incident_created']}
- Status: {session['status']}
- Phase: {session['phase']}
- KB Found: {session['kb_chunk'] is not None}

EXTRACT (respond with ONLY JSON object, nothing else):
{{
    "is_farewell": true/false,
    "is_off_topic": true/false,
    "is_it_incident": true/false,
    "should_search_kb": true/false,
    "new_status": "No Incident" | "Pending Admin Review" | "Pending Information" | "In Progress" | "Resolved" | "Escalated",
    "new_phase": null | "gathering_info" | "providing_solutions" | "resolution",
    "info_gathered": true/false,
    "all_steps_done": true/false,
    "reason": "brief reason"
}}

LOGIC RULES:
- is_farewell: true if user says goodbye, bye, thanks, done, no more questions, etc.
- is_off_topic: true if user response unrelated to current IT issue being discussed
- is_it_incident: true for genuine IT problems (computer, software, network, email, hardware, system errors)
- should_search_kb: true only if is_it_incident AND not already searched
- new_status: determine based on phase and conversation flow
- new_phase transitions: gathering_info → providing_solutions → resolution
"""

        metadata_response = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=analysis_prompt),
                HumanMessage(content="Extract metadata as JSON")
            ])
        )
        
        metadata_text = metadata_response.content.strip()
        
        # Parse JSON response
        try:
            # Remove markdown code blocks if present
            if "```json" in metadata_text:
                metadata_text = metadata_text.split("```json")[1].split("```")[0].strip()
            elif "```" in metadata_text:
                metadata_text = metadata_text.split("```")[1].split("```")[0].strip()
            
            metadata = json.loads(metadata_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse metadata JSON: {metadata_text}")
            metadata = {
                'is_farewell': False,
                'is_off_topic': False,
                'is_it_incident': False,
                'should_search_kb': False,
                'new_status': session['status'],
                'new_phase': session['phase'],
                'info_gathered': session['required_info_gathered'],
                'all_steps_done': session['all_steps_completed']
            }
        
        logger.info(f"Metadata extracted: Farewell={metadata.get('is_farewell')}, Off-topic={metadata.get('is_off_topic')}, IT={metadata.get('is_it_incident')}")
        
        # ========== HANDLE METADATA RESULTS ==========
        
        # Handle KB search if needed
        if metadata.get('should_search_kb') and not session['kb_searched']:
            logger.info("Searching KB for IT incident")
            search_results = hybrid_search_kb(query, n_results=2)
            kb_match_found = search_results and search_results[0]['similarity'] > 0.3
            
            if kb_match_found:
                session['kb_chunk'] = {
                    'kb_id': search_results[0]['kb_id'],
                    'content': search_results[0]['content'],
                    'similarity': search_results[0]['similarity']
                }
                session['status'] = 'Pending Information'
                session['phase'] = 'gathering_info'
                logger.info(f"KB match found: {session['kb_chunk']['kb_id']}")
            else:
                session['status'] = 'Pending Admin Review'
                session['phase'] = 'gathering_info'
                session['kb_chunk'] = None
                logger.info("No KB match found")
            
            session['kb_searched'] = True
            
            # Create incident
            if not session['incident_created']:
                incident_id = f"INC{datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4].upper()}"
                session['incident_id'] = incident_id
                session['incident_created'] = True
                
                incident_data = {
                    "incident_id": incident_id,
                    "user_demand": query,
                    "status": session['status'],
                    "kb_reference": f"KB_{session['kb_chunk']['kb_id']}" if session['kb_chunk'] else "No KB Match",
                    "additional_info": session['conversation'].copy(),
                    "created_on": datetime.utcnow(),
                    "updated_on": datetime.utcnow()
                }
                
                await create_incident(incident_data)
                logger.info(f"Created incident {incident_id} with status {session['status']}")
        
        # Update session state from metadata
        if metadata.get('new_status'):
            session['status'] = metadata['new_status']
        if metadata.get('new_phase'):
            session['phase'] = metadata['new_phase']
        if 'info_gathered' in metadata:
            session['required_info_gathered'] = metadata['info_gathered']
        if 'all_steps_done' in metadata:
            session['all_steps_completed'] = metadata['all_steps_done']
        
        # Update incident in DB
        incident_id = session.get('incident_id')
        if incident_id:
            await update_incident_in_db(incident_id, session['conversation'], session['status'])
        
        status_changed = session['previous_status'] != session['status']
        session['previous_status'] = session['status']
        
        return response_text, session.get('incident_id'), session['status'], status_changed
        
    except Exception as e:
        logger.error(f"Error in handle_user_query: {e}", exc_info=True)
        error_msg = "I encountered an error. Please try again."
        
        error_message = {
            'sender': 'AI',
            'text': error_msg,
            'timestamp': datetime.utcnow()
        }
        session['conversation'].append(error_message)
        
        incident_id = session.get('incident_id')
        if incident_id:
            await update_incident_in_db(incident_id, session['conversation'], 'Error')
        
        return error_msg, None, "Error", False

async def update_incident_in_db(incident_id: str, full_conversation: list, status: str):
    """Update incident in MongoDB with full conversation"""
    try:
        current_incident = await get_incident(incident_id)
        
        if current_incident:
            update_data = {
                "status": status,
                "additional_info": full_conversation,
                "updated_on": datetime.utcnow()
            }
            
            await update_incident(incident_id, update_data)
            logger.info(f"Updated incident {incident_id} with status {status}")
        else:
            logger.warning(f"Incident {incident_id} not found for update")
            
    except Exception as e:
        logger.error(f"Error updating incident: {e}")

def get_session_incident_id(session_id: str) -> str:
    """Get incident ID for session"""
    session = _session_data.get(session_id, {})
    return session.get('incident_id')

def get_session_status(session_id: str) -> str:
    """Get status for session"""
    session = _session_data.get(session_id, {})
    return session.get('status', 'No Incident')

async def clear_session_data(session_id: str):
    """Clear session data"""
    if session_id in _conversation_history:
        del _conversation_history[session_id]
    if session_id in _session_data:
        del _session_data[session_id]
    logger.info(f"Cleared session data for {session_id}")