import { useState, useEffect, useRef } from 'react';
import React from 'react'; // Ensure React is available for callback
import Login from './Login';

const API_BASE = '/api';

function getAuthHeaders(token) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

// ─── Context Menu Component ──────────────────────────────────
function ContextMenu({ x, y, options, onClose }) {
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onClose]);

  return (
    <div
      ref={menuRef}
      className="custom-context-menu"
      style={{ top: y, left: x }}
    >
      {options.map((opt, i) => (
        <div key={i} className={`context-menu-item ${opt.type || ''}`} onClick={() => { opt.onClick(); onClose(); }}>
          {opt.icon && <span className="icon">{opt.icon}</span>}
          {opt.label}
        </div>
      ))}
    </div>
  );
}

// ─── Top Navbar ──────────────────────────────────────────────
function Navbar({ user, onLogout }) {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <div className="logo-wrapper">
          <svg viewBox="0 0 160 60" className="avanza-logo">
            <text x="5" y="45" fontFamily="Inter, sans-serif" fontWeight="700" fontSize="38" fill="var(--accent)" letterSpacing="-1">avanza</text>
            <text x="6" y="58" fontFamily="Inter, sans-serif" fontWeight="400" fontSize="10" fill="#64748b" letterSpacing="6">SOLUTIONS</text>
            <path d="M125 15 L142 8 L136 20" fill="none" stroke="#64748b" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
        </div>
        <span>AI Report Designer</span>
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
function Sidebar({
  activeTab,
  setActiveTab,
  chatSessions,
  activeChatId,
  onNewChat,
  onSelectChat,
  onDeleteChat,
  collapsed,
  toggleSidebar,
  onSelectReport,
  onDeleteReport,
  onDeleteLoginLog
}) {
  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        {!collapsed && <h3>Menu</h3>}
        <button className="sidebar-toggle" onClick={toggleSidebar}>
          {collapsed ? '☰' : '←'}
        </button>
      </div>

      <div className="sidebar-tabs">
        <button className={`tab-btn ${activeTab === 'chat' ? 'active' : ''}`} onClick={() => setActiveTab('chat')} title="Chats">
          <span className="icon">💬</span> {!collapsed && "Chats"}
        </button>
        <button className={`tab-btn ${activeTab === 'reports' ? 'active' : ''}`} onClick={() => setActiveTab('reports')} title="Reports">
          <span className="icon">📄</span> {!collapsed && "Reports"}
        </button>
        <button className={`tab-btn ${activeTab === 'logs' ? 'active' : ''}`} onClick={() => setActiveTab('logs')} title="Login History">
          <span className="icon">🕒</span> {!collapsed && "Logins"}
        </button>
      </div>

      <div className="sidebar-content-wrapper">
        {!collapsed && (
          <>
            {activeTab === 'chat' && (
              <div className="sidebar-content">
                <button className="new-chat-btn" onClick={onNewChat}>+ New Chat</button>
                <div className="chat-session-list">
                  {chatSessions.map((s) => (
                    <div
                      key={s.chat_session_id}
                      className={`chat-session-item ${activeChatId === s.chat_session_id ? 'active' : ''}`}
                      onClick={() => onSelectChat(s.chat_session_id)}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        onDeleteChat(s.chat_session_id, e.clientX, e.clientY);
                      }}
                    >
                      <span className="session-title">{s.title}</span>
                      <span className="session-date">{new Date(s.updated_at).toLocaleDateString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {activeTab === 'reports' && <ReportHistory onSelectReport={onSelectReport} onDeleteReport={onDeleteReport} />}
            {activeTab === 'logs' && <LoginHistory onDeleteLoginLog={onDeleteLoginLog} />}
          </>
        )}
      </div>
    </aside>
  );
}

// ─── Report History ──────────────────────────────────────────
function ReportHistory({ onSelectReport, onDeleteReport }) {
  const [reports, setReports] = useState([]);
  const token = localStorage.getItem('token');

  const fetchHistory = React.useCallback(() => {
    fetch(`${API_BASE}/reports/history`, { headers: getAuthHeaders(token) })
      .then((r) => r.json())
      .then((data) => {
        const parsed = (Array.isArray(data) ? data : []).map(r => {
          try {
            const details = typeof r.details === 'string' ? JSON.parse(r.details) : r.details;
            return { ...r, details };
          } catch { return r; }
        });
        setReports(parsed);
      })
      .catch((err) => console.error("History fetch error:", err));
  }, [token]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return (
    <div className="sidebar-content">
      <h3 className="sidebar-heading">Generated Reports</h3>
      {reports.length === 0 ? (
        <p className="empty-state">No reports generated yet</p>
      ) : (
        <div className="history-list">
          {reports.map((r, i) => {
            const filename = r.details?.filename;
            if (!filename) return null;
            return (
              <div
                key={i}
                className="history-item clickable"
                onClick={() => onSelectReport({
                  report_plan: { report_title: r.details.prompt || "Report" },
                  total_rows: r.details.rows || 0,
                  download_link: `/api/reports/download/${filename}`
                })}
                onContextMenu={(e) => {
                  e.preventDefault();
                  onDeleteReport(filename, e.clientX, e.clientY, () => fetchHistory());
                }}
              >
                <span className="history-action">{r.details?.prompt || "Report"}</span>
                <span className="history-date">
                  {new Date(r.created_at).toLocaleString()} • {r.details?.rows || 0} rows
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Login History ───────────────────────────────────────────
function LoginHistory({ onDeleteLoginLog }) {
  const [history, setHistory] = useState([]);
  const token = localStorage.getItem('token');

  const fetchLogs = React.useCallback(() => {
    fetch(`${API_BASE}/audit/login-history`, { headers: getAuthHeaders(token) })
      .then((r) => r.json())
      .then((data) => setHistory(Array.isArray(data) ? data : []))
      .catch((err) => console.error("Login history fetch error:", err));
  }, [token]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return (
    <div className="sidebar-content">
      <h3 className="sidebar-heading">Login History</h3>
      {history.length === 0 ? (
        <p className="empty-state">No login history</p>
      ) : (
        <div className="history-list">
          {history.map((h, i) => (
            <div
              key={h.id || i}
              className="history-item"
              onContextMenu={(e) => {
                e.preventDefault();
                onDeleteLoginLog(h.id, e.clientX, e.clientY, () => fetchLogs());
              }}
            >
              <div className="history-user">
                <span className="history-name">{h.name}</span>
                <span className={`history-badge ${h.status === 'SUCCESS' ? 'success' : 'failure'}`}>{h.status}</span>
              </div>
              <span className="history-date">{h.timestamp ? new Date(h.timestamp).toLocaleString() : '—'}</span>
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
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const handleSend = () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput('');
    onSend(msg);
  };

  return (
    <div className="chat-panel">
      <div className="chat-messages" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`chat-message ${m.role}`}>
            <div className="message-avatar">{m.role === 'assistant' ? '🤖' : '👤'}</div>
            <div className="message-content">
              <MessageContent
                content={m.content}
                metadata={m.metadata}
              />
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-message assistant">
            <div className="message-avatar">🤖</div>
            <div className="message-content">
              <div className="typing-indicator"><span></span><span></span><span></span></div>
            </div>
          </div>
        )}
      </div>
      <div className="chat-input-bar">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
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

// ─── Message Content ─────────────────────────────────────────
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
    } catch (err) { console.error('Download failed:', err); }
  };

  const handleView = async (link) => {
    try {
      const reportUrl = link.startsWith('http') ? link : `${API_BASE}/reports/download/${link.split('/').pop()}?preview=true`;
      const res = await fetch(reportUrl, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error("Failed to load PDF");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch (err) {
      console.error('View failed:', err);
      alert("Could not open report preview. Please try downloading it instead.");
    }
  };

  const renderContent = (text) => {
    return text.split('\n').map((line, i) => {
      line = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      if (line.startsWith('• ') || line.startsWith('- ')) {
        const content = line.slice(2);
        return <li key={i} dangerouslySetInnerHTML={{ __html: content }} />;
      }
      if (line.trim() === '') return <div key={i} style={{ height: '0.5rem' }} />;
      return <p key={i} dangerouslySetInnerHTML={{ __html: line }} />;
    });
  };

  return (
    <div className="message-text">
      {renderContent(content)}
      {metadata?.download_link && (
        <div className="message-actions" style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
          <button className="download-btn" onClick={() => handleView(metadata.download_link)}>
            👁️ View Report
          </button>
          <button className="download-btn secondary" onClick={() => handleDownload(metadata.download_link)}>
            📥 Download PDF
          </button>
        </div>
      )}
    </div>
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // UI States
  const [contextMenu, setContextMenu] = useState(null);

  const authHeaders = (t = token) => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${t}`,
  });

  const viewReportInNewWindow = async (link) => {
    if (!link) return;
    try {
      const reportUrl = link.startsWith('http') ? link : `${API_BASE}/reports/download/${link.split('/').pop()}?preview=true`;
      const res = await fetch(reportUrl, { headers: authHeaders() });
      if (!res.ok) throw new Error("Failed to load PDF");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch (err) {
      console.error('Failed to open report:', err);
      alert("Could not open report preview. Please try downloading it instead.");
    }
  };

  const loadChatSessions = async (t) => {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`, { headers: authHeaders(t) });
      const data = await res.json();
      if (Array.isArray(data)) {
        setChatSessions(data);
        if (data.length > 0 && !activeChatId) selectChat(data[0].chat_session_id, t);
      }
    } catch (err) { console.error("Load sessions error:", err); }
  };

  const selectChat = async (sessionId, t = token) => {
    setActiveChatId(sessionId);
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages`, { headers: authHeaders(t) });
      const data = await res.json();
      setMessages(Array.isArray(data) ? data : []);
    } catch (err) { console.error("Select chat error:", err); }
  };

  const handleDeleteChat = (sessionId, x, y) => {
    setContextMenu({
      x, y,
      options: [
        {
          label: 'Delete Chat',
          icon: '🗑️',
          type: 'danger',
          onClick: async () => {
            if (!window.confirm("Delete this chat?")) return;
            await fetch(`${API_BASE}/chat/sessions/${sessionId}`, { method: 'DELETE', headers: authHeaders() });
            setChatSessions(prev => prev.filter(s => s.chat_session_id !== sessionId));
            if (activeChatId === sessionId) {
              setMessages([]);
              setActiveChatId(null);
            }
          }
        }
      ]
    });
  };

  const handleDeleteReport = (filename, x, y, onDeleted) => {
    setContextMenu({
      x, y,
      options: [
        {
          label: 'Delete Report',
          icon: '🗑️',
          type: 'danger',
          onClick: async () => {
            if (!window.confirm("Permanently delete this report?")) return;
            await fetch(`${API_BASE}/reports/delete/${filename}`, { method: 'DELETE', headers: authHeaders() });
            onDeleted();
          }
        }
      ]
    });
  };

  const handleDeleteLoginLog = (logId, x, y, onDeleted) => {
    setContextMenu({
      x, y,
      options: [
        {
          label: 'Remove from list',
          icon: '❌',
          type: 'danger',
          onClick: async () => {
            await fetch(`${API_BASE}/audit/login-history/${logId}`, { method: 'DELETE', headers: authHeaders() });
            onDeleted();
          }
        }
      ]
    });
  };

  const handleSendMessage = async (content) => {
    let currentId = activeChatId;
    if (!currentId) {
      const res = await fetch(`${API_BASE}/chat/sessions`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ title: 'New Chat' }),
      });
      const data = await res.json();
      if (!data.session) return;
      currentId = data.session.chat_session_id;
      setChatSessions(prev => [data.session, ...prev]);
      setActiveChatId(currentId);
    }

    setMessages(prev => [...prev, { role: 'user', content }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat/messages`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({ session_id: currentId, content }),
      });
      const data = await res.json();
      if (data.message) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.message,
          metadata: data.report ? { download_link: data.report.download_link, total_rows: data.report.total_rows } : undefined
        }]);
      }
      if (data.report?.download_link) {
        viewReportInNewWindow(data.report.download_link);
      }
      loadChatSessions(token);
    } catch (err) { console.error("Send error:", err); }
    finally { setLoading(false); }
  };

  const handleLogin = (userData, newToken) => {
    setUser(userData);
    setToken(newToken);
    localStorage.setItem('token', newToken);
    loadChatSessions(newToken);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setUser(null);
    setToken(null);
  };

  useEffect(() => {
    if (token) {
      fetch(`${API_BASE}/auth/me`, { headers: authHeaders(token) })
        .then(r => r.ok ? r.json() : Promise.reject())
        .then(data => { setUser(data); loadChatSessions(token); })
        .catch(() => { localStorage.removeItem('token'); setToken(null); setUser(null); });
    }
  }, [token]);

  if (!user) return <Login onLogin={handleLogin} />;

  return (
    <div className="app-layout" onClick={() => setContextMenu(null)}>
      <Navbar user={user} onLogout={handleLogout} />
      <div className="app-body">
        <Sidebar
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          chatSessions={chatSessions}
          activeChatId={activeChatId}
          onNewChat={() => { setActiveChatId(null); setMessages([]); }}
          onSelectChat={selectChat}
          onDeleteChat={handleDeleteChat}
          collapsed={sidebarCollapsed}
          toggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
          onSelectReport={(report) => viewReportInNewWindow(report.download_link)}
          onDeleteReport={handleDeleteReport}
          onDeleteLoginLog={handleDeleteLoginLog}
        />
        <main className="main-panel">
          <div className="chat-container-full">
            <ChatPanel
              messages={messages}
              onSend={handleSendMessage}
              loading={loading}
            />
          </div>
        </main>
      </div>

      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          options={contextMenu.options}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
}