# backend/models.py - UPDATED WITH NEW FIELDS
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime
import pytz 

class Message(BaseModel):
    sender: str  # "User" or "AI"
    text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(pytz.UTC).isoformat())

class AdminMessage(BaseModel):
    """Admin status change message"""
    timestamp: str
    old_status: str
    new_status: str
    message: str
    admin_id: Optional[str] = "admin"  # Can be extended for multi-admin support

class Incident(BaseModel):
    incident_id: str
    user_demand: str
    additional_info: List[Dict] = []  # Full conversation history
    collected_information: List[Dict] = []  # NEW: Only Q&A pairs
    status: str = "New"
    created_on: datetime = Field(default_factory=lambda: datetime.now(pytz.UTC).isoformat())
    updated_on: datetime = Field(default_factory=lambda: datetime.now(pytz.UTC).isoformat())
    kb_reference: Optional[str] = None
    priority: str = "Normal"
    admin_messages: List[Dict] = []  # NEW: Status change messages from admin

class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    kb_reference: Optional[str] = None
    priority: Optional[str] = None
    admin_message: Optional[str] = None  # NEW: Custom message from admin

class UserQuery(BaseModel):
    session_id: Optional[str] = None
    query: str

class AdminKBUpdate(BaseModel):
    kb_content: str

class SessionEndRequest(BaseModel):
    session_id: str