from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

class Message(BaseModel):
    sender: str
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Incident(BaseModel):
    incident_id: str
    user_demand: str
    additional_info: List[Message] = []
    status: str = "Pending Information"
    created_on: datetime = Field(default_factory=datetime.utcnow)
    updated_on: datetime = Field(default_factory=datetime.utcnow)
    kb_reference: Optional[str] = None

class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    kb_reference: Optional[str] = None

class UserQuery(BaseModel):
    session_id: Optional[str] = None
    query: str

class AdminKBUpdate(BaseModel):
    kb_content: str