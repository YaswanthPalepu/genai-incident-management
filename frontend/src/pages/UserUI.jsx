import React, { useState, useEffect, useRef } from 'react';
import { chatWithAI, endSession } from '../services/api';
import ChatWindow from '../components/ChatWindow';
import MessageInput from '../components/MessageInput';
import Header from '../components/Header';

function UserUI() {
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [incidentInfo, setIncidentInfo] = useState({ id: null, status: null });
  const [conversationActive, setConversationActive] = useState(false);
  const [connectionError, setConnectionError] = useState(false);

  // Initialize session on component mount
  useEffect(() => {
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    
    const welcomeMessage = {
      id: Date.now(),
      sender: 'AI',
      text: '👋 Hello! I\'m your IT Incident Assistant. Please describe your IT issue, and I\'ll help you resolve it step by step.',
      timestamp: new Date()
    };
    setMessages([welcomeMessage]);
  }, []);

  const generateSessionId = () => {
    return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
  };

  const handleSendMessage = async (text) => {
    if (!text.trim() || isLoading) return;

    // Add user message immediately
    const userMessage = {
      id: Date.now(),
      sender: 'User',
      text: text.trim(),
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setConnectionError(false);
    setConversationActive(true);

    try {
      const response = await chatWithAI(sessionId, text.trim());
      const { response: aiResponse, incident_id, status } = response.data;

      // Update incident info if provided
      if (incident_id) {
        setIncidentInfo({ id: incident_id, status });
      }

      // Add AI response
      const aiMessage = {
        id: Date.now() + 1,
        sender: 'AI',
        text: aiResponse,
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, aiMessage]);

      // Check if conversation should end
      if (aiResponse.includes('resolved') || aiResponse.includes('closed') || aiResponse.includes('completed')) {
        setTimeout(() => {
          handleEndSession();
        }, 3000);
      }

    } catch (error) {
      console.error('Error sending message:', error);
      setConnectionError(true);
      
      const errorMessage = {
        id: Date.now() + 1,
        sender: 'AI',
        text: '❌ Sorry, I encountered an error connecting to the server. Please check if the backend is running and try again.',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEndSession = async () => {
    if (sessionId) {
      try {
        await endSession(sessionId);
      } catch (error) {
        console.error('Error ending session:', error);
      }
    }
    
    // Reset conversation
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
    setIncidentInfo({ id: null, status: null });
    setConversationActive(false);
    setConnectionError(false);
    
    const welcomeMessage = {
      id: Date.now(),
      sender: 'AI',
      text: '🔄 Starting new session. How can I help you with your IT issues today?',
      timestamp: new Date()
    };
    
    setMessages([welcomeMessage]);
  };

  const handleNewConversation = () => {
    if (conversationActive && messages.length > 1) {
      if (window.confirm('Start a new conversation? Your current conversation will be saved as an incident.')) {
        handleEndSession();
      }
    } else {
      handleEndSession();
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      'Pending Info': '#ffa726',
      'Information Gathering': '#ffa726',
      'Open': '#42a5f5',
      'Solution in Progress': '#29b6f6',
      'Resolved': '#66bb6a',
      'Completed': '#66bb6a'
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
        
        {/* Incident Info Bar */}
        {incidentInfo.id && (
          <div className="incident-info-bar">
            <div className="incident-id">
              🆔 <strong>Incident:</strong> {incidentInfo.id}
            </div>
            <div 
              className="incident-status"
              style={{ color: getStatusColor(incidentInfo.status) }}
            >
              📊 <strong>Status:</strong> {incidentInfo.status}
            </div>
          </div>
        )}

        {/* Connection Error Banner */}
        {connectionError && (
          <div className="error-banner">
            ⚠️ Connection issue detected. Please ensure the backend server is running on port 8000.
          </div>
        )}

        {/* Chat Area */}
        <div className="chat-area">
          <ChatWindow messages={messages} />
          <MessageInput 
            onSendMessage={handleSendMessage} 
            isLoading={isLoading}
            placeholder="Describe your IT issue or question..."
          />
        </div>

        {/* Quick Actions */}
        <div className="quick-actions">
          <button 
            className="new-conversation-btn"
            onClick={handleNewConversation}
            title="Start new conversation"
          >
            🗨️ New Chat
          </button>
          {conversationActive && (
            <button 
              className="help-button"
              onClick={() => handleSendMessage('I need help with this issue.')}
              title="Get help"
            >
              ❓ Get Help
            </button>
          )}
        </div>

        {/* Session Info */}
        <div className="session-info">
          <small>Session: {sessionId?.substring(0, 15)}...</small>
        </div>
      </div>
    </div>
  );
}

export default UserUI;