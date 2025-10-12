# backend/admin_routes.py - REFACTORED
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
        return {
            "success": True,
            "count": len(incidents),
            "incidents": incidents
        }
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
        return {
            "success": True,
            "incident": incident
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting incident details: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve incident details")

@router.put("/incidents/{incident_id}")
async def update_incident_status(incident_id: str, incident_update: IncidentUpdate):
    """Update incident status"""
    try:
        update_data = incident_update.dict(exclude_unset=True)
        update_data["updated_on"] = datetime.utcnow()
        
        success = await update_incident(incident_id, update_data)
        if not success:
            raise HTTPException(status_code=404, detail="Incident not found")
        
        updated = await get_incident(incident_id)
        return {
            "success": True,
            "message": "Incident updated successfully",
            "incident": updated
        }
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
        return {
            "success": True,
            "kb_content": content
        }
    except Exception as e:
        logger.error(f"Error getting KB content: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve knowledge base")

@router.post("/knowledge_base")
async def update_kb(kb_update: AdminKBUpdate):
    """Update knowledge base and re-vectorize"""
    try:
        success = update_knowledge_base_file(kb_update.kb_content)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update and vectorize KB")
        
        return {
            "success": True,
            "message": "Knowledge base updated and re-vectorized successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating KB: {e}")
        raise HTTPException(status_code=500, detail="Failed to update knowledge base")

@router.get("/stats")
async def get_admin_stats():
    """Get dashboard statistics"""
    try:
        incidents = await get_all_incidents()
        
        stats = {
            "total_incidents": len(incidents),
            "by_status": {},
            "recent_incidents": incidents[:5]
        }
        
        # Count by status
        for incident in incidents:
            status = incident.get('status', 'Unknown')
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
        
        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")