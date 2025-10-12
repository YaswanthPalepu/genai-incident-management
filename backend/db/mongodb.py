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
    
    # Convert ObjectId to string and remove it from the document
    if '_id' in doc:
        doc['_id'] = str(doc['_id'])
    
    # Convert any other ObjectId fields if they exist
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            # Ensure datetime is in ISO format
            doc[key] = value.isoformat()
    
    return doc

async def create_incident(incident_data: dict):
    """Create a new incident"""
    try:
        # Ensure timestamps are properly set
        if 'created_on' not in incident_data:
            incident_data['created_on'] = datetime.utcnow()
        if 'updated_on' not in incident_data:
            incident_data['updated_on'] = datetime.utcnow()
            
        result = await incidents_collection.insert_one(incident_data)
        logger.info(f"Created incident with ID: {incident_data['incident_id']}")
        return True
    except Exception as e:
        logger.error(f"Error creating incident: {e}")
        return False

async def get_incident(incident_id: str):
    """Get incident by ID"""
    try:
        incident = await incidents_collection.find_one({"incident_id": incident_id})
        return serialize_document(incident)
    except Exception as e:
        logger.error(f"Error getting incident: {e}")
        return None

async def get_all_incidents():
    """Get all incidents"""
    try:
        cursor = incidents_collection.find().sort("created_on", -1)
        incidents = []
        async for document in cursor:
            incidents.append(serialize_document(document))
        return incidents
    except Exception as e:
        logger.error(f"Error getting all incidents: {e}")
        return []

async def update_incident(incident_id: str, update_data: dict):
    """Update incident"""
    try:
        # Always update the updated_on timestamp
        update_data["updated_on"] = datetime.utcnow()
        
        result = await incidents_collection.update_one(
            {"incident_id": incident_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error(f"Error updating incident: {e}")
        return False

async def delete_incident(incident_id: str):
    """Delete incident by ID"""
    try:
        result = await incidents_collection.delete_one({"incident_id": incident_id})
        return result.deleted_count > 0
    except Exception as e:
        logger.error(f"Error deleting incident: {e}")
        return False