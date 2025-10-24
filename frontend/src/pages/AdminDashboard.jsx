// frontend/src/components/AdminDashboard.jsx - UPDATED WITH COLLECTED_INFORMATION
import React, { useState, useEffect } from 'react';
import {
  getAllIncidents,
  getIncidentDetails,
  updateIncidentStatus,
  getKnowledgeBaseContent,
  updateKnowledgeBase,
  deleteIncident
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

  useEffect(() => {
    fetchIncidents();
    fetchKbContent();
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

  const handleIncidentClick = async (incidentId) => {
    try {
      const response = await getIncidentDetails(incidentId);
      setSelectedIncident(response.data.incident);
    } catch (error) {
      console.error('Error fetching incident details:', error);
      alert('Failed to load incident details.');
    }
  };

  const handleStatusChange = async (incidentId, newStatus, adminMessage) => {
    try {
      await updateIncidentStatus(incidentId, newStatus, null, adminMessage);
      fetchIncidents();
      if (selectedIncident && selectedIncident.incident_id === incidentId) {
        // Refresh the selected incident to show updated admin messages
        const response = await getIncidentDetails(incidentId);
        setSelectedIncident(response.data.incident);
      }
    } catch (error) {
      console.error('Error updating incident status:', error);
      alert('Failed to update incident status.');
    }
  };

  // --- NEW HANDLER FUNCTION FOR DELETION ---
  const handleDeleteIncident = async (incidentId) => {
    if (!window.confirm(`Are you sure you want to permanently delete incident ${incidentId}? This cannot be undone.`)) {
      return;
    }
    
    try {
      // NOTE: This assumes you have implemented deleteIncident in ../services/api
      await deleteIncident(incidentId); 
      alert(`Incident ${incidentId} deleted successfully.`);
      
      // Close modal if the deleted incident was selected
      if (selectedIncident && selectedIncident.incident_id === incidentId) {
        setSelectedIncident(null);
      }
      
      fetchIncidents(); // Refresh the list
    } catch (error) {
      console.error('Error deleting incident:', error);
      alert('Failed to delete incident. Check backend implementation.');
    }
  };
  // ----------------------------------------

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
      'Pending Information': '#ffa726',
      'Open': '#42a5f5',
      'Resolved': '#66bb6a',
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
                  <option value="Pending Information">Pending Information</option>
                  <option value="Pending Admin Review">Pending Admin Review</option>
                  <option value="Open">Open</option>
                  <option value="Resolved">Resolved</option>
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
                          <button 
                            className="delete-button"
                            onClick={() => handleDeleteIncident(incident.incident_id)}
                            title="Delete Incident"
                          >
                            Delete
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
            onDelete={handleDeleteIncident}
            getStatusColor={getStatusColor}
          />
        )}
      </div>
    </div>
  );
}

function IncidentDetailsModal({ incident, onClose, onStatusChange,onDelete, getStatusColor }) {
  const [newStatus, setNewStatus] = useState(incident.status);
  const [adminMessage, setAdminMessage] = useState('');
  const [showMessageInput, setShowMessageInput] = useState(false);

  const handleSaveStatus = () => {
    if (newStatus !== incident.status) {
      if (!adminMessage.trim()) {
        alert('Please provide a message describing this status change.');
        return;
      }
      onStatusChange(incident.incident_id, newStatus, adminMessage);
      setAdminMessage('');
      setShowMessageInput(false);
    } else {
      alert('Status has not changed. Please select a different status.');
    }
  };

  const handleStatusSelectChange = (e) => {
    setNewStatus(e.target.value);
    if (e.target.value !== incident.status) {
      setShowMessageInput(true);
    } else {
      setShowMessageInput(false);
      setAdminMessage('');
    }
  };

  return (
    <div className="incident-details-modal">
      <div className="modal-content">
        <button className="close-button" onClick={onClose}>&times;</button>
        <h3>Incident: {incident.incident_id}
        <button 
        className="delete-button-modal"
        onClick={() => onDelete(incident.incident_id)}
        title="Delete this Incident"
        >
        🗑️ Delete
        </button>
        </h3>
        
        <div className="incident-summary">
          <div className="summary-item">
            <strong>Issue:</strong>
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

          <div className="status-update-section">
            <strong>Update Status:</strong>
            <select value={newStatus} onChange={handleStatusSelectChange} className="status-select-input">
              <option value="Pending Information">Pending Information</option>
              <option value="Pending Admin Review">Pending Admin Review</option>
              <option value="Open">Open</option>
              <option value="Resolved">Resolved</option>
            </select>
            
            {showMessageInput && (
              <div className="admin-message-input-container">
                <label><strong>Admin Message (Required):</strong></label>
                <textarea
                  value={adminMessage}
                  onChange={(e) => setAdminMessage(e.target.value)}
                  placeholder="Enter a message describing this status change..."
                  className="admin-message-textarea"
                  rows="3"
                />
              </div>
            )}
            
            <button 
              onClick={handleSaveStatus} 
              className="update-status-btn"
              disabled={newStatus === incident.status}
            >
              Update Status
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

        {/* Admin Messages History */}
        {incident.admin_messages && incident.admin_messages.length > 0 && (
          <div className="admin-messages-section">
            <h4>📝 Admin Status Change History:</h4>
            <div className="admin-messages-list">
              {incident.admin_messages.map((msg, index) => (
                <div key={index} className="admin-message-item">
                  <div className="admin-message-header">
                    <span className="admin-message-time">
                      {new Date(msg.timestamp).toLocaleString()}
                    </span>
                    <span className="admin-message-status-change">
                      <span style={{ color: getStatusColor(msg.old_status) }}>
                        {msg.old_status}
                      </span>
                      {' → '}
                      <span style={{ color: getStatusColor(msg.new_status) }}>
                        {msg.new_status}
                      </span>
                    </span>
                  </div>
                  <div className="admin-message-content">
                    {msg.message}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Collected Information - Q&A pairs only */}
        <h4>📋 Collected Information (Q&A):</h4>
        <div className="collected-information-section">
          {incident.collected_information && incident.collected_information.length > 0 ? (
            incident.collected_information.map((qa, index) => (
              <div key={index} className="qa-pair">
                <div className="qa-question">
                  <strong>Q{index + 1}:</strong> {qa.question}
                </div>
                <div className="qa-answer">
                  <strong>A:</strong> {qa.answer}
                </div>
                <div className="qa-timestamp">
                  {new Date(qa.timestamp).toLocaleString()}
                </div>
              </div>
            ))
          ) : (
            <p className="no-data">No information collected yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;