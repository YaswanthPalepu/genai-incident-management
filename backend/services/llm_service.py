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
            model="gemini-2.0-flash",
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
            'phase': None, 
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
    # UPDATED: The instructions here are crucial for the LLM's response generation logic.
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
   - ONLY gather information - do NOT provide solutions.
   - Ask ONE question at a time about the issue to understand it better.
   - After gathering sufficient info (e.g., after 2-3 questions are answered), inform user: "Thank you for providing the details. I have forwarded this incident to our admin team for review. They will contact you shortly with a solution."
   - Then the system will set the status to "Pending Admin Review".
   - **Ensure you DO NOT ask for information already provided in the `CONVERSATION HISTORY`.**
6. **IF IT INCIDENT WITH KB MATCH** (Status: "Pending Information"):
   - **Phase: gathering_info** - Ask for required information from the KB one at a time.
   - Once ALL required information from the KB has been gathered, inform the user: "Thank you for providing the necessary information. I have created an incident, and our admin team will contact you shortly with the solution."
   - Then the system will set the status to "Open". **DO NOT provide solution steps from the KB to the user.**
   - Wait for user response before moving forward.
   - **Ensure you DO NOT ask for information already provided in the `CONVERSATION HISTORY`.**

BE CONVERSATIONAL, EMPATHETIC, AND NATURAL. Ask ONE question at a time."""

    try:
        # CALL 1: Generate response based on current state and prompt
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
        # UPDATED: Status and phase transitions now align with "Open" status.
        analysis_prompt = f"""Analyze the conversation and extract metadata. Return ONLY valid JSON (no markdown, no extra text).

USER LATEST MESSAGE: "{query}"
AI RESPONSE: "{response_text}"

CURRENT SESSION:
- Incident Created: {session['incident_created']}
- Status: {session['status']}
- Phase: {session['phase']}
- Info Gathered: {session['required_info_gathered']}
- KB Found: {session['kb_chunk'] is not None}
- Conversation length: {len(session['conversation'])}
- Has KB chunk been available previously in this session?: {session['kb_chunk'] is not None}

EXTRACT (respond with ONLY JSON object, nothing else):
{{
    "is_farewell": true/false,
    "is_off_topic": true/false,
    "is_it_incident": true/false,
    "should_search_kb": true/false,
    "new_status": "Pending Admin Review" | "Pending Information" | "Open" | "Resolved" | null,
    "new_phase": "gathering_info" | "resolution" | null,
    "info_gathered": true/false,
    "all_steps_done": true/false,
    "needs_escalation": true/false,
    "reason": "brief reason"
}}

CRITICAL STATUS & PHASE RULES:

**STATUS TRANSITIONS (MOST IMPORTANT):**

1. **New IT Incident (No KB Found):** If `is_it_incident` is true, `incident_created` is false, and `KB Found` is false: `new_status` should be "Pending Admin Review", `new_phase` should be "gathering_info".
2. **New IT Incident (KB Found):** If `is_it_incident` is true, `incident_created` is false, and `KB Found` is true: `new_status` should be "Pending Information", `new_phase` should be "gathering_info".
3. **KB Matched Incident - Info Gathering Complete:** If `AI RESPONSE` *explicitly states* "Thank you for providing the necessary information. I have created an incident, and our admin team will contact you shortly with the solution." (This indicates completion of gathering info for a KB-matched incident):
   - `info_gathered` MUST be true.
   - `all_steps_done` MUST be true.
   - `new_status` MUST be "Open".
   - `new_phase` should be "resolution" or `null`.
4. **No KB Matched Incident - Info Gathering Complete:** If `AI RESPONSE` *explicitly states* "Thank you for providing the details. I have forwarded this incident to our admin team for review. They will contact you shortly with a solution." (This indicates completion of gathering info for a non-KB-matched incident):
   - `info_gathered` MUST be true.
   - `all_steps_done` MUST be true.
   - `new_status` MUST be "Pending Admin Review".
   - `new_phase` should be "resolution" or `null`.
5. **Issue Explicitly Resolved:** If the `USER LATEST MESSAGE` indicates the issue is resolved (e.g., "It's fixed", "Problem solved", "I figured it out"): `new_status` should be "Resolved".
6. **No Status Change:** If none of the above conditions are met for `new_status`, it should be `null` (allowing the system to maintain the current status).

**PHASE TRANSITIONS:**
- If `new_status` becomes "Pending Information" or "Pending Admin Review" from `null` or 'No Incident': `new_phase` should be "gathering_info".
- If `info_gathered` becomes true and `new_status` is "Open" or "Pending Admin Review": `new_phase` should be "resolution" or `null`.

