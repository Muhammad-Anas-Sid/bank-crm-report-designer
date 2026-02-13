import { useState, useEffect } from 'react';

function LoginHistory({ onBack }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Auto-open when component mounts (triggered by parent)
  useEffect(() => {
    // Fetch data
    fetch('/api/login-history')
      .then(res => {
        if (!res.ok) throw new Error("Failed to fetch history");
        return res.json();
      })
      .then(data => {
        setHistory(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div className="sidebar-overlay" onClick={onBack}>
      <div 
        className="sidebar open" 
        onClick={e => e.stopPropagation()} // Prevents closing when clicking inside sidebar
      >
        <div className="sidebar-header">
          <h2 className="sidebar-title">Login History</h2>
          <button className="close-btn" onClick={onBack}>
            ×
          </button>
        </div>

        <div className="history-list">
          {loading ? (
            <div className="loader">
              <div className="spinner"></div>
              <p>Loading login records...</p>
            </div>
          ) : error ? (
            <div className="error-message">
              <strong>Error:</strong> {error}
            </div>
          ) : history.length === 0 ? (
            <p className="no-data">No login records found.</p>
          ) : (
            history.map((record, index) => {
              const dateObj = new Date(record.timestamp);
              return (
                <div key={index} className="history-item">
                  <div className="history-name">
                    <span className="history-avatar">👤</span>
                    {record.name || 'Unknown User'}
                  </div>
                  <div className="history-role">{record.role}</div>
                  <div className="history-date">
                    <span>{dateObj.toLocaleDateString()}</span>
                    <span>·</span>
                    <span>{dateObj.toLocaleTimeString()}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

export default LoginHistory;