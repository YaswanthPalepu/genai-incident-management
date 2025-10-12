from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from config import GOOGLE_API_KEY
import logging
from concurrent.futures import ThreadPoolExecutor
import asyncio
import re
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm = None
_conversation_history = {}
_active_incident_sessions = {}
_incident_context = {}
_kb_context_cache = {}

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

async def get_llm_response(query: str, session_id: str, kb_chunks_content: list = None, incident_id: str = None):
    """LLM service that intelligently handles ALL conversation types"""
    llm_instance = get_llm()
    current_history = _conversation_history.get(session_id, [])
    
    # Cache KB context when provided (only for new incidents)
    if incident_id and kb_chunks_content and incident_id not in _kb_context_cache:
        _kb_context_cache[incident_id] = kb_chunks_content
        logger.info(f"Cached KB context for incident {incident_id}")
    
    # Get cached KB context if available
    cached_kb_chunks = _kb_context_cache.get(incident_id, []) if incident_id else []
    
    # Build intelligent context
    kb_context = _build_intelligent_context(cached_kb_chunks, incident_id)
    
    # Get current incident context
    incident_ctx = _incident_context.get(session_id, {})
    current_status = incident_ctx.get('status', 'New')

    system_prompt = f"""You are an AI assistant for an IT incident management system. You must intelligently handle ALL aspects of the conversation.

## YOUR INTELLIGENT RESPONSIBILITIES:

1. CONVERSATION ANALYSIS:
   - First, determine if this is a greeting (hi, hello), farewell (bye, goodbye), or IT issue
   - Handle greetings and farewells naturally and appropriately
   - For IT issues, guide the conversation professionally

2. INCIDENT CONTEXT AWARENESS:
   - Current Incident ID: {incident_id or "None - new conversation"}
   - Current Status: {current_status}
   - Knowledge Base: {kb_context}

3. INTELLIGENT FLOW MANAGEMENT:
   - If this is clearly a greeting: Respond naturally without creating incident
   - If this is clearly a farewell: Respond naturally and close conversation appropriately
   - If this is an IT issue with KB support: Ask required info, then provide solutions step by step
   - If this is an IT issue without KB: Create incident and escalate to admin

4. STATUS INTELLIGENCE:
   - Update status based on conversation flow naturally
   - "Pending Information" when asking questions
   - "In Progress" when providing solutions
   - "Resolved" when issue is fixed
   - "Pending Admin Review" when escalation needed

## CONVERSATION HISTORY:
{_format_conversation_history(current_history)}

## IMPORTANT:
- Use your intelligence to understand conversation context
- Handle greetings/farewells naturally
- Create incidents only for genuine IT issues
- Reference incident ID when appropriate
- Update status intelligently based on conversation flow"""

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=query)
            ])
        )
        llm_response_text = response.content
        
        # Update conversation history
        current_history.append(HumanMessage(content=query, name="User"))
        current_history.append(HumanMessage(content=llm_response_text, name="AI"))
        _conversation_history[session_id] = current_history
        
        # Let LLM intelligently analyze and update context
        await _intelligent_context_analysis(session_id, llm_response_text, query, incident_id)
        
        return llm_response_text, current_history
        
    except Exception as e:
        logger.error(f"Error invoking LLM: {e}")
        error_msg = "I'm experiencing technical difficulties. Please try again later."
        current_history.append(HumanMessage(content=query, name="User"))
        current_history.append(HumanMessage(content=error_msg, name="AI"))
        _conversation_history[session_id] = current_history
        return error_msg, current_history

def _build_intelligent_context(kb_chunks, incident_id):
    """Build intelligent context based on available information"""
    if not kb_chunks:
        return "No specific knowledge base entries found. Use general IT knowledge and judgment."
    
    context = ["🔍 RELEVANT KNOWLEDGE BASE FOUND:"]
    
    for i, chunk in enumerate(kb_chunks):
        context.append(f"\n--- Entry {i+1} ---")
        context.append(chunk)
    
    context.append("\n📋 INSTRUCTIONS:")
    context.append("- Ask for required information ONE question at a time")
    context.append("- After gathering info, provide solution steps ONE at a time")
    context.append("- Wait for user confirmation between steps")
    
    return "\n".join(context)

async def _intelligent_context_analysis(session_id: str, llm_response: str, user_query: str, incident_id: str):
    """Let LLM intelligently analyze conversation and update context"""
    llm_instance = get_llm()
    
    analysis_prompt = f"""Analyze this conversation intelligently:

User Query: "{user_query}"
AI Response: "{llm_response}"
Incident ID: {incident_id or "None"}

Based on your analysis of the conversation, determine the appropriate status and context.

Consider:
- Is this a greeting, farewell, or IT issue?
- What is the current phase of the conversation?
- What should be the next action?

Return ONLY the most appropriate status:
- "New" - Just starting, no incident yet
- "Pending Information" - Asking for details
- "In Progress" - Providing solutions
- "Resolved" - Issue appears resolved
- "Pending Admin Review" - Needs escalation
- "Closed" - Conversation ended

Use your intelligence to choose the best status."""

    try:
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(
            executor,
            lambda: llm_instance.invoke([
                SystemMessage(content=analysis_prompt),
                HumanMessage(content="Analyze conversation intelligently")
            ])
        )
        
        # Update incident context based on LLM analysis
        status = analysis.content.strip()
        valid_statuses = ["New", "Pending Information", "In Progress", "Resolved", "Pending Admin Review", "Closed"]
        
        if status in valid_statuses:
            _incident_context[session_id] = {'status': status}
            logger.info(f"LLM intelligently updated status to: {status} for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error in intelligent context analysis: {e}")

def _format_conversation_history(history):
    """Format conversation history"""
    if not history:
        return "No previous conversation"
    
    formatted = []
    for msg in history[-6:]:
        if hasattr(msg, 'name') and hasattr(msg, 'content'):
            formatted.append(f"{msg.name}: {msg.content}")
    return "\n".join(formatted)

# Session management functions
def set_active_incident(session_id: str, incident_id: str):
    """Set active incident for a session"""
    _active_incident_sessions[session_id] = incident_id
    logger.info(f"Set active incident {incident_id} for session {session_id}")

def get_active_incident(session_id: str):
    """Get active incident for a session"""
    return _active_incident_sessions.get(session_id)

def clear_active_incident(session_id: str):
    """Clear active incident for a session"""
    if session_id in _active_incident_sessions:
        incident_id = _active_incident_sessions[session_id]
        if incident_id in _kb_context_cache:
            del _kb_context_cache[incident_id]
        del _active_incident_sessions[session_id]
        logger.info(f"Cleared active incident for session {session_id}")

async def clear_session_history(session_id: str):
    """Clear session data"""
    if session_id in _conversation_history:
        del _conversation_history[session_id]
    if session_id in _incident_context:
        del _incident_context[session_id]
    if session_id in _active_incident_sessions:
        clear_active_incident(session_id)
    logger.info(f"Cleared session history for {session_id}")

async def get_session_history(session_id: str):
    return _conversation_history.get(session_id, [])

def get_incident_context(session_id: str):
    return _incident_context.get(session_id, {})