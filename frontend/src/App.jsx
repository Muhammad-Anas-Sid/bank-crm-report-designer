import { useState, useEffect, useRef } from 'react';
import Login from './Login';

const API_BASE = '/api';

function getAuthHeaders(token) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

// ─── Top Navbar ──────────────────────────────────────────────
function Navbar({ user, onLogout }) {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <svg viewBox="0 0 32 32" className="navbar-logo">
          <rect x="3" y="16" width="26" height="13" rx="2" fill="#38bdf8" />
          <rect x="6" y="8" width="20" height="11" rx="2" fill="#0ea5e9" />
          <rect x="10" y="3" width="12" height="8" rx="2" fill="#0284c7" />
          <circle cx="16" cy="22" r="2.5" fill="#0F2B46" />
        </svg>
        <span>Enterprise Bank — AI Report Designer</span>
      </div>
      <div className="navbar-user">
        <div className="user-info">
          <span className="user-name">{user.full_name || user.username}</span>
          <span className="user-role">{(user.roles || []).join(', ')}</span>
        </div>
        <button className="logout-btn" onClick={onLogout} title="Logout">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>
    </nav>
  );
}

// ─── Left Sidebar ────────────────────────────────────────────
function Sidebar({ activeTab, setActiveTab, chatSessions, activeChatId, onNewChat, onSelectChat }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-tabs">
        <button
          className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          Chats
        </button>
        <button
          className={`tab-btn ${activeTab === 'history' ? 'active' : ''}`}
          onClick={() => setActiveTab('history')}
        >
          History
        </button>
        <button
          className={`tab-btn ${activeTab === 'logs' ? 'active' : ''}`}
          onClick={() => setActiveTab('logs')}
        >
          Logs
        </button>
      </div>

      {activeTab === 'chat' && (
        <div className="sidebar-content">
          <button className="new-chat-btn" onClick={onNewChat}>
            + New Chat
          </button>
          <div className="chat-session-list">
            {chatSessions.map((s) => (
              <div
                key={s.chat_session_id}
                className={`chat-session-item ${activeChatId === s.chat_session_id ? 'active' : ''}`}
                onClick={() => onSelectChat(s.chat_session_id)}
              >
                <span className="session-title">{s.title}</span>
                <span className="session-date">
                  {new Date(s.updated_at).toLocaleDateString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === 'history' && <ReportHistory />}
      {activeTab === 'logs' && <LoginHistory />}
    </aside>
  );
}

// ─── Report History ──────────────────────────────────────────
function ReportHistory() {
  const [reports, setReports] = useState([]);
  const token = localStorage.getItem('token');

  useEffect(() => {
    fetch(`${API_BASE}/reports/history`, { headers: getAuthHeaders(token) })
      .then((r) => r.json())
      .then((data) => setReports(Array.isArray(data) ? data : []))
      .catch(() => { });
  }, []);

  return (
    <div className="sidebar-content">
      <h3 className="sidebar-heading">Report History</h3>
      {reports.length === 0 ? (
        <p className="empty-state">No reports generated yet</p>
      ) : (
        <div className="history-list">
          {reports.map((r, i) => (
            <div key={i} className="history-item">
              <span className="history-action">{r.action}</span>
              <span className="history-date">
                {new Date(r.created_at).toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Login History ───────────────────────────────────────────
function LoginHistory() {
  const [history, setHistory] = useState([]);
  const token = localStorage.getItem('token');

  useEffect(() => {
    fetch(`${API_BASE}/audit/login-history`, { headers: getAuthHeaders(token) })
      .then((r) => r.json())
      .then((data) => setHistory(Array.isArray(data) ? data : []))
      .catch(() => { });
  }, []);

  return (
    <div className="sidebar-content">
      <h3 className="sidebar-heading">Login History</h3>
      {history.length === 0 ? (
        <p className="empty-state">No login history</p>
      ) : (
        <div className="history-list">
          {history.map((h, i) => (
            <div key={i} className="history-item">
              <div className="history-user">
                <span className="history-name">{h.name}</span>
                <span className={`history-badge ${h.status === 'SUCCESS' ? 'success' : 'failure'}`}>
                  {h.status}
                </span>
              </div>
              <span className="history-date">
                {h.timestamp ? new Date(h.timestamp).toLocaleString() : '—'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Chat Panel ──────────────────────────────────────────────
function ChatPanel({ messages, onSend, loading }) {
  const [input, setInput] = useState('');
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput('');
    onSend(msg);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-messages" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`chat-message ${m.role}`}>
            <div className="message-avatar">
              {m.role === 'assistant' ? '🤖' : '👤'}
            </div>
            <div className="message-content">
              <MessageContent content={m.content} metadata={m.metadata} />
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-message assistant">
            <div className="message-avatar">🤖</div>
            <div className="message-content">
              <div className="typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        )}
      </div>
      <div className="chat-input-bar">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe the report you need..."
          rows={1}
          disabled={loading}
        />
        <button className="send-btn" onClick={handleSend} disabled={loading || !input.trim()}>
          <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
          </svg>
        </button>
      </div>
    </div>
  );
}

// ─── Message Content (with download link) ────────────────────
function MessageContent({ content, metadata }) {
  const token = localStorage.getItem('token');

  const handleDownload = async (link) => {
    try {
      const res = await fetch(link, { headers: { Authorization: `Bearer ${token}` } });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = link.split('/').pop();
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  // Render markdown-like content
  const renderContent = (text) => {
    return text.split('\n').map((line, i) => {
      // Bold text
      line = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      // Bullet points
      if (line.startsWith('• ') || line.startsWith('- ')) {
        return <li key={i} dangerouslySetInnerHTML={{ __html: line.slice(2) }} />;
      }
      if (line.trim() === '') return <br key={i} />;
      return <p key={i} dangerouslySetInnerHTML={{ __html: line }} />;
    });
  };

  return (
    <div className="message-text">
      {renderContent(content)}
      {metadata?.download_link && (
        <button
          className="download-btn"
          onClick={() => handleDownload(metadata.download_link)}
        >
          📥 Download PDF Report
        </button>
      )}
    </div>
  );
}

// ─── Document Preview Panel ──────────────────────────────────
function DocumentPreview({ report }) {
  if (!report) {
    return (
      <div className="preview-empty">
        <div className="preview-placeholder">
          <svg viewBox="0 0 80 80" width="80" height="80" fill="none" stroke="#334155" strokeWidth="1.5">
            <rect x="15" y="5" width="50" height="70" rx="4" />
            <line x1="25" y1="20" x2="55" y2="20" />
            <line x1="25" y1="30" x2="55" y2="30" />
            <line x1="25" y1="40" x2="45" y2="40" />
            <rect x="25" y="50" width="30" height="15" rx="2" />
          </svg>
          <h3>No Report Generated Yet</h3>
          <p>Use the chat to describe the report you need.</p>
        </div>
      </div>
    );
  }

  const plan = report.report_plan || {};
  const preview = report.data_preview || [];
  const insights = report.insights || '';

  return (
    <div className="preview-content">
      <div className="preview-header">
        <h2>{plan.report_title || 'Generated Report'}</h2>
        <span className="preview-rows">{report.total_rows} rows</span>
      </div>

      {/* Insights */}
      <div className="preview-section">
        <h3>📊 Insights</h3>
        <div className="insights-box">
          {insights.split('\n').map((line, i) => {
            line = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            if (!line.trim()) return <br key={i} />;
            return <p key={i} dangerouslySetInnerHTML={{ __html: line }} />;
          })}
        </div>
      </div>

      {/* Data Preview */}
      {preview.length > 0 && (
        <div className="preview-section">
          <h3>📋 Data Preview (Top 5)</h3>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  {Object.keys(preview[0]).map((key) => (
                    <th key={key}>{key}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.map((row, i) => (
                  <tr key={i}>
                    {Object.values(row).map((val, j) => (
                      <td key={j}>{val !== null ? String(val) : '—'}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Download */}
      {report.download_link && (
        <div className="preview-actions">
          <DownloadButton link={report.download_link} />
        </div>
      )}
    </div>
  );
}

function DownloadButton({ link }) {
  const token = localStorage.getItem('token');
  const handleDownload = async () => {
    try {
      const res = await fetch(link, { headers: { Authorization: `Bearer ${token}` } });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = link.split('/').pop();
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download error:', err);
    }
  };

  return (
    <button className="download-report-btn" onClick={handleDownload}>
      📥 Download Full PDF Report
    </button>
  );
}

// ─── Main App ────────────────────────────────────────────────
export default function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [activeTab, setActiveTab] = useState('chat');
  const [chatSessions, setChatSessions] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [currentReport, setCurrentReport] = useState(null);

  // Verify token on mount
  useEffect(() => {
    if (token) {
      fetch(`${API_BASE}/auth/me`, { headers: getAuthHeaders(token) })
        .then((r) => {
          if (!r.ok) throw new Error('Invalid token');
          return r.json();
        })
        .then((data) => {
          setUser(data);
          loadChatSessions(token);
        })
        .catch(() => {
          localStorage.removeItem('token');
          setToken(null);
          setUser(null);
        });
    }
  }, []);

  const loadChatSessions = async (t) => {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`, { headers: getAuthHeaders(t) });
      const data = await res.json();
      if (Array.isArray(data)) {
        setChatSessions(data);
        if (data.length > 0 && !activeChatId) {
          selectChat(data[0].chat_session_id, t);
        }
      }
    } catch (err) { console.error(err); }
  };

  const selectChat = async (sessionId, t = token) => {
    setActiveChatId(sessionId);
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, {
        headers: getAuthHeaders(t),
      });
      const data = await res.json();
      setMessages(Array.isArray(data) ? data : []);
    } catch (err) { console.error(err); }
  };

  const handleNewChat = async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify({ title: 'New Chat' }),
      });
      const data = await res.json();
      if (data.session) {
        setChatSessions((prev) => [data.session, ...prev]);
        selectChat(data.session.chat_session_id);
      }
    } catch (err) { console.error(err); }
  };

  const handleSendMessage = async (content) => {
    if (!activeChatId) {
      await handleNewChat();
      return;
    }

    // Optimistic UI — add user message immediately
    setMessages((prev) => [...prev, { role: 'user', content, created_at: new Date().toISOString() }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat/messages`, {
        method: 'POST',
        headers: getAuthHeaders(token),
        body: JSON.stringify({ session_id: activeChatId, content }),
      });
      const data = await res.json();

      if (data.message) {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.message,
            metadata: data.report ? {
              download_link: data.report.download_link,
              total_rows: data.report.total_rows,
            } : undefined,
            created_at: new Date().toISOString(),
          },
        ]);
      }

      if (data.report && data.report.status === 'success') {
        setCurrentReport(data.report);
      }

      // Refresh sessions
      loadChatSessions(token);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '⚠️ Failed to process request.', created_at: new Date().toISOString() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = (userData, newToken) => {
    setUser(userData);
    setToken(newToken);
    loadChatSessions(newToken);
  };

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: getAuthHeaders(token),
      });
    } catch (err) { /* ignore */ }
    localStorage.removeItem('token');
    setUser(null);
    setToken(null);
    setChatSessions([]);
    setMessages([]);
    setActiveChatId(null);
    setCurrentReport(null);
  };

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="app-layout">
      <Navbar user={user} onLogout={handleLogout} />
      <div className="app-body">
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          chatSessions={chatSessions}
          activeChatId={activeChatId}
          onNewChat={handleNewChat}
          onSelectChat={(id) => selectChat(id)}
        />
        <main className="main-panel">
          <div className="main-split">
            <ChatPanel messages={messages} onSend={handleSendMessage} loading={loading} />
            <DocumentPreview report={currentReport} />
          </div>
        </main>
      </div>
    </div>
  );
}