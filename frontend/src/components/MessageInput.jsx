import React, { useState } from 'react';

function MessageInput({ onSendMessage, isLoading, placeholder }) {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="message-input-container">
      <form onSubmit={handleSubmit} className="input-area">
        <div className="input-wrapper">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={placeholder || "Type your message..."}
            disabled={isLoading}
            maxLength={500}
          />
          <button 
            type="submit" 
            disabled={isLoading || !input.trim()}
            className="send-button"
            title="Send message"
          >
            {isLoading ? (
              <div className="loading-spinner"></div>
            ) : (
              '📤'
            )}
          </button>
        </div>
        <div className="input-footer">
          <span className="char-count">{input.length}/500</span>
          <span className="input-hint">Press Enter to send</span>
        </div>
      </form>
    </div>
  );
}

export default MessageInput;