**KEY RULES:**
- is_farewell: true if user says goodbye, bye, thanks, done, no more questions, exit, quit, etc.
- is_off_topic: true if user response unrelated to current IT issue
- is_it_incident: true for genuine IT problems (computer, software, network, email, hardware, system errors), and false for greetings, farewells, or general questions.
- should_search_kb: true only if `is_it_incident` is true AND `session['kb_searched']` is false AND `session['incident_created']` is false.
- needs_escalation: true when `new_status` is "Open" or "Pending Admin Review" because the incident has been escalated/forwarded.
- `new_status` should be `null` if no explicit status change is detected.
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
        
        logger.info(f"Metadata extracted: {metadata}")
        
        # ========== HANDLE METADATA RESULTS ==========
        
        # Handle KB search if needed
        # Condition changed: `incident_created` added to prevent re-searching KB for ongoing incidents.
        if metadata.get('should_search_kb') and not session['kb_searched'] and not session['incident_created']:
            logger.info("Searching KB for IT incident")
            search_results = hybrid_search_kb(query, n_results=2)
            kb_match_found = search_results and search_results[0]['similarity'] > 0.3
            
            # Determine initial status based on KB match
            initial_status = 'Pending Information' if kb_match_found else 'Pending Admin Review'
            initial_phase = 'gathering_info' # Always starts in gathering info phase for new incidents
            
            if kb_match_found:
                session['kb_chunk'] = {
                    'kb_id': search_results[0]['kb_id'],
                    'content': search_results[0]['content'],
                    'similarity': search_results[0]['similarity']
                }
                logger.info(f"KB match found: {session['kb_chunk']['kb_id']}")
            else:
                session['kb_chunk'] = None
                logger.info("No KB match found")
            
            session['status'] = initial_status
            session['phase'] = initial_phase
            session['kb_searched'] = True
            
            # Create incident only if it's a new IT incident and not already created
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

        # Track status change for frontend
        status_changed = session['previous_status'] != metadata.get('new_status', session['status'])
        
        # Update session state based on metadata, respecting the new flow
        # This part handles the transition to "Open" status.
        if metadata.get('new_status'):
            session['status'] = metadata['new_status']
        if metadata.get('new_phase'):
            session['phase'] = metadata['new_phase']

        if metadata.get('info_gathered') and session['status'] == 'Pending Information':
            # If all required info from KB is gathered and it was a KB match scenario,
            # transition to "Open".
            session['required_info_gathered'] = True
            session['all_steps_completed'] = True # All steps (info gathering) done.
            session['status'] = 'Open' # New status: Open
            session['phase'] = 'resolution' # Phase can be resolution or null after info gathering.
            logger.info(f"KB matched incident {session.get('incident_id')} moved to 'Open' status after info gathering.")

        elif metadata.get('info_gathered') and session['status'] == 'Pending Admin Review':
            # If info gathered for a non-KB matched incident, keep it Pending Admin Review
            session['required_info_gathered'] = True
            session['all_steps_completed'] = True # All steps (info gathering) done.
            session['status'] = 'Pending Admin Review'
            session['phase'] = 'resolution'
            logger.info(f"No KB matched incident {session.get('incident_id')} status remains 'Pending Admin Review' after info gathering.")
        
        # If the user states the issue is resolved, update the status
        if metadata.get('new_status') == 'Resolved':
            session['status'] = 'Resolved'
            session['phase'] = 'resolution'

        # Update incident in DB if an incident exists
        incident_id = session.get('incident_id')
        if incident_id:
            await update_incident_in_db(incident_id, session['conversation'], session['status'], session['kb_chunk'])
        
        session['previous_status'] = session['status']
        
        return response_text, session.get('incident_id'), session['status'], status_changed
        
    except Exception as e:
        logger.error(f"Error in handle_user_query: {e}", exc_info=True)
        error_msg = "I encountered an error. Please try again."
        
        error_message = {
            'sender': 'AI',
            'text': error_msg,
            'timestamp': datetime.now(pytz.UTC).isoformat()
        }
        session['conversation'].append(error_message)
        
        incident_id = session.get('incident_id')
        if incident_id:
            await update_incident_in_db(incident_id, session['conversation'], 'Error', session['kb_chunk'])
        
        return error_msg, None, "Error", False

async def update_incident_in_db(incident_id: str, full_conversation: list, status: str, kb_chunk: dict = None):
    """Update incident in MongoDB with full conversation and KB reference if available"""
    try:
        current_incident = await get_incident(incident_id)
        
        if current_incident:
            update_data = {
                "status": status,
                "additional_info": full_conversation,
                "updated_on": datetime.now(pytz.UTC).isoformat()
            }
            if kb_chunk:
                update_data["kb_reference"] = f"KB_{kb_chunk['kb_id']}"
            else:
                update_data["kb_reference"] = "No KB Match"
            
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
    # Note: _conversation_history is not used directly but keep the check.
    if session_id in _conversation_history: 
        del _conversation_history[session_id]
    if session_id in _session_data:
        del _session_data[session_id]
    logger.info(f"Cleared session data for {session_id}")