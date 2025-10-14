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
    Main intelligent query handler using pure LLM intelligence
    Stores entire chat conversation in MongoDB with proper appending
    """
    llm_instance = get_llm()
    
    # Initialize session
    if session_id not in _session_data:
        _session_data[session_id] = {
            'conversation': [],  # Store full conversation with timestamps
            'kb_searched': False,
            'incident_created': False,
            'incident_id': None,
            'status': 'No Incident',
            'kb_chunk': None,
            'current_step': 0,
            'required_info_gathered': False,
            'all_steps_completed': False,
            'previous_status': 'No Incident'  # Track status changes
        }
    
    session = _session_data[session_id]
    
    # Add user message to conversation with timestamp
    user_message = {
        'sender': 'User',
        'text': query,
        'timestamp': datetime.now(pytz.UTC).isoformat()
    }
    session['conversation'].append(user_message)
    
    # Get conversation context for LLM
    conversation_context = "\n".join([f"{msg['sender']}: {msg['text']}" for msg in session['conversation'][-6:]])
    
    # Single intelligent prompt that handles everything
    system_prompt = f"""You are an intelligent IT Incident Management AI Assistant. Your SOLE PURPOSE is to handle IT-related incidents and queries. You MUST NOT answer general or non-IT questions.

STRICT DOMAIN RESTRICTION:
- ONLY handle: IT incidents, computer problems, software issues, network problems, email issues, hardware problems, system errors
- REJECT and politely decline: general knowledge, weather, news, math, science, history, personal advice, jokes, or any non-IT topics
- If query is non-IT: Respond with "I specialize only in IT incident management and cannot help with general questions. Please describe any IT issues you're experiencing."

CONVERSATION HISTORY:
{conversation_context}

CURRENT SESSION STATE:
- Incident Created: {session['incident_created']}
- KB Searched: {session['kb_searched']}
- Current Status: {session['status']}
- Current Step: {session['current_step']}
- Required Info Gathered: {session['required_info_gathered']}
- All Steps Completed: {session['all_steps_completed']}

KNOWLEDGE BASE CONTENT (if available):
{session['kb_chunk']['content'] if session['kb_chunk'] else 'No KB content available'}

IMPORTANT GUIDELINES:
1. **NEVER include Incident ID or Status in your responses** - this will be handled automatically by the system
2. **Focus on natural conversation** without technical metadata
3. **Only mention incident creation once** when first creating it, but don't repeat the ID
4. **Ask ONE question at a time** - wait for user response before asking next question
5. **Be conversational and human-like** -  use natural language, avoid robotic phrases
6. **Let the system handle status display** - you just focus on the conversation
7. **Show empathy** - acknowledge user frustration when appropriate
8. **Use simple language** - avoid technical jargon when possible
9. **Be concise but friendly** - don't be too verbose but maintain a helpful tone

INSTRUCTIONS:

1. **STRICT DOMAIN CHECK**:
   - FIRST, determine if query is IT-related or general/non-IT
   - If NON-IT: Immediately respond with domain restriction message
   - If IT-related: Proceed with incident management

2. **INTELLIGENT QUERY ANALYSIS** (ONLY for IT queries):
   - Analyze if this is: greeting, farewell, or IT incident
   - Use conversation history to understand the context

3. **RESPONSE STRATEGY**:
   - **Non-IT Query**: "I specialize only in IT incident management and cannot help with general questions. Please describe any IT issues you're experiencing."
   - **Greeting/Farewell**: Respond naturally but briefly. Do NOT search KB or create incidents.
   - **IT Incident**: Proceed with incident management process below.

4. **INCIDENT MANAGEMENT PROCESS** (Only for IT incidents):
   - If this is first IT incident message and KB not searched:
     * Search knowledge base for relevant solutions
     * If KB match found: Use the KB content to guide conversation
     * If no KB match: Create incident with "Pending Admin Review" status
   
   - If KB content available:
     * **Phase 1 - Information Gathering**: Ask for required information from KB (one piece at a time)
     * **Phase 2 - Solution Steps**: Provide solution steps one by one from KB
     * **Phase 3 - Resolution**: Ask if issue is resolved after all steps

