// frontend/src/components/ChatWindow.jsx - REFACTORED
import React, { useRef, useEffect } from 'react';

function ChatWindow({ messages }) {
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const formatMessageText = (text) => {
    return text.split('\n').map((line, index) => {
      // Highlight incident IDs and statuses
      if (line.includes('INC') || line.includes('Incident ID') || line.includes('Status')) {
        return (
          <div key={index} className="highlighted-line">
            {line}
          </div>
        );
      }
      return (
        <div key={index}>
          {line}
        </div>
      );
    });
  };

  return (
    <div className="chat-window">
      {messages.length === 0 ? (
        <div className="empty-chat">
          <div className="empty-chat-icon">💬</div>
          <h3>Start a Conversation</h3>
          <p>Describe your IT issue to get started with incident resolution.</p>
        </div>
      ) : (
        messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.sender.toLowerCase()}`}>
            <div className="message-header">
              <span className="message-sender">
                {msg.sender === 'AI' ? '🤖 IT Assistant' : '👤 You'}
              </span>
              <span className="message-time">
                {new Date(msg.timestamp).toLocaleTimeString([], { 
                  hour: '2-digit', 
                  minute: '2-digit' 
                })}
              </span>
            </div>
            <div className="message-content">
              {formatMessageText(msg.text)}
            </div>
          </div>
        ))
      )}
      <div ref={messagesEndRef} />
    </div>
  );
}

export default ChatWindow;
