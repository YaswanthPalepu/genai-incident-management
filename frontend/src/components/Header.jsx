// frontend/src/components/Header.jsx - FIXED
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

function Header({ onNewConversation, conversationActive }) {
  const navigate = useNavigate();
  const location = useLocation();
  const isUserInterface = location.pathname === '/user';
  const isAdminInterface = location.pathname === '/admin';

  return (
    <div className="header">
      <div className="header-content">
        <div className="header-left">
          <h1 className="app-title">
            <span className="app-icon">🔧</span>
            IT Incident Assistant
          </h1>
          <p className="app-subtitle">AI-powered IT support and incident resolution</p>
        </div>
        
        <div className="header-right">
          {/* Only show User button in Admin interface */}
          {isAdminInterface && (
            <button 
              className="nav-button user-button"
              onClick={() => navigate('/user')}
              title="User Interface"
            >
              👤 User
            </button>
          )}
          
          {/* Only show Admin button in Login page, not in User interface */}
          {!isUserInterface && !isAdminInterface && (
            <button 
              className="nav-button admin-button"
              onClick={() => navigate('/admin/login')}
              title="Admin Dashboard"
            >
              ⚙️ Admin
            </button>
          )}
          
          {/* Show New Chat only once in User interface */}
          {isUserInterface && conversationActive && (
            <button 
              className="new-chat-button"
              onClick={onNewConversation}
              title="Start new conversation"
            >
              🗨️ New Chat
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default Header;