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
            'required_info_gathered': False,
            'previous_status': 'No Incident',
            'phase': None,
            'questions_asked_count': 0,
            # 'last_question_asked': None, # REMOVED: No longer managing this in session state
        }
    
    session = _session_data[session_id]
    
    # Add user message to conversation
    user_message = {
        'sender': 'User',
        'text': query,
        'timestamp': datetime.now(pytz.UTC).isoformat()
    }
    session['conversation'].append(user_message)
    
    conversation_context = "\n".join([f"{msg['sender']}: {msg['text']}" for msg in session['conversation'][-8:]])
    
    # NO pre-processing of last_ai_question here, LLM will infer from conversation_context
    
    # ========== CONSOLIDATED LLM CALL #1: ANALYZE QUERY & PROVIDE RESPONSE ==========
    system_prompt = f"""You are an intelligent IT Incident Management AI Assistant.

STRICT RULES:
1. ONLY handle IT incidents (computer, software, network, email, hardware, system issues)
2. REJECT non-IT queries based on context (see detailed rules below)
3. For greetings/farewells: respond naturally, don't create incidents
4. **DO NOT** include the Incident ID or Status in your response text. The system will display this information separately to the user after your final completion message.

CONVERSATION HISTORY (last 8 messages, most recent at bottom):
{conversation_context}

CURRENT SESSION STATE:
- Incident Created: {session['incident_created']}
- KB Searched: {session['kb_searched']}
- Status: {session['status']}
- Phase: {session['phase']}
- KB Match Found: {session['kb_chunk'] is not None}
- Questions Asked So Far: {session['questions_asked_count']}
- Info Gathered: {session['required_info_gathered']}
# REMOVED: No longer providing 'Last Question Asked' from session state here

KNOWLEDGE BASE CONTENT (if KB match found):
{session['kb_chunk']['content'] if session['kb_chunk'] else 'No KB content - this is a non-KB incident'}

RESPONSE INSTRUCTIONS:

1. **IF INCIDENT COMPLETED**: If the Status is 'Open', 'Pending Admin Review', or 'Resolved', and Info Gathered is true, respond with a friendly and conversational farewell message (e.g., "Thanks for using the IT Assistant. I'm ready for your next IT issue.") and DO NOT ask any further questions.

2. **IF INITIAL GREETING (No active incident)**: Respond warmly and ask how you can help with IT issues. Example responses for hi/hello/etc.

3. **IF USER SAYS FAREWELL (at any point)**: 
   - If user indicates ending conversation (goodbye, bye, exit, done, etc.)
   - Provide a friendly closing message that:
     * Acknowledges the conversation ending
     * Includes the current Incident ID and Status if an incident exists
     * Offers to help with future IT issues
   - Examples:
     * With incident: "Thanks for using the IT Assistant! Your incident {session.get('incident_id')} has status: {session['status']}. I'm here if you have any more IT issues in the future. Goodbye!"
     * Without incident: "Thanks for using the IT Assistant! I'm here if you have any more IT issues in the future. Goodbye!"

4. **CRITICAL: IF UNRESPONSIVE OR OFF-TOPIC DURING ACTIVE IT INCIDENT** (Incident Created is true AND Status is NOT 'Open', 'Pending Admin Review', or 'Resolved'):
   - This is the HIGHEST PRIORITY rule during active incident gathering
   - User's latest message is either:
        a) **Off-topic**: Completely unrelated to the IT issue (e.g., asking about Python, favorite color).
        b) **Unresponsive**: Does not directly answer the immediate preceding question asked by the AI in the 'CONVERSATION HISTORY', or provides an irrelevant/nonsensical answer to it.
   - **Action**: Carefully identify the **last direct question asked by the AI** in the 'CONVERSATION HISTORY' that has not been adequately answered by the user. Politely reiterate this specific question.
   - **Example Response (adjust wording as needed)**: "I appreciate that, but let's focus on resolving your IT issue. Could you please answer my previous question about [reiterate the specific question you asked previously, e.g., 'which VPN client you are using (e.g., Cisco, GlobalProtect)?']?"
   - This rule takes precedence over rule 5 when an incident is being actively worked on

5. **IF NON-IT QUERY and incident is complete OR no incident exists** (Status is 'No Incident' OR 'Open' OR 'Pending Admin Review' OR 'Resolved'):
   - Respond politely: "I'm an IT Service Management assistant specialized in handling IT-related incidents. I'm unable to assist with general queries. However, I'm here to help if you have any IT issues. Is there anything IT-related I can assist you with?"
   - This applies when:
     * No incident has been created yet, OR
     * Incident is already completed (Open/Pending Admin Review/Resolved status), OR
     * After admin contact message has been given

6. **IF IT INCIDENT WITHOUT KB MATCH** (Non-KB scenario - No KB content available):
   - Your role: Gather information ONLY - do NOT provide solutions or troubleshooting steps
   - Ask ONE clear question at a time to understand the issue:
     * What exactly is happening with the application/system?
     * When did this issue start?
     * Are there any error messages displayed?
     * What have you already tried?
     * What operating system and version are you using?
   - DO NOT repeat questions already answered in conversation history
   - Remember the question you ask so it can be referenced if user goes off-topic
   - Count the Questions Asked So Far - after user has answered approximately 4-5 questions, provide this EXACT completion message:
     "Thank you for providing the details. I have forwarded this incident to our admin team for review. They will contact you shortly with a solution."
   - This EXACT phrase signals completion - do not paraphrase

7. **IF IT INCIDENT WITH KB MATCH** (KB scenario - KB content is available):
   - Your role: Gather specific information required by the KB solution - do NOT provide the solution steps to the user
   - Carefully review the KB content above to identify what specific information is needed for the solution
   - Ask for ONE piece of required information at a time
   - Examples based on KB requirements:
     * If KB mentions OS-specific steps, ask: "What operating system are you using?"
     * If KB needs hardware details, ask: "What device model do you have?"
     * If KB requires software version, ask: "Which version of [software] you are running?"
     * If KB references settings, ask about those specific settings
   - DO NOT repeat questions already answered in conversation history
   - Remember the question you ask so it can be referenced if user goes off-topic
   - Once ALL required information from the KB has been collected, provide this EXACT completion message:
     "Thank you for providing the necessary information. I have created an incident, and our admin team will contact you shortly with the solution."
   - This EXACT phrase signals completion - do not paraphrase

BE CONVERSATIONAL, EMPATHETIC, AND NATURAL. Focus on ONE question at a time. Keep responses concise and friendly."""

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
        analysis_prompt = f"""Analyze the conversation and extract metadata. Return ONLY valid JSON (no markdown, no extra text).

USER LATEST MESSAGE: "{query}"
AI RESPONSE: "{response_text}"

CURRENT SESSION STATE:
- Incident Created: {session['incident_created']}
- Status: {session['status']}
- Phase: {session['phase']}
- Info Gathered: {session['required_info_gathered']}
- KB Found: {session['kb_chunk'] is not None}
- Questions Asked: {session['questions_asked_count']}

EXTRACT (respond with ONLY a JSON object):
{{
    "is_farewell": true/false,
    "is_off_topic": true/false,
    "is_it_incident": true/false,
    "should_search_kb": true/false,
    "asked_question": true/false,
    // "question_text": "the actual question asked, or null", # REMOVED: No longer needed for session state
    "info_gathering_complete": true/false,
    "issue_resolved_by_user": true/false,
    "reason": "brief reason"
}}

CRITICAL RULES FOR EXTRACTION:

1. **is_farewell**: true if user explicitly indicates ending the conversation with words like:
   - goodbye, bye, thanks bye, done, exit, quit, farewell, see you, that's all, thank you, ending, closing, stop, no more, I'm done
   - This can happen at ANY point in the conversation (middle or end)
   - Does NOT depend on incident completion status

2. **is_off_topic**: true if user's message is a greeting/general question/non-IT question **while an incident is being actively worked on** (Incident Created is true AND Status is NOT 'Open', 'Pending Admin Review', or 'Resolved') AND the AI's response redirected the user back to the issue (Rule 4 in the main RESPONSE INSTRUCTIONS).

3. **is_it_incident**: true for genuine IT problems (computer, software, network, email, hardware, system errors)
   - FALSE for: greetings ("hi", "hello", "good morning"), general questions, non-IT topics
   - User must describe an actual IT issue/problem/error

4. **should_search_kb**: true ONLY when ALL of these are true:
   - is_it_incident is true
   - Incident Created is false
   - Status is "No Incident"

5. **asked_question**: true if AI response ends with a question mark (?) and is asking the user for information about the IT incident
   # REMOVED: No longer need to extract question_text here for session state

6. **info_gathering_complete**: true ONLY if AI response contains one of these TWO EXACT phrases (word-for-word):
   - "Thank you for providing the details. I have forwarded this incident to our admin team for review. They will contact you shortly with a solution."
   - "Thank you for providing the necessary information. I have created an incident, and our admin team will contact you shortly with the solution."
   
   IMPORTANT: Must match EXACTLY - if AI used similar wording but not exact, this should be FALSE.

7. **issue_resolved_by_user**: true if user explicitly states their issue is now fixed/resolved/working

8. **reason**: Brief explanation of what happened in this exchange"""

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
                'asked_question': False,
                # 'question_text': None, # REMOVED
                'info_gathering_complete': False,
                'issue_resolved_by_user': False
            }
        
        logger.info(f"Metadata extracted: {metadata}")
        
        # Track if question was asked
        if metadata.get('asked_question') and session['incident_created']:
            session['questions_asked_count'] += 1
            # REMOVED: No longer setting session['last_question_asked']
            logger.info(f"Question asked. Total questions: {session['questions_asked_count']}")
        
        # ========== HANDLE KB SEARCH FOR NEW INCIDENTS ==========
        if metadata.get('should_search_kb') and not session['kb_searched'] and not session['incident_created']:
            logger.info("Searching KB for IT incident")
            search_results = hybrid_search_kb(query, n_results=2)
            kb_match_found = search_results and len(search_results) > 0 and search_results[0].get('similarity', 0) > 0.3
            
            if kb_match_found:
                session['kb_chunk'] = {
                    'kb_id': search_results[0]['kb_id'],
                    'content': search_results[0]['content'],
                    'similarity': search_results[0]['similarity']
                }
                session['status'] = 'Pending Information'
                session['phase'] = 'gathering_info'
                logger.info(f"KB match found (similarity: {search_results[0]['similarity']:.3f}): KB_{session['kb_chunk']['kb_id']}")
            else:
                session['kb_chunk'] = None
                session['status'] = 'Pending Admin Review'
                session['phase'] = 'gathering_info'
                logger.info("No KB match found - will gather general incident information")
            
            session['kb_searched'] = True
            
            # Create incident
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
            logger.info(f"Created incident {incident_id} with initial status: {session['status']}")

        # Track status for change detection
        previous_status = session['previous_status']
        status_changed = False
        
        # ========== HANDLE INFO GATHERING COMPLETION ==========
        if metadata.get('info_gathering_complete') and not session['required_info_gathered']:
            session['required_info_gathered'] = True
            session['phase'] = 'resolution'
            
            # Determine final status based on KB presence
            if session['kb_chunk']:
                # KB matched scenario - transition to Open
                session['status'] = 'Open'
                status_changed = previous_status != 'Open'
                logger.info(f"KB-matched incident {session.get('incident_id')} completed info gathering -> Status: 'Open'")
            else:
                # Non-KB scenario - keep as Pending Admin Review
                session['status'] = 'Pending Admin Review'
                status_changed = previous_status != 'Pending Admin Review'
                logger.info(f"Non-KB incident {session.get('incident_id')} completed info gathering -> Status: 'Pending Admin Review'")
        
        # ========== HANDLE USER-RESOLVED ISSUES ==========
        if metadata.get('issue_resolved_by_user'):
            session['status'] = 'Resolved'
            session['phase'] = 'resolution'
            status_changed = previous_status != 'Resolved'
            logger.info(f"Incident {session.get('incident_id')} marked as 'Resolved' by user")

        # Update incident in DB if incident exists
        incident_id = session.get('incident_id')
        if incident_id:
            await update_incident_in_db(
                incident_id, 
                session['conversation'], 
                session['status'], 
                session['kb_chunk']
            )
        
        # Update previous status for next iteration
        session['previous_status'] = session['status']
        
        # The return values (response_text, incident_id, status) are used by the 
        # client application to display the final status message and metadata.
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
    """Update incident in MongoDB with full conversation and KB reference"""
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
            logger.info(f"Updated incident {incident_id} with status: {status}")
        else:
            logger.warning(f"Incident {incident_id} not found for update")
            
    except Exception as e:
        logger.error(f"Error updating incident in DB: {e}")

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