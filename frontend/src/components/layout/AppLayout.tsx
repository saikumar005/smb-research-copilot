import React from 'react';
import { LogOut, Brain, MessageSquare, Plus, Settings, Loader2, Mail } from 'lucide-react';

interface ChatThread {
  id: number;
  title: string;
}

interface AppLayoutProps {
  children: React.ReactNode;
  userEmail: string;
  chats: ChatThread[];
  activeChatId: number | null;
  creatingChat?: boolean;
  onSelectChat: (id: number) => void;
  onCreateChat: () => void;
  onDeleteChat?: (id: number) => void;
  onOpenMemorySettings: () => void;
  onLogout: () => void;
  gmailConnected?: boolean;
  onConnectGmail?: () => void;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  children,
  userEmail,
  chats,
  activeChatId,
  creatingChat = false,
  onSelectChat,
  onCreateChat,
  onOpenMemorySettings,
  onLogout,
  gmailConnected = false,
  onConnectGmail,
}) => {
  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar-container glass-panel">
        <div className="sidebar-brand">
          <Brain size={24} className="brand-logo" />
          <h2>Research Copilot</h2>
        </div>

        {/* New Research Chat Button — with loading state and double-click guard */}
        <button
          className="new-chat-btn glow-btn-base glow-btn"
          onClick={onCreateChat}
          disabled={creatingChat}
          aria-label="Create a new research thread"
          title={creatingChat ? 'Creating thread…' : 'New Research Chat'}
          style={{
            opacity: creatingChat ? 0.75 : 1,
            cursor: creatingChat ? 'not-allowed' : 'pointer',
          }}
        >
          {creatingChat ? (
            <Loader2 size={16} className="spin-icon" />
          ) : (
            <Plus size={16} />
          )}
          <span>{creatingChat ? 'Creating…' : 'New Research Chat'}</span>
        </button>

        <nav className="sidebar-nav">
          <div className="nav-section-title">RECENT THREADS</div>
          <div className="chat-threads-list">
            {chats.length === 0 ? (
              <div className="empty-threads">No research chats yet.</div>
            ) : (
              chats.map((chat) => (
                <button
                  key={chat.id}
                  className={`thread-item-btn ${activeChatId === chat.id ? 'thread-active' : ''}`}
                  onClick={() => onSelectChat(chat.id)}
                >
                  <MessageSquare size={16} className="thread-icon" />
                  <span className="thread-title">{chat.title || 'Untitled Thread'}</span>
                </button>
              ))
            )}
          </div>
        </nav>

        <div className="sidebar-footer">
          <button className="sidebar-footer-btn" onClick={onOpenMemorySettings}>
            <Settings size={16} />
            <span>Manage Memory</span>
          </button>

          {/* Gmail Connection Status */}
          {gmailConnected ? (
            <div className="gmail-status-badge gmail-status-connected">
              <Mail size={13} />
              <span>Gmail Connected</span>
              <span className="gmail-connected-dot" />
            </div>
          ) : (
            <button className="gmail-status-badge gmail-status-disconnected" onClick={onConnectGmail}>
              <Mail size={13} />
              <span>Connect Gmail</span>
            </button>
          )}

          <div className="user-profile-badge">
            <span className="user-initial">{userEmail[0]?.toUpperCase()}</span>
            <span className="user-email-text" title={userEmail}>{userEmail}</span>
          </div>

          <button className="logout-btn-action" onClick={onLogout}>
            <LogOut size={16} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Page Workspace */}
      <main className="main-content-workspace">
        {children}
      </main>
    </div>
  );
};
