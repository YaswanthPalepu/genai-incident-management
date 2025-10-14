// frontend/src/pages/UserUI.jsx - REFACTORED
import React, { useState, useEffect } from 'react';
import { chatWithAI, endSession } from '../services/api';
import ChatWindow from '../components/ChatWindow';
import MessageInput from '../components/MessageInput';
import Header from '../components/Header';

function UserUI() {
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [incidentInfo, setIncidentInfo] = useState({ 
    id: null, 
    status: null,
    kb_reference: null 
  });
  const [conversationActive, setConversationActive] = useState(false);
  const [connectionError, setConnectionError] = useState(false);

  useEffect(() => {
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    
    const welcomeMessage = {
      id: Date.now(),
      sender: 'AI',
      text: 'Hello! I\'m your IT Incident Assistant. Please describe any IT issues you\'re experiencing, and I\'ll help you resolve them.',
      timestamp: new Date().toISOString()
    };
    setMessages([welcomeMessage]);
  }, []);

  const generateSessionId = () => {
    return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
  };

  const handleSendMessage = async (text) => {
    if (!text.trim() || isLoading) return;

    const userMessage = {
        id: Date.now(),
        sender: 'User',
        text: text.trim(),
        timestamp: new Date().toISOString()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setConnectionError(false);
    setConversationActive(true);

    try {
        const response = await chatWithAI(sessionId, text.trim());
        const { response: aiResponse, incident_id, status, show_incident_info } = response.data;

        // Update incident info if provided - only when show_incident_info is true
        if (incident_id) {
            setIncidentInfo({ 
                id: incident_id, 
                status: status,
                kb_reference: response.data.kb_reference || null
            });
        } else if (incident_id) {
            // Update status only without forcing the info bar to show
            setIncidentInfo(prev => ({ 
                ...prev, 
                status: status 
            }));
        }

        // Add AI response
        const aiMessage = {
            id: Date.now() + 1,
            sender: 'AI',
            text: aiResponse,
            timestamp: new Date().toISOString()
        };
        
        setMessages(prev => [...prev, aiMessage]);

    } catch (error) {
        console.error('Error sending message:', error);
        setConnectionError(true);
        
        const errorMessage = {
            id: Date.now() + 1,
            sender: 'AI',
            text: 'Sorry, I encountered a connection error. Please ensure the backend server is running on port 8000 and try again.',
            timestamp: new Date().toISOString()
        };
        
        setMessages(prev => [...prev, errorMessage]);
    } finally {
        setIsLoading(false);
    }
  };
  const handleEndSession = async () => {
    if (sessionId) {
      try {
        await endSession({ session_id: sessionId });
      } catch (error) {
        console.error('Error ending session:', error);
      }
    }
    
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    setIncidentInfo({ id: null, status: null, kb_reference: null });
    setConversationActive(false);
    setConnectionError(false);
    
    const welcomeMessage = {
      id: Date.now(),
      sender: 'AI',
      text: 'New session started. How can I help you with your IT issues today?',
      timestamp: new Date().toISOString()
    };
    
    setMessages([welcomeMessage]);
  };

  const handleNewConversation = () => {
    if (conversationActive && messages.length > 1) {
      if (window.confirm('Start a new conversation? Your current session will be saved as an incident.')) {
        handleEndSession();
      }
    } else {
      handleEndSession();
    }
  };

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
      <div className="card chat-card">
        <Header 
          onNewConversation={handleNewConversation}
          conversationActive={conversationActive}
        />
        
        {incidentInfo.id && (
          <div className="incident-info-bar">
            <div className="incident-details">
              <div className="incident-id">
                <strong>🆔 Incident:</strong> {incidentInfo.id}
              </div>
              <div className="incident-meta">
                <span 
                  className="incident-status"
                  style={{ backgroundColor: getStatusColor(incidentInfo.status), color: 'white' }}
                >
                  {incidentInfo.status}
                </span>
                {incidentInfo.kb_reference && (
                  <span className="kb-reference">
                    📚 {incidentInfo.kb_reference}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {connectionError && (
          <div className="error-banner">
            ⚠️ Connection issue detected. Please ensure the backend server is running on port 8000.
          </div>
        )}

        <div className="chat-area">
          <ChatWindow messages={messages} />
          <MessageInput 
            onSendMessage={handleSendMessage} 
            isLoading={isLoading}
            placeholder="Describe your IT issue..."
          />
        </div>

        <div className="quick-actions">
          <button 
            className="new-conversation-btn"
            onClick={handleNewConversation}
            title="Start new conversation"
          >
            New Chat
          </button>
        </div>

        <div className="session-info">
          <small>Session: {sessionId?.substring(0, 20)}...</small>
        </div>
      </div>
    </div>
  );
}

export default UserUI;