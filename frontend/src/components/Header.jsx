import React from 'react';
import { useNavigate } from 'react-router-dom';

function Header({ onNewConversation, conversationActive }) {
  const navigate = useNavigate();

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
          <button 
            className="nav-button user-button"
            onClick={() => navigate('/user')}
            title="User Interface"
          >
            👤 User
          </button>
          <button 
            className="nav-button admin-button"
            onClick={() => navigate('/admin/login')}
            title="Admin Dashboard"
          >
            ⚙️ Admin
          </button>
          {conversationActive && (
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