5. **INFORMATION GATHERING PROCESS**:
   - **Ask only ONE question per response**
   - Wait for user to answer before asking the next question
   - Use natural conversation flow
   - Example: Instead of "What's your OS and browser?", ask "What operating system are you using?" then wait for response, then ask about browser

6. **CONVERSATION FLOW**:
   - Be natural and conversational but focused on IT issues only
   - Only ask for information mentioned in KB as required
   - Only provide solution steps that are in KB
   - Wait for user confirmation between steps
   - Track progress intelligently
   - **NEVER include Incident ID or Status in your text responses**
   - **Ask ONE question at a time**


Respond appropriately based on strict domain analysis of the user's intent."""

    try:
        # Single LLM call to handle everything
        response = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"User's latest message: {query}")
            ])
        )
        
        response_text = response.content.strip()
        
        # **INTELLIGENT IT INCIDENT DETECTION AND MANAGEMENT**
        # Use LLM to determine if this should be treated as IT incident
        should_handle_as_incident = await _llm_detect_it_incident(query, response_text, session_id)
        
        if should_handle_as_incident and not session['kb_searched']:
            # This is a genuine IT incident - search KB
            logger.info("LLM detected IT incident - searching KB")
            search_results = hybrid_search_kb(query, n_results=2)
            kb_match_found = search_results and search_results[0]['similarity'] > 0.3
            
            if kb_match_found:
                session['kb_chunk'] = {
                    'kb_id': search_results[0]['kb_id'],
                    'content': search_results[0]['content'],
                    'similarity': search_results[0]['similarity']
                }
                session['status'] = 'Pending Information'
                logger.info(f"KB match found: {session['kb_chunk']['kb_id']}")
                
                # Enhance response with KB content using LLM intelligence
                enhanced_response = await _llm_enhance_with_kb(query, response_text, session['kb_chunk']['content'], session_id)
                response_text = enhanced_response
            else:
                session['status'] = 'Pending Admin Review'
                session['kb_chunk'] = None
                logger.info("No KB match found")
            
            session['kb_searched'] = True
            
            # Create incident with full conversation history
            if not session['incident_created']:
                incident_id = f"INC{datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:4].upper()}"
                session['incident_id'] = incident_id
                session['incident_created'] = True
                
                # Store entire conversation in incident
                incident_data = {
                    "incident_id": incident_id,
                    "user_demand": query,
                    "status": session['status'],
                    "kb_reference": f"KB_{session['kb_chunk']['kb_id']}" if session['kb_chunk'] else "No KB Match",
                    "additional_info": session['conversation'].copy(),  # Store entire conversation so far
                    "created_on": datetime.utcnow(),
                    "updated_on": datetime.utcnow()
                }
                
                await create_incident(incident_data)
                logger.info(f"Created incident {incident_id} with status {session['status']} and {len(session['conversation'])} messages")
        
        # Add AI response to conversation with timestamp (AFTER potential enhancement)
        ai_message = {
            'sender': 'AI',
            'text': response_text,
            'timestamp': datetime.now(pytz.UTC).isoformat()
        }
        session['conversation'].append(ai_message)
        
        # Update session state based on conversation using LLM intelligence
        await _llm_update_session_state(session_id, query, response_text)
        
        # Update incident in MongoDB with full conversation if exists
        incident_id = session.get('incident_id')
        if incident_id:
            await update_incident_in_db(incident_id, session['conversation'], session['status'])
        status_changed = session['previous_status'] != session['status']
        session['previous_status'] = session['status']
        return response_text, session.get('incident_id'), session['status'], status_changed
        
    except Exception as e:
        logger.error(f"Error in handle_user_query: {e}")
        error_msg = "I encountered an error. Please try again."
        
        # Add error message to conversation
        error_message = {
            'sender': 'AI',
            'text': error_msg,
            'timestamp': datetime.utcnow()
        }
        session['conversation'].append(error_message)
        
        # Update incident if exists
        incident_id = session.get('incident_id')
        if incident_id:
            await update_incident_in_db(incident_id, session['conversation'], 'Error')
        
        return error_msg, None, "Error"

