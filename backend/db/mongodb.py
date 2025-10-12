# backend/db/mongodb.py - REFACTORED (Key sections)
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from config import MONGO_DETAILS, DB_NAME
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(MONGO_DETAILS)
db = client[DB_NAME]
incidents_collection = db["incidents"]

def serialize_document(doc):
    """Convert MongoDB document to JSON-serializable format"""
    if not doc:
        return None
    
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])
    
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
        elif isinstance(value, list):
            # Handle list of dicts (messages)
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if isinstance(v, datetime):
                            item[k] = v.isoformat()
    
    return doc

async def create_incident(incident_data: dict) -> bool:
    """Create new incident in MongoDB"""
    try:
        if 'created_on' not in incident_data:
            incident_data['created_on'] = datetime.utcnow()
        if 'updated_on' not in incident_data:
            incident_data['updated_on'] = datetime.utcnow()
        
        result = await incidents_collection.insert_one(incident_data)
        logger.info(f"Created incident: {incident_data.get('incident_id')}")
        return True
    
    except Exception as e:
        logger.error(f"Error creating incident: {e}")
        return False

async def get_incident(incident_id: str):
    """Get single incident by ID"""
    try:
        incident = await incidents_collection.find_one({"incident_id": incident_id})
        return serialize_document(incident)
    except Exception as e:
        logger.error(f"Error getting incident: {e}")
        return None

async def get_all_incidents():
    """Get all incidents sorted by creation date"""
    try:
        cursor = incidents_collection.find().sort("created_on", -1)
        incidents = []
        async for document in cursor:
            incidents.append(serialize_document(document))
        return incidents
    except Exception as e:
        logger.error(f"Error getting all incidents: {e}")
        return []

async def update_incident(incident_id: str, update_data: dict) -> bool:
    """Update incident in MongoDB"""
    try:
        update_data["updated_on"] = datetime.utcnow()
        
        result = await incidents_collection.update_one(
            {"incident_id": incident_id},
            {"$set": update_data}
        )
        
        success = result.modified_count > 0
        if success:
            logger.info(f"Updated incident: {incident_id}")
        else:
            logger.warning(f"Incident not found or no changes: {incident_id}")
        
        return success
    
    except Exception as e:
        logger.error(f"Error updating incident: {e}")
        return False

async def delete_incident(incident_id: str) -> bool:
    """Delete incident from MongoDB"""
    try:
        result = await incidents_collection.delete_one({"incident_id": incident_id})
        return result.deleted_count > 0
    except Exception as e:
        logger.error(f"Error deleting incident: {e}")
        return False
