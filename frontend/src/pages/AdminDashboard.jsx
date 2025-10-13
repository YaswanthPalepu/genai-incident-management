// frontend/src/pages/AdminDashboard.jsx - REFACTORED (Key sections)
import React, { useState, useEffect } from 'react';
import {
  getAllIncidents,
  getIncidentDetails,
  updateIncidentStatus,
  getKnowledgeBaseContent,
  updateKnowledgeBase,
  getAdminStats
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
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchIncidents();
    fetchKbContent();
    fetchStats();
  }, []);

  const fetchIncidents = async () => {
    try {
      setIsLoading(true);
      const response = await getAllIncidents();
      setIncidents(response.data.incidents || []);
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

  const fetchStats = async () => {
    try {
      const response = await getAdminStats();
      setStats(response.data.stats);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const handleIncidentClick = async (incidentId) => {
    try {
      const response = await getIncidentDetails(incidentId);
      setSelectedIncident(response.data.incident);
    } catch (error) {
      console.error('Error fetching incident details:', error);
      alert('Failed to load incident details.');
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
      alert('Failed to update incident status.');
    }
  };

  const handleUpdateKb = async () => {
    if (!kbContent.trim()) {
      setKbMessage('Knowledge Base content cannot be empty.');
      return;
    }

    setIsUpdatingKb(true);
    setKbMessage('');
    try {
      await updateKnowledgeBase(kbContent);
      setKbMessage('Knowledge Base updated and re-indexed successfully!');
      setTimeout(() => setKbMessage(''), 3000);
    } catch (error) {
      console.error('Error updating KB:', error);
      setKbMessage('Failed to update Knowledge Base. Please check the backend.');
    } finally {
      setIsUpdatingKb(false);
    }
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
      'New': '#6c757d',
      'Pending Information': '#ffa726',
      'In Progress': '#42a5f5',
      'Resolved': '#66bb6a',
      'Open': '#ff7043',
      'Pending Admin Review': '#d32f2f'
    };
    return colors[status] || '#78909c';
  };

  return (
    <div className="full-page-container">
      <div className="card admin-card">
        <div className="admin-header">
          <div className="admin-title">
            <h1>Admin Dashboard</h1>
            <p>Manage incidents and knowledge base</p>
          </div>
        </div>

        {stats && (
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-number">{stats.total_incidents}</div>
              <div className="stat-label">Total Incidents</div>
            </div>
            {Object.entries(stats.by_status).map(([status, count]) => (
              <div key={status} className="stat-card">
                <div className="stat-number">{count}</div>
                <div className="stat-label">{status}</div>
              </div>
            ))}
          </div>
        )}

        <div className="admin-dashboard-layout">
          <div className="kb-editor-section">
            <div className="section-header">
              <h2>Knowledge Base</h2>
              <button 
                onClick={fetchKbContent} 
                className="refresh-button"
                title="Reload KB content"
              >
                Refresh
              </button>
            </div>
            
            <div className="kb-editor-container">
              <textarea
                value={kbContent}
                onChange={(e) => setKbContent(e.target.value)}
                placeholder="Enter KB content with [KB_ID: X] format..."
                className="kb-textarea"
              />
              <div className="kb-actions">
                <button 
                  onClick={handleUpdateKb} 
                  disabled={isUpdatingKb}
                  className="update-kb-button"
                >
                  {isUpdatingKb ? 'Updating...' : 'Update Knowledge Base'}
                </button>
                {kbContent && (
                  <span className="kb-stats">
                    {kbContent.split('\n').filter(line => line.trim()).length} lines
                  </span>
                )}
              </div>
              {kbMessage && (
                <div className={`kb-message ${kbMessage.includes('successfully') ? 'success' : 'error'}`}>
                  {kbMessage}
                </div>
              )}
            </div>
          </div>

          <div className="incidents-section">
            <div className="section-header">
              <h2>Incidents ({filteredIncidents.length})</h2>
              <div className="incident-controls">
                <input
                  type="text"
                  placeholder="Search incidents..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="search-input"
                />
                <select 
                  value={filterStatus} 
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="status-filter"
                >
                  <option value="">All Status</option>
                  <option value="New">New</option>
                  <option value="Pending Information">Pending Information</option>
                  <option value="In Progress">In Progress</option>
                  <option value="Resolved">Resolved</option>
                  <option value="Open">Open</option>
                  <option value="Pending Admin Review">Pending Admin Review</option>
                </select>
                <button 
                  onClick={fetchIncidents} 
                  className="refresh-button"
                >
                  Refresh
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
                <p>No incidents found</p>
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
                        <td className="user-demand">
                          {incident.user_demand.substring(0, 50)}...
                        </td>
                        <td>
                          <span 
                            className="status-badge"
                            style={{ backgroundColor: getStatusColor(incident.status) }}
                          >
                            {incident.status}
                          </span>
                        </td>
                        <td>
                          {new Date(incident.created_on).toLocaleDateString()}
                        </td>
                        <td className="action-buttons">
                          <button 
                            className="view-button"
                            onClick={() => handleIncidentClick(incident.incident_id)}
                          >
                            View
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

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

function IncidentDetailsModal({ incident, onClose, onStatusChange, getStatusColor }) {
  const [newStatus, setNewStatus] = useState(incident.status);

  const handleSaveStatus = () => {
    onStatusChange(incident.incident_id, newStatus);
  };

  return (
    <div className="incident-details-modal">
      <div className="modal-content">
        <button className="close-button" onClick={onClose}>&times;</button>
        <h3>Incident: {incident.incident_id}</h3>
        
        <div className="incident-summary">
          <div className="summary-item">
            <strong>Issue:</strong>
            <p>{incident.user_demand}</p>
          </div>
          
          <div className="summary-item">
            <strong>Status:</strong>
            <span 
              className="status-badge"
              style={{ backgroundColor: getStatusColor(incident.status) }}
            >
              {incident.status}
            </span>
          </div>

          <div className="status-select">
            <strong>Update Status:</strong>
            <select value={newStatus} onChange={(e) => setNewStatus(e.target.value)}>
              <option value="New">New</option>
              <option value="Pending Information">Pending Information</option>
              <option value="In Progress">In Progress</option>
              <option value="Resolved">Resolved</option>
              <option value="Open">Open</option>
              <option value="Pending Admin Review">Pending Admin Review</option>
            </select>
            <button onClick={handleSaveStatus} className="update-status-btn">
              Update
            </button>
          </div>

          <div className="summary-grid">
            <div className="grid-item">
              <strong>Created:</strong>
              <span>{new Date(incident.created_on).toLocaleString()}</span>
            </div>
            <div className="grid-item">
              <strong>Updated:</strong>
              <span>{new Date(incident.updated_on).toLocaleString()}</span>
            </div>
            {incident.kb_reference && (
              <div className="grid-item">
                <strong>KB Reference:</strong>
                <span>{incident.kb_reference}</span>
              </div>
            )}
          </div>
        </div>

        <h4>Conversation History:</h4>
        <div className="modal-conversation-history">
          {incident.additional_info && incident.additional_info.length > 0 ? (
            incident.additional_info.map((msg, index) => (
              <div key={index} className={`conversation-message ${msg.sender.toLowerCase()}`}>
                <div className="message-header">
                  <strong>{msg.sender}:</strong>
                  <span>{new Date(msg.timestamp).toLocaleTimeString()}</span>
                </div>
                <div className="message-content">{msg.text}</div>
              </div>
            ))
          ) : (
            <p>No conversation history.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;