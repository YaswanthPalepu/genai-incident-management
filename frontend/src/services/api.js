import axios from 'axios';

const BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// User API
export const chatWithAI = (session_id, query) => {
  return api.post('/user/chat', { session_id, query });
};

export const endSession = (session_id) => {
  return api.post('/user/end_session', { session_id });
};

// Admin APIs
export const getAllIncidents = () => {
  return api.get('/admin/incidents');
};

export const getIncidentDetails = (incidentId) => {
  return api.get(`/admin/incidents/${incidentId}`);
};

export const updateIncidentStatus = (incidentId, status, kb_reference = null) => {
  const updateData = { status };
  if (kb_reference) {
    updateData.kb_reference = kb_reference;
  }
  return api.put(`/admin/incidents/${incidentId}`, updateData);
};

export const getKnowledgeBaseContent = () => {
  return api.get('/admin/knowledge_base');
};

export const updateKnowledgeBase = (kb_content) => {
  return api.post('/admin/knowledge_base', { kb_content });
};

// Add request interceptor for better error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;