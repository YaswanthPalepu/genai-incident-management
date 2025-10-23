// frontend/src/services/api.js - UPDATED WITH ADMIN MESSAGE SUPPORT
import axios from 'axios';

const BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000
});

// User APIs
export const chatWithAI = (session_id, query) => {
  return api.post('/user/chat', { session_id, query });
};

export const endSession = (sessionData) => {
  return api.post('/user/end_session', sessionData);
};

// Admin APIs
export const getAllIncidents = () => {
  return api.get('/admin/incidents');
};

export const getIncidentDetails = (incidentId) => {
  return api.get(`/admin/incidents/${incidentId}`);
};

export const updateIncidentStatus = (incidentId, status, kb_reference = null, admin_message = null) => {
  const updateData = { status };
  if (kb_reference) {
    updateData.kb_reference = kb_reference;
  }
  if (admin_message) {
    updateData.admin_message = admin_message;
  }
  return api.put(`/admin/incidents/${incidentId}`, updateData);
};

export const getKnowledgeBaseContent = () => {
  return api.get('/admin/knowledge_base');
};

export const updateKnowledgeBase = (kb_content) => {
  return api.post('/admin/knowledge_base', { kb_content });
};

export const getAdminStats = () => {
  return api.get('/admin/stats');
};

// Error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      console.error('API Error:', error.response.data);
    } else if (error.request) {
      console.error('No response received:', error.request);
    } else {
      console.error('Error:', error.message);
    }
    return Promise.reject(error);
  }
);

export default api;