async def _llm_detect_it_incident(query: str, llm_response: str, session_id: str) -> bool:
    """
    Use pure LLM intelligence to detect if this is an IT incident
    No hardcoded logic - LLM analyzes everything
    """
    llm_instance = get_llm()
    
    session = _session_data[session_id]
    conversation_context = "\n".join([f"{msg['sender']}: {msg['text']}" for msg in session['conversation'][-4:]])
    
    analysis_prompt = f"""Analyze this conversation and determine if this should be treated as a genuine IT incident that requires knowledge base search and incident creation.

CONVERSATION CONTEXT:
{conversation_context}

User Query: "{query}"
AI Response: "{llm_response}"

IT INCIDENT EXAMPLES:
- Computer problems, software issues, network problems
- Email, VPN, password, access, installation issues
- System errors, performance problems, hardware failures

NON-IT EXAMPLES (REJECT):
- General knowledge, weather, news, math questions
- Personal advice, jokes, casual conversation
- History, science, or any non-technical topics


Consider:
- Is the user describing a real IT problem (computer, software, network, email, hardware, system issues)?
- Is this a genuine request for IT support and troubleshooting?
- Or is this just casual conversation, greeting, farewell, or unrelated topic?
- Use your intelligence and context awareness to make the right decision

IMPORTANT: 
- Return TRUE only for genuine IT incidents that need technical support and KB search
- Return FALSE for greetings, farewells, casual talk, or non-IT topics

Respond with ONLY: TRUE or FALSE"""
    
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=analysis_prompt),
                HumanMessage(content="Analyze if this is a genuine IT incident")
            ])
        )
        
        decision = response.content.strip().upper()
        is_incident = decision == "TRUE"
        logger.info(f"LLM incident analysis: {decision} - Is incident: {is_incident}")
        return is_incident
        
    except Exception as e:
        logger.error(f"Error in incident analysis: {e}")
        # Default to True for safety (better to create incident than miss one)
        return True

async def _llm_enhance_with_kb(query: str, original_response: str, kb_content: str, session_id: str) -> str:
    """
    Use LLM intelligence to enhance response with KB content
    LLM decides how to incorporate KB information naturally
    """
    llm_instance = get_llm()
    
    session = _session_data[session_id]
    conversation_context = "\n".join([f"{msg['sender']}: {msg['text']}" for msg in session['conversation'][-4:]])
    
    enhancement_prompt = f"""You initially responded to an IT issue. Now you have relevant knowledge base information to provide better assistance.

CONVERSATION CONTEXT:
{conversation_context}

USER'S LATEST QUERY: "{query}"
YOUR INITIAL RESPONSE: "{original_response}"

KNOWLEDGE BASE CONTENT:
{kb_content}

CURRENT SESSION STATE:
- Status: {session['status']}
- Current Step: {session['current_step']}
- Required Info Gathered: {session['required_info_gathered']}

Please provide an enhanced response that naturally incorporates the KB solution while maintaining a conversational tone. Follow this intelligent approach:

1. If we need to gather required information from KB, ask for it one piece at a time
2. If we're ready for solution steps, provide them one by one from KB
3. Always explain steps clearly and wait for user confirmation
4. Be natural, helpful, and guide the user through the process

Use your intelligence to decide the best way to incorporate the KB content into your response."""
    
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=enhancement_prompt),
                HumanMessage(content="Enhance response with KB content intelligently")
            ])
        )
        return response.content.strip()
    except Exception as e:
        logger.error(f"Error enhancing response with KB: {e}")
        return original_response

