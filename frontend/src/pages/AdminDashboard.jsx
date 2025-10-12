import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getAllIncidents,
  getIncidentDetails,
  updateIncidentStatus,
  getKnowledgeBaseContent,
  updateKnowledgeBase
} from '../services/api';

function AdminDashboard({ setAuth }) {
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [filterStatus, setFilterStatus] = useState('');
  const [kbContent, setKbContent] = useState('');
  const [isUpdatingKb, setIsUpdatingKb] = useState(false);
  const [kbMessage, setKbMessage] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    fetchIncidents();
    fetchKbContent();
  }, []);

  const fetchIncidents = async () => {
    try {
      setIsLoading(true);
      const response = await getAllIncidents();
      setIncidents(response.data);
    } catch (error) {
      console.error('Error fetching incidents:', error);
      alert('Failed to fetch incidents. Please check if the backend is running.');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchKbContent = async () => {
    try {
      const response = await getKnowledgeBaseContent();
      setKbContent(response.data.kb_content);
    } catch (error) {
      console.error('Error fetching KB content:', error);
    }
  };

  const handleIncidentClick = async (incidentId) => {
    try {
      console.log('Fetching incident details for:', incidentId);
      const response = await getIncidentDetails(incidentId);
      console.log('Incident details:', response.data);
      setSelectedIncident(response.data);
    } catch (error) {
      console.error('Error fetching incident details:', error);
      alert('Failed to load incident details. Please check the console for errors.');
    }
  };

  const handleStatusChange = async (incidentId, newStatus) => {
    try {
      await updateIncidentStatus(incidentId, newStatus);
      fetchIncidents();
      if (selectedIncident && selectedIncident.incident_id === incidentId) {
        setSelectedIncident(prev => ({ ...prev, status: newStatus }));
      }
    } catch (error) {
      console.error('Error updating incident status:', error);
    }
  };

  const handleUpdateKb = async () => {
    if (!kbContent.trim()) {
      setKbMessage('❌ Knowledge Base content cannot be empty.');
      return;
    }

    setIsUpdatingKb(true);
    setKbMessage('');
    try {
      await updateKnowledgeBase(kbContent);
      setKbMessage('✅ Knowledge Base updated and re-indexed successfully!');
      setTimeout(() => setKbMessage(''), 3000);
    } catch (error) {
      console.error('Error updating KB:', error);
      setKbMessage('❌ Failed to update Knowledge Base. Please check the backend.');
    } finally {
      setIsUpdatingKb(false);
    }
  };

  const handleLogout = () => {
    setAuth(false);
    navigate('/admin/login');
  };

  const filteredIncidents = incidents.filter(incident => {
    const matchesStatus = filterStatus ? incident.status === filterStatus : true;
    const matchesSearch = searchTerm 
      ? incident.incident_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        incident.user_demand.toLowerCase().includes(searchTerm.toLowerCase())
      : true;
    return matchesStatus && matchesSearch;
  });

  const getStatusColor = (status) => {
    const colors = {
      'Pending Information': '#ffa726',
      'In Progress': '#42a5f5',
      'Pending Admin Review': '#ff7043',
      'Resolved': '#66bb6a',
      'Closed': '#78909c'
    };
    return colors[status] || '#78909c';
  };

  return (
    <div className="full-page-container">
      <div className="card admin-card">
        {/* Header */}
        <div className="admin-header">
          <div className="admin-title">
            <h1>🛠️ Admin Dashboard</h1>
            <p>Manage incidents and knowledge base</p>
          </div>
          <button 
            onClick={handleLogout} 
            className="logout-button"
            title="Logout from admin"
          >
            🚪 Logout
          </button>
        </div>

        <div className="admin-dashboard-layout">
          {/* Knowledge Base Editor */}
          <div className="kb-editor-section">
            <div className="section-header">
              <h2>📚 Knowledge Base</h2>
              <div className="section-actions">
                <button 
                  onClick={fetchKbContent} 
                  className="refresh-button"
                  title="Reload KB content"
                >
                  🔄
                </button>
              </div>
            </div>
            
            <div className="kb-editor-container">
              <textarea
                value={kbContent}
                onChange={(e) => setKbContent(e.target.value)}
                placeholder="Enter your knowledge base content here. Use [KB_ID: X] format for entries..."
                className="kb-textarea"
              />
              <div className="kb-actions">
                <button 
                  onClick={handleUpdateKb} 
                  disabled={isUpdatingKb}
                  className="update-kb-button"
                >
                  {isUpdatingKb ? '⏳ Updating...' : '💾 Update Knowledge Base'}
                </button>
                <div className="kb-stats">
                  {kbContent && (
                    <span>
                      📊 {kbContent.split('\n').filter(line => line.trim()).length} lines
                    </span>
                  )}
                </div>
              </div>
              {kbMessage && (
                <div className={`kb-message ${kbMessage.includes('✅') ? 'success' : 'error'}`}>
                  {kbMessage}
                </div>
              )}
            </div>
          </div>

          {/* Incidents Section */}
          <div className="incidents-section">
            <div className="section-header">
              <h2>📋 Incidents ({filteredIncidents.length})</h2>
              <div className="incident-controls">
                <div className="search-box">
                  <input
                    type="text"
                    placeholder="Search incidents..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="search-input"
                  />
                </div>
                <select 
                  value={filterStatus} 
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="status-filter"
                >
                  <option value="">All Status</option>
                  <option value="Pending Information">Pending Information</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Pending Admin Review">Pending Admin Review</option>
                  <option value="Resolved">Resolved</option>
                  <option value="Closed">Closed</option>
                </select>
                <button 
                  onClick={fetchIncidents} 
                  className="refresh-button"
                  title="Refresh incidents"
                >
                  🔄
                </button>
              </div>
            </div>

            {isLoading ? (
              <div className="loading-state">
                <div className="loading-spinner"></div>
                <p>Loading incidents...</p>
              </div>
            ) : filteredIncidents.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">📭</div>
                <h3>No incidents found</h3>
                <p>
                  {searchTerm || filterStatus 
                    ? 'Try adjusting your search or filter criteria.'
                    : 'No incidents have been created yet.'
                  }
                </p>
              </div>
            ) : (
              <div className="incidents-table-container">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Incident ID</th>
                      <th>User Issue</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredIncidents.map((incident) => (
                      <tr key={incident.incident_id}>
                        <td className="incident-id">{incident.incident_id}</td>
                        <td className="user-demand" title={incident.user_demand}>
                          {incident.user_demand.length > 50 
                            ? incident.user_demand.substring(0, 50) + '...'
                            : incident.user_demand
                          }
                        </td>
                        <td>
                          <span 
                            className="status-badge"
                            style={{ backgroundColor: getStatusColor(incident.status) }}
                          >
                            {incident.status}
                          </span>
                        </td>
                        <td className="created-time">
                          {new Date(incident.created_on).toLocaleDateString()}
                        </td>
                        <td className="action-buttons">
                          <button 
                            className="view-button"
                            onClick={() => handleIncidentClick(incident.incident_id)}
                            title="View details"
                          >
                            👁️ View
                          </button>
                          {incident.status !== 'Resolved' && incident.status !== 'Closed' ? (
                            <button 
                              className="resolve-button"
                              onClick={() => handleStatusChange(incident.incident_id, 'Resolved')}
                              title="Mark as resolved"
                            >
                              ✅ Resolve
                            </button>
                          ) : (
                            <button 
                              className="reopen-button"
                              onClick={() => handleStatusChange(incident.incident_id, 'In Progress')}
                              title="Reopen incident"
                            >
                              🔄 Reopen
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Incident Details Modal */}
        {selectedIncident && (
          <IncidentDetailsModal
            incident={selectedIncident}
            onClose={() => setSelectedIncident(null)}
            onStatusChange={handleStatusChange}
            getStatusColor={getStatusColor}
          />
        )}
      </div>
    </div>
  );
}

// Incident Details Modal Component
function IncidentDetailsModal({ incident, onClose, onStatusChange, getStatusColor }) {
  const [newStatus, setNewStatus] = useState(incident.status);

  const handleSaveStatus = () => {
    onStatusChange(incident.incident_id, newStatus);
  };

  return (
    <div className="incident-details-modal">
      <div className="modal-content">
        <button className="close-button" onClick={onClose}>&times;</button>
        <h3>Incident Details: {incident.incident_id}</h3>
        
        <div className="incident-summary">
          <div className="summary-item">
            <strong>User Issue:</strong>
            <p>{incident.user_demand}</p>
          </div>
          
          <div className="summary-item">
            <strong>Current Status:</strong>
            <span 
              className="status-badge"
              style={{ backgroundColor: getStatusColor(incident.status) }}
            >
              {incident.status}
            </span>
          </div>

          <div className="status-select">
            <strong>Update Status:</strong>
            <div className="status-controls">
              <select value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
                <option value="Pending Information">Pending Information</option>
                <option value="In Progress">In Progress</option>
                <option value="Pending Admin Review">Pending Admin Review</option>
                <option value="Resolved">Resolved</option>
                <option value="Closed">Closed</option>
              </select>
              <button onClick={handleSaveStatus} className="update-status-btn">
                Update
              </button>
            </div>
          </div>

          <div className="summary-grid">
            <div className="grid-item">
              <strong>Created On:</strong>
              <span>{new Date(incident.created_on).toLocaleString()}</span>
            </div>
            <div className="grid-item">
              <strong>Updated On:</strong>
              <span>{new Date(incident.updated_on).toLocaleString()}</span>
            </div>
            <div className="grid-item">
              <strong>KB Reference:</strong>
              <span>{incident.kb_reference || 'N/A'}</span>
            </div>
          </div>
        </div>

        <h4>Conversation History:</h4>
        <div className="modal-conversation-history">
          {incident.additional_info && incident.additional_info.length > 0 ? (
            incident.additional_info.map((msg, index) => (
              <div key={index} className={`conversation-message ${msg.sender.toLowerCase()}`}>
                <div className="message-header">
                  <strong>{msg.sender}:</strong>
                  <span className="message-time">
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div className="message-content">{msg.text}</div>
              </div>
            ))
          ) : (
            <p>No conversation history available.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;