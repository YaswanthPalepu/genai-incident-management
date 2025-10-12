import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import UserUI from './pages/UserUI';
import AdminDashboard from './pages/AdminDashboard';
import './index.css';

function App() {
  const [isAdminAuthenticated, setIsAdminAuthenticated] = React.useState(
    localStorage.getItem('isAdminAuthenticated') === 'true'
  );

  const setAuth = (isAuthenticated) => {
    setIsAdminAuthenticated(isAuthenticated);
    localStorage.setItem('isAdminAuthenticated', isAuthenticated.toString());
  };

  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/" element={<Navigate to="/user" replace />} />
          <Route path="/user" element={<UserUI />} />
          <Route 
            path="/admin/login" 
            element={<LoginPage setAuth={setAuth} />} 
          />
          <Route 
            path="/admin" 
            element={
              isAdminAuthenticated ? (
                <AdminDashboard setAuth={setAuth} />
              ) : (
                <Navigate to="/admin/login" replace />
              )
            } 
          />
          {/* Catch all route - redirect to user interface */}
          <Route path="*" element={<Navigate to="/user" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;