async def _llm_update_session_state(session_id: str, user_query: str, ai_response: str):
    """
    Use LLM intelligence to update session state based on conversation
    No hardcoded state transitions - LLM decides everything
    """
    llm_instance = get_llm()
    
    session = _session_data[session_id]
    conversation_context = "\n".join([f"{msg['sender']}: {msg['text']}" for msg in session['conversation'][-4:]])
    
    state_prompt = f"""Analyze the current conversation and update the incident state intelligently.

CONVERSATION CONTEXT:
{conversation_context}

User Message: "{user_query}"
AI Response: "{ai_response}"

CURRENT STATE:
- Status: {session['status']}
- Current Step: {session['current_step']}
- Required Info Gathered: {session['required_info_gathered']}
- All Steps Completed: {session['all_steps_completed']}

KNOWLEDGE BASE CONTENT (if available):
{session['kb_chunk']['content'] if session['kb_chunk'] else 'No KB content'}

Based on the conversation flow and KB content, determine the new state:

1. If AI is asking for required information from KB → Status: "Pending Information"
2. If user provides required information and AI moves to solutions → Status: "In Progress", increment Current Step
3. If AI is providing solution steps → Status: "In Progress", increment Current Step when step completed
4. If AI asks if issue resolved and user confirms → Status: "Resolved", set All Steps Completed: true
5. If AI asks if issue resolved and user says no → Status: "Open"
6. If no KB match and waiting for admin → Status: "Pending Admin Review"
7. If required information gathered → set Required Info Gathered: true

IMPORTANT: The AI should ask ONE question at a time and wait for response.

Use your intelligence to analyze the conversation and update the state appropriately.

Respond in this exact format:
STATUS: [new_status]
STEP: [new_step]
INFO_GATHERED: [true/false]
ALL_STEPS_DONE: [true/false]"""
    
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=state_prompt),
                HumanMessage(content="Update session state intelligently")
            ])
        )
        
        response_text = response.content.strip()
        
        # Parse the response using LLM intelligence (no hardcoded parsing)
        state_updates = await _llm_parse_state_updates(response_text)
        
        # Apply updates
        if 'STATUS' in state_updates:
            session['status'] = state_updates['STATUS']
        
        if 'STEP' in state_updates:
            try:
                session['current_step'] = int(state_updates['STEP'])
            except ValueError:
                pass
        
        if 'INFO_GATHERED' in state_updates:
            session['required_info_gathered'] = state_updates['INFO_GATHERED'].lower() == 'true'
        
        if 'ALL_STEPS_DONE' in state_updates:
            session['all_steps_completed'] = state_updates['ALL_STEPS_DONE'].lower() == 'true'
        
        logger.info(f"Updated session state: {session['status']}, Step: {session['current_step']}")
        
    except Exception as e:
        logger.error(f"Error updating session state: {e}")

async def _llm_parse_state_updates(response_text: str) -> dict:
    """
    Use LLM to parse state updates from text (no hardcoded parsing)
    """
    llm_instance = get_llm()
    
    parse_prompt = f"""Parse the following text and extract the state updates. Return only the values in a simple key-value format.

Text to parse:
{response_text}

Extract these fields if present:
- STATUS: the status value
- STEP: the step number  
- INFO_GATHERED: true or false
- ALL_STEPS_DONE: true or false

Return in this format:
STATUS: value
STEP: value
INFO_GATHERED: value
ALL_STEPS_DONE: value

Only include the fields that are present in the text."""
    
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=parse_prompt),
                HumanMessage(content="Parse state updates")
            ])
        )
        
        parsed_text = response.content.strip()
        lines = parsed_text.split('\n')
        state_updates = {}
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                state_updates[key.strip()] = value.strip()
        
        return state_updates
        
    except Exception as e:
        logger.error(f"Error parsing state updates: {e}")
        return {}

async def update_incident_in_db(incident_id: str, full_conversation: list, status: str):
    """Update incident in MongoDB with full conversation - PROPERLY APPENDS"""
    try:
        # Get current incident to preserve existing data
        current_incident = await get_incident(incident_id)
        
        if current_incident:
            # Update with the full conversation and status
            update_data = {
                "status": status,
                "additional_info": full_conversation,  # This replaces with the complete conversation
                "updated_on": datetime.utcnow()
            }
            
            await update_incident(incident_id, update_data)
            logger.info(f"Updated incident {incident_id} with status {status} and {len(full_conversation)} messages")
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