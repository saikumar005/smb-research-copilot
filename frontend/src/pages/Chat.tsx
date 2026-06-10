import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  Send, 
  Trash2, 
  Search, 
  Mail, 
  CheckSquare, 
  Brain, 
  ExternalLink, 
  FileText, 
  Sparkles,
  RefreshCw
} from 'lucide-react';
import { apiClient } from '../api/client';
import { AppLayout } from '../components/layout/AppLayout';
import { Spinner } from '../components/ui/Spinner';
import { MemoryManager } from '../components/memory/MemoryManager';

interface ChatThread {
  id: number;
  title: string;
}

interface Source {
  title: string;
  link: string;
  snippet: string;
}

interface Message {
  id: number;
  chat_id: number;
  role: 'user' | 'assistant';
  content: string;
  metadata_json?: {
    sources?: Source[];
    action_mode?: string;
  };
  created_at: string;
}

/**
 * Rewrites citation references in AI response text into clickable markdown links.
 * Handles: (Source 1), (Source 2), [1], [2], Source 1, Source 2
 * Converts them to [[1]](url) which ReactMarkdown renders as a link.
 */
function processCitationLinks(content: string, sources: Source[]): string {
  if (!sources || sources.length === 0) return content;

  let processed = content;

  // Replace (Source N) — most common pattern from Writer agent
  processed = processed.replace(/\(Source\s+(\d+)\)/gi, (_, num) => {
    const idx = parseInt(num, 10) - 1;
    if (idx >= 0 && idx < sources.length) {
      return `[[${num}]](${sources[idx].link})`;
    }
    return `(Source ${num})`;
  });

  // Replace bare [N] that are NOT already part of a markdown link [text](url)
  processed = processed.replace(/\[(\d+)\](?!\()/g, (_, num) => {
    const idx = parseInt(num, 10) - 1;
    if (idx >= 0 && idx < sources.length) {
      return `[[${num}]](${sources[idx].link})`;
    }
    return `[${num}]`;
  });

  return processed;
}

/** Extract a short readable domain name from a URL for display in footnotes */
function getDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export const Chat: React.FC = () => {
  const [userEmail, setUserEmail] = useState('');
  const [chats, setChats] = useState<ChatThread[]>([]);
  const [activeChatId, setActiveChatId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  
  // Interface view states
  const [loadingApp, setLoadingApp] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sending, setSending] = useState(false);
  const [composerText, setComposerText] = useState('');
  const [showMemorySettings, setShowMemorySettings] = useState(false);
  
  // Pending action mode: set when user clicks an action pill but hasn't provided input yet.
  // The next message the user sends will be routed through /actions/run with this mode.
  const [pendingActionMode, setPendingActionMode] = useState<'research' | 'email_draft' | 'task_list' | null>(null);
  // Which action button is currently being validated by the backend (shows spinner on that pill)
  const [validatingMode, setValidatingMode] = useState<'research' | 'email_draft' | 'task_list' | null>(null);
  
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll messages list to the bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  const loadAppData = async () => {
    try {
      setLoadingApp(true);
      // Fetch user profile
      const userRes = await apiClient.get('/auth/me');
      setUserEmail(userRes.data.email);

      // Fetch chat threads
      const chatsRes = await apiClient.get<ChatThread[]>('/chats');
      setChats(chatsRes.data);
      
      // Select the first thread by default if available
      if (chatsRes.data.length > 0) {
        setActiveChatId(chatsRes.data[0].id);
      }
    } catch (err) {
      console.error('Could not authenticate or load dashboard states:', err);
      // Token is likely invalid or missing, api client handles clearing it
    } finally {
      setLoadingApp(false);
    }
  };

  const loadMessages = async (chatId: number) => {
    try {
      setLoadingMessages(true);
      const res = await apiClient.get<Message[]>(`/chats/${chatId}/messages`);
      setMessages(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingMessages(false);
    }
  };

  useEffect(() => {
    loadAppData();
  }, []);

  useEffect(() => {
    if (activeChatId !== null) {
      loadMessages(activeChatId);
    } else {
      setMessages([]);
    }
  }, [activeChatId]);

  const handleCreateChat = async (title?: string) => {
    try {
      const res = await apiClient.post<ChatThread>('/chats', { 
        title: title || 'New Research Thread' 
      });
      setChats((prev) => [res.data, ...prev]);
      setActiveChatId(res.data.id);
      setShowMemorySettings(false);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteChat = async (id: number) => {
    if (!window.confirm('Delete this research chat thread permanently?')) return;
    try {
      await apiClient.delete(`/chats/${id}`);
      setChats((prev) => prev.filter((c) => c.id !== id));
      if (activeChatId === id) {
        setActiveChatId(null);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleSendMessage = async (text: string) => {
    if (!text.trim() || activeChatId === null || sending) return;
    
    setComposerText('');
    setSending(true);
    
    // If an action mode is pending, this message is the user's input for that action.
    // Route it through /actions/run instead of the regular chat endpoint.
    const activeMode = pendingActionMode;
    if (activeMode) setPendingActionMode(null); // clear mode before async work
    
    // Optimistically show the user message immediately
    const tempId = Date.now();
    const tempUserMsg: Message = {
      id: tempId,
      chat_id: activeChatId,
      role: 'user',
      content: text,
      created_at: new Date().toISOString()
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      if (activeMode) {
        // User is responding to an action prompt — run the specialized agent mode
        await apiClient.post<Message>('/actions/run', {
          chat_id: activeChatId,
          mode: activeMode,
          message: text,
        });
      } else {
        // Normal conversational message
        await apiClient.post<Message>(`/chats/${activeChatId}/messages`, {
          content: text,
        });
      }

      // Reload full message list to get both persisted user msg and assistant reply
      const refreshed = await apiClient.get<Message[]>(`/chats/${activeChatId}/messages`);
      setMessages(refreshed.data);
      
      // Reload threads list to fetch updated titles and ordering
      const threadsRes = await apiClient.get<ChatThread[]>('/chats');
      setChats(threadsRes.data);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev.filter(m => m.id !== tempId),
        { ...tempUserMsg, id: Date.now() },
        {
          id: Date.now() + 1,
          chat_id: activeChatId,
          role: 'assistant',
          content: '⚠️ Failed to get agent response. Please check your API key configuration.',
          created_at: new Date().toISOString()
        }
      ]);
    } finally {
      setSending(false);
    }
  };

  // Action config: each mode has a local prompt shown to guide the user,
  // a textarea placeholder, and a display label.
  const ACTION_CONFIG = {
    research: {
      label: 'Research Company',
      icon: <Search size={13} />,
      prompt: [
        '🔍 **Research Company** — I\'ll gather a full company brief including:',
        '',
        '- Company overview & size',
        '- Key priorities & recent developments',
        '- Likely pain points',
        '- Suggested outreach angles',
        '- Verified source citations',
        '',
        '**Please type the company name** you want me to research below.',
      ].join('\n'),
      placeholder: 'Type company name, e.g. HubSpot, Razorpay, Stripe…',
    },
    email_draft: {
      label: 'Draft Sales Email',
      icon: <Mail size={13} />,
      prompt: [
        '✉️ **Draft Sales Email** — I\'ll write a personalized outreach email tailored to the target company.',
        '',
        'For the best results, include:',
        '- **Company name** (required)',
        '- Any specific pain point or product angle to address *(optional)*',
        '',
        '**Type your request below**, e.g. *"Draft email for HubSpot targeting their RevOps team"*',
      ].join('\n'),
      placeholder: 'e.g. Draft email for HubSpot targeting their RevOps team…',
    },
    task_list: {
      label: 'Create Task Checklist',
      icon: <CheckSquare size={13} />,
      prompt: [
        '✅ **Create Task Checklist** — I\'ll compile a structured, actionable checklist to prepare for outreach.',
        '',
        'Tell me:',
        '- **Target company or deal** (required)',
        '- Context or goal *(optional)*, e.g. *product demo, first call, partnership pitch*',
        '',
        '**Type your request below**, e.g. *"Prepare checklist for Microsoft enterprise demo"*',
      ].join('\n'),
      placeholder: 'e.g. Prepare checklist for Microsoft enterprise demo…',
    },
  } as const;

  /**
   * handleAction — smart two-step flow with backend guard-rails:
   * 1. Calls POST /actions/validate to check if the chat already has enough context.
   * 2a. If can_execute=true → auto-fires /actions/run with the extracted company name.
   * 2b. If can_execute=false → shows a targeted guidance prompt for what's MISSING only.
   *
   * This prevents asking for the company name when it was already discussed,
   * while still prompting the user when context is genuinely absent.
   */
  const handleAction = async (mode: 'research' | 'email_draft' | 'task_list') => {
    if (activeChatId === null || sending || validatingMode) return;

    const config = ACTION_CONFIG[mode];
    setValidatingMode(mode);

    try {
      // Ask the backend whether enough context exists to auto-execute
      const validateRes = await apiClient.post<{
        can_execute: boolean;
        company_name: string | null;
        context_summary: string | null;
        missing_fields: string[];
        auto_message: string | null;
      }>('/actions/validate', { chat_id: activeChatId, mode });

      const { can_execute, auto_message, missing_fields } = validateRes.data;

      if (can_execute && auto_message) {
        // Context is sufficient — execute immediately without prompting
        setValidatingMode(null);
        await executePendingAction(mode, auto_message);
      } else {
        // Build a targeted guidance prompt listing only what's missing
        const missingLabels: Record<string, string> = { company_name: 'the target **company name**' };
        const missingList = missing_fields
          .map((f) => `- Please provide ${missingLabels[f] || f}`)
          .join('\n');

        const targetedPrompt = [
          config.prompt.split('\n')[0], // keep the first header line
          '',
          missing_fields.length > 0
            ? `To proceed, I need:\n${missingList}`
            : 'Please type your request below.',
        ].join('\n');

        const guidanceMsg: Message = {
          id: Date.now(),
          chat_id: activeChatId,
          role: 'assistant',
          content: targetedPrompt,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, guidanceMsg]);
        setPendingActionMode(mode);
        setValidatingMode(null);
        setTimeout(() => composerRef.current?.focus(), 50);
      }
    } catch (err) {
      // Validate endpoint failed — fall back to showing the full guidance prompt
      console.error('Validate action context failed:', err);
      setValidatingMode(null);
      const guidanceMsg: Message = {
        id: Date.now(),
        chat_id: activeChatId,
        role: 'assistant',
        content: config.prompt,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, guidanceMsg]);
      setPendingActionMode(mode);
      setTimeout(() => composerRef.current?.focus(), 50);
    }
  };

  /**
   * Directly executes a structured action (used when /validate says can_execute=true).
   * Shows the action as a user message then calls /actions/run.
   */
  const executePendingAction = async (
    mode: 'research' | 'email_draft' | 'task_list',
    message: string,
  ) => {
    if (activeChatId === null) return;
    setSending(true);

    const modeLabels: Record<string, string> = {
      research: '🔍 Research Company',
      email_draft: '✉️ Draft Email',
      task_list: '📋 Create Tasklist',
    };
    const tempId = Date.now();
    const tempUserMsg: Message = {
      id: tempId,
      chat_id: activeChatId,
      role: 'user',
      content: `${modeLabels[mode] || mode}: ${message}`,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      await apiClient.post('/actions/run', {
        chat_id: activeChatId,
        mode,
        message,
      });
      const refreshed = await apiClient.get<Message[]>(`/chats/${activeChatId}/messages`);
      setMessages(refreshed.data);
      const threadsRes = await apiClient.get<ChatThread[]>('/chats');
      setChats(threadsRes.data);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== tempId),
        { ...tempUserMsg, id: Date.now() },
        {
          id: Date.now() + 1,
          chat_id: activeChatId,
          role: 'assistant',
          content: '⚠️ Action execution failed. Please verify your API key configuration.',
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  if (loadingApp) {
    return <Spinner fullScreen />;
  }

  return (
    <AppLayout
      userEmail={userEmail}
      chats={chats}
      activeChatId={activeChatId}
      onSelectChat={(id) => {
        setActiveChatId(id);
        setShowMemorySettings(false);
      }}
      onCreateChat={() => handleCreateChat()}
      onDeleteChat={handleDeleteChat}
      onOpenMemorySettings={() => setShowMemorySettings(true)}
      onLogout={handleLogout}
    >
      {showMemorySettings ? (
        <MemoryManager onBackToChat={() => setShowMemorySettings(false)} />
      ) : activeChatId === null ? (
        <div className="empty-chat-welcome animate-fade-in">
          <div className="welcome-logo-badge">
            <Brain size={32} />
          </div>
          <h2>Business Research Copilot</h2>
          <p>Please create or select a research thread from the sidebar to get started.</p>
          <button className="glow-btn-base glow-btn" onClick={() => handleCreateChat()}>
            Create Research Thread
          </button>
        </div>
      ) : (
        <div className="chat-workspace-container">
          {/* Header */}
          <header className="chat-header-bar">
            <div className="chat-header-info">
              <h3>{chats.find((c) => c.id === activeChatId)?.title || 'Untitled Thread'}</h3>
            </div>
            <div>
              <button 
                className="delete-memory-btn" 
                onClick={() => handleDeleteChat(activeChatId)} 
                title="Delete chat thread"
                style={{ color: 'var(--text-muted)' }}
              >
                <Trash2 size={16} />
              </button>
            </div>
          </header>

          {/* Messages Grid */}
          <div className="messages-list-wrapper">
            {loadingMessages ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: '60px' }}>
                <Spinner size="md" />
              </div>
            ) : messages.length === 0 ? (
              <div className="empty-chat-welcome">
                <div className="welcome-logo-badge">
                  <Sparkles size={32} />
                </div>
                <h2>Explore target business insights</h2>
                <p>
                  Start by typing a company name and prompt below, or select one of the suggested starter prompts to test tool routing.
                </p>
                <div className="suggested-starters-grid">
                  <div 
                    className="glass-panel starter-card" 
                    onClick={() => handleSendMessage('Research Razorpay and suggest outreach angles for sales automation')}
                  >
                    <h4>Research Razorpay</h4>
                    <p>Scrapes organic company data & suggests angles</p>
                  </div>
                  <div 
                    className="glass-panel starter-card"
                    onClick={() => handleSendMessage('Research HubSpot recent priorities & pain points')}
                  >
                    <h4>Research HubSpot</h4>
                    <p>Crawl announcements to infer company needs</p>
                  </div>
                  <div 
                    className="glass-panel starter-card"
                    onClick={() => handleSendMessage('Draft cold email for Stripe SaaS prospects')}
                  >
                    <h4>Sales copywriting</h4>
                    <p>Creates tailored email drafts using company findings</p>
                  </div>
                  <div 
                    className="glass-panel starter-card"
                    onClick={() => handleSendMessage('Create tasks list to prepare for product demo with Microsoft')}
                  >
                    <h4>Task Checklists</h4>
                    <p>Compiles actionable checklist items</p>
                  </div>
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className={`message-card message-${msg.role}`}>
                  <div className={`avatar-badge avatar-badge-${msg.role}`}>
                    {msg.role === 'user' ? 'U' : 'AI'}
                  </div>
                  <div className="message-body-content">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        // Custom link renderer: citation links like [[1]](url) become
                        // superscript badge numbers; all other links open in new tab.
                        a: ({ href, children }) => {
                          const text = String(children ?? '');
                          // A citation link has text matching [N]
                          const citationMatch = text.match(/^\[(\d+)\]$/);
                          if (citationMatch && href) {
                            return (
                              <a
                                href={href}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="citation-superscript"
                                title={`Source ${citationMatch[1]}: ${href}`}
                              >
                                {citationMatch[1]}
                              </a>
                            );
                          }
                          return (
                            <a href={href} target="_blank" rel="noopener noreferrer">
                              {children}
                            </a>
                          );
                        },
                      }}
                    >
                      {msg.role === 'assistant' && msg.metadata_json?.sources
                        ? processCitationLinks(msg.content, msg.metadata_json.sources)
                        : msg.content}
                    </ReactMarkdown>

                    {/* ChatGPT-style numbered footnotes */}
                    {msg.role === 'assistant' && msg.metadata_json?.sources && msg.metadata_json.sources.length > 0 && (
                      <div className="citations-footnotes">
                        <div className="citations-footnotes-header">
                          <ExternalLink size={12} />
                          <span>Sources</span>
                        </div>
                        <div className="citations-footnotes-list">
                          {msg.metadata_json.sources.map((src, sIdx) => (
                            <a
                              key={sIdx}
                              href={src.link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="citation-footnote-row"
                              title={src.snippet}
                            >
                              <span className="citation-footnote-number">{sIdx + 1}</span>
                              <span className="citation-footnote-text">
                                <span className="citation-footnote-title">{src.title || getDomain(src.link)}</span>
                                <span className="citation-footnote-domain">{getDomain(src.link)}</span>
                              </span>
                              <ExternalLink size={11} className="citation-footnote-icon" />
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {/* Spinner indicator when agent is processing */}
            {sending && (
              <div className="message-card message-assistant">
                <div className="avatar-badge avatar-badge-assistant">AI</div>
                <div className="message-body-content" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Spinner size="sm" />
                  <span className="spinner-text" style={{ fontStyle: 'italic' }}>
                    Agent routing & evaluating validation criteria...
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Composer Box */}
          <footer className="chat-composer-footer">
            {/* Action pill buttons */}
            <div className="composer-action-bar">
              <button
                id="action-btn-research"
                className={`action-pill-btn ${pendingActionMode === 'research' ? 'action-pill-active' : ''}`}
                onClick={() => handleAction('research')}
                disabled={sending || validatingMode !== null}
              >
                {validatingMode === 'research' ? <Spinner size="sm" /> : <Search size={14} />}
                <span>{validatingMode === 'research' ? 'Checking context…' : 'Research Company'}</span>
              </button>
              <button
                id="action-btn-email"
                className={`action-pill-btn ${pendingActionMode === 'email_draft' ? 'action-pill-active' : ''}`}
                onClick={() => handleAction('email_draft')}
                disabled={sending || validatingMode !== null}
              >
                {validatingMode === 'email_draft' ? <Spinner size="sm" /> : <Mail size={14} />}
                <span>{validatingMode === 'email_draft' ? 'Checking context…' : 'Draft Email'}</span>
              </button>
              <button
                id="action-btn-tasklist"
                className={`action-pill-btn ${pendingActionMode === 'task_list' ? 'action-pill-active' : ''}`}
                onClick={() => handleAction('task_list')}
                disabled={sending || validatingMode !== null}
              >
                {validatingMode === 'task_list' ? <Spinner size="sm" /> : <CheckSquare size={14} />}
                <span>{validatingMode === 'task_list' ? 'Checking context…' : 'Create Tasklist'}</span>
              </button>
            </div>

            {/* Active mode indicator strip */}
            {pendingActionMode && (
              <div className="active-mode-strip animate-fade-in">
                <span className="active-mode-label">
                  {ACTION_CONFIG[pendingActionMode].icon}
                  {ACTION_CONFIG[pendingActionMode].label} mode active — type your input below
                </span>
                <button
                  className="active-mode-cancel"
                  onClick={() => setPendingActionMode(null)}
                  title="Cancel action mode"
                >
                  ✕
                </button>
              </div>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage(composerText);
              }}
              className="composer-input-row"
            >
              <textarea
                ref={composerRef}
                className="composer-textarea"
                rows={1}
                placeholder={
                  pendingActionMode
                    ? ACTION_CONFIG[pendingActionMode].placeholder
                    : 'Ask research questions, discuss targets, or click quick action buttons…'
                }
                value={composerText}
                onChange={(e) => setComposerText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage(composerText);
                  }
                }}
              />
              <button type="submit" className="send-message-btn" disabled={!composerText.trim() || sending}>
                <Send size={16} />
              </button>
            </form>
          </footer>
        </div>
      )}
    </AppLayout>
  );
};
export default Chat;
