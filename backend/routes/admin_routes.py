from fastapi import APIRouter, HTTPException
from models import IncidentUpdate, AdminKBUpdate
from db.mongodb import get_all_incidents, get_incident, update_incident
from services.kb_service import update_knowledge_base_file, get_knowledge_base_content
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/incidents")
async def get_incidents():
    """Get all incidents for admin view"""
    try:
        incidents = await get_all_incidents()
        return incidents
    except Exception as e:
        logger.error(f"Error getting incidents: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve incidents")

@router.get("/incidents/{incident_id}")
async def get_incident_details(incident_id: str):
    """Get specific incident details"""
    try:
        incident = await get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        return incident
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting incident details: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve incident details")

@router.put("/incidents/{incident_id}")
async def update_incident_status(incident_id: str, incident_update: IncidentUpdate):
    """Admin update incident status"""
    try:
        update_data = incident_update.dict(exclude_unset=True)
        
        success = await update_incident(incident_id, update_data)
        if not success:
            raise HTTPException(status_code=404, detail="Incident not found or no changes made")
        
        return {"message": "Incident updated successfully", "incident_id": incident_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating incident: {e}")
        raise HTTPException(status_code=500, detail="Failed to update incident")

@router.get("/knowledge_base")
async def get_kb_content():
    """Get current knowledge base content"""
    try:
        content = get_knowledge_base_content()
        return {"kb_content": content}
    except Exception as e:
        logger.error(f"Error getting KB content: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve knowledge base content")

@router.post("/knowledge_base")
async def update_kb(kb_update: AdminKBUpdate):
    """Update knowledge base"""
    try:
        success = update_knowledge_base_file(kb_update.kb_content)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update knowledge base file and re-vectorize.")
        return {"message": "Knowledge base updated and re-vectorized successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating KB: {e}")
        raise HTTPException(status_code=500, detail="Failed to update knowledge base")