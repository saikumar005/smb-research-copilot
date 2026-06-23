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
  Sparkles,
  X,
  Loader2,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react';
import { apiClient, logger_session_expiry, getGmailStatus, getGmailConnectUrl, parseDraft, sendGmailEmail, submitFeedback } from '../api/client';
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
    user_feedback?: number;
    langfuse_trace_id?: string;
  };
  created_at: string;
}

/** Helper to extract plain text string from any nested ReactNode children. */
const getChildrenText = (node: any): string => {
  if (node == null) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(getChildrenText).join('');
  if (node.props && node.props.children) return getChildrenText(node.props.children);
  return '';
};

/**
 * Rewrites citation references in AI response text into clickable markdown links.
 * Handles: (Source 1), (Source 2), [1], [2], Source 1, Source 2
 * Converts them to [[1]](url) which ReactMarkdown renders as a link.
 * Performs a single-pass regex replacement, skipping already-formatted links to prevent double-wrapping.
 */
function processCitationLinks(content: string, sources: Source[]): string {
  if (!sources || sources.length === 0) return content;

  // Single-pass regex to match:
  // 1. Existing [[N]](url) or [N](url) links (so we can skip them)
  // 2. Various unlinked citation formats: [Source N], (Source N), Source [N], [N], Source N
  const regex = /\[\[\d+\]\]\([^)]+\)|\[\d+\]\([^)]+\)|(?:Source\s+)?\[(?:Source\s+)?(\d+)\]|\(Source\s+(\d+)\)|\[(\d+)\](?!\()|\bSource\s+(\d+)\b/gi;

  return content.replace(regex, (match, p1, p2, p3, p4) => {
    // If it's already a markdown link, keep it exactly as-is
    if (match.startsWith('[') && match.includes('](')) {
      return match;
    }

    // Extract citation number from whichever capture group matched
    const num = p1 || p2 || p3 || p4;
    if (num) {
      const idx = parseInt(num, 10) - 1;
      if (idx >= 0 && idx < sources.length) {
        return `[${num}](${sources[idx].link})`;
      }
    }
    return match;
  });
}

/** Extract a short readable domain name from a URL.
 * Strips www. and common subdomains like en. m. for cleaner badge display. */
function getDomain(url: string): string {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '');
    // Strip single-letter subdomains like en. m. fr. etc.
    return host.replace(/^[a-z]{1,2}\./, '');
  } catch {
    return url;
  }
}

/** Perplexity-style inline citation badge with hover popover */
const CitationBadge: React.FC<{
  num: string;
  source?: Source;
  href: string;
}> = ({ num, source, href }) => {
  const [hovered, setHovered] = React.useState(false);
  const domain = source ? getDomain(source.link) : href;

  return (
    <span
      className="citation-badge-wrapper"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="citation-badge"
        onClick={(e) => e.stopPropagation()}
      >
        <span className="citation-badge-num">{num}</span>
        <span className="citation-badge-domain">{domain}</span>
      </a>
      {hovered && source && (
        <div className="citation-popover">
          <div className="citation-popover-title">{source.title || domain}</div>
          {source.snippet && (
            <div className="citation-popover-snippet">
              {source.snippet.length > 130 ? source.snippet.slice(0, 130) + '…' : source.snippet}
            </div>
          )}
          <div className="citation-popover-link">{domain}</div>
        </div>
      )}
    </span>
  );
};

/** Compact collapsible sources toggle (replaces old SOURCES block) */
const SourcesToggle: React.FC<{ sources: Source[] }> = ({ sources }) => {
  if (!sources || sources.length === 0) return null;
  return (
    <details className="sources-toggle">
      <summary className="sources-toggle-summary">
        <ExternalLink size={10} />
        {sources.length} source{sources.length !== 1 ? 's' : ''}
      </summary>
      <div className="sources-toggle-list">
        {sources.map((src, i) => (
          <a
            key={i}
            href={src.link}
            target="_blank"
            rel="noopener noreferrer"
            className="sources-toggle-row"
          >
            <span className="sources-toggle-num">{i + 1}</span>
            <span className="sources-toggle-title">{src.title || getDomain(src.link)}</span>
            <span className="sources-toggle-domain">{getDomain(src.link)}</span>
          </a>
        ))}
      </div>
    </details>
  );
};

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
  // Creating chat guard — prevents double-clicks on "New Research Chat"
  const [creatingChat, setCreatingChat] = useState(false);
  // Global toast notification queue
  const [toasts, setToasts] = useState<{ id: string; message: string; type: 'success' | 'error' | 'info' }[]>([]);
  
  // Real-time output and reasoning streaming states
  const [streamingThoughts, setStreamingThoughts] = useState<string[]>([]);
  const [streamingSources, setStreamingSources] = useState<Source[]>([]);
  // Single active content string — gets reset & rebuilt cleanly on each new writer attempt
  const [activeContent, setActiveContent] = useState<string>('');
  // Track which attempt number (1-indexed) we're on for display
  const [attemptNumber, setAttemptNumber] = useState<number>(0);
  // True when a new writer attempt is starting after a failed judge pass
  const [isRefining, setIsRefining] = useState<boolean>(false);
  // Whether streaming content has started (controls thoughts accordion open state)
  const [contentStarted, setContentStarted] = useState<boolean>(false);

  // ── Gmail integration state ───────────────────────────────────────────────
  const [gmailConnected, setGmailConnected] = useState(false);
  const [sendModal, setSendModal] = useState<{
    open: boolean;
    draft: string;
    subject: string;
    body: string;
    to: string;
    cc: string;
    loading: boolean;
    parsing: boolean;
  }>({
    open: false,
    draft: '',
    subject: '',
    body: '',
    to: '',
    cc: '',
    loading: false,
    parsing: false,
  });
  
  const renderMarkdown = (content: string, sources: Source[] = []) => {
    const processed = processCitationLinks(content, sources);
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => {
            const text = getChildrenText(children);
            const citationMatch = text.match(/^\[?(\d+)\]?$/);
            if (citationMatch && href) {
              // Render as Perplexity-style inline source pill with hover popover
              const idx = parseInt(citationMatch[1], 10) - 1;
              const source = sources[idx];
              return <CitationBadge num={citationMatch[1]} source={source} href={href} />;
            }
            return (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {processed}
      </ReactMarkdown>
    );
  };
  
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

  /**
   * Shows a toast notification that auto-dismisses after `duration` ms.
   */
  const showToast = (
    message: string,
    type: 'success' | 'error' | 'info' = 'info',
    duration = 4000,
  ) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), duration);
  };

  const handleCreateChat = async (title?: string) => {
    if (creatingChat) return; // guard against double-clicks
    setCreatingChat(true);
    try {
      const res = await apiClient.post<ChatThread>('/chats', {
        title: title || 'New Research Thread',
      });
      setChats((prev) => [res.data, ...prev]);
      setActiveChatId(res.data.id);
      setShowMemorySettings(false);
      showToast('Research thread created. Start typing to begin!', 'success');
    } catch (err: unknown) {
      console.error('Failed to create chat thread:', err);
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Could not create a new research thread. Please check your connection and try again.';
      showToast(detail, 'error');
    } finally {
      setCreatingChat(false);
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

  const runWorkflowStream = async (streamUrl: string, bodyData: any, tempUserMsg: Message) => {
    const token = localStorage.getItem('token');
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

    try {
      setStreamingThoughts([]);
      setStreamingSources([]);
      setActiveContent('');
      setAttemptNumber(0);
      setIsRefining(false);
      setContentStarted(false);
      const response = await fetch(`${baseUrl}${streamUrl}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(bodyData)
      });

      if (response.status === 401) {
        logger_session_expiry();
        return;
      }

      if (!response.ok) {
        throw new Error(`Streaming request failed with status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('Response body reader is not available.');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;

          try {
            const rawJson = trimmed.slice(6);
            const parsed = JSON.parse(rawJson);

            if (parsed.type === 'status') {
              // Always add status messages to thinking steps — validation failures are shown there, not as banners
              setStreamingThoughts((prev) => [...prev, parsed.message]);
              // If a new self-correction is starting, show the refining indicator
              if (parsed.message.toLowerCase().includes('triggering self-correction') ||
                  parsed.message.toLowerCase().includes('self-correction')) {
                setIsRefining(true);
              }
            } else if (parsed.type === 'stream_start') {
              // New writer attempt starting — clear previous content and start fresh
              setAttemptNumber((prev) => prev + 1);
              setActiveContent('');
              setIsRefining(false);
              setContentStarted(false);
            } else if (parsed.type === 'token') {
              setActiveContent((prev) => prev + parsed.content);
              setContentStarted(true);
            } else if (parsed.type === 'done') {
              if (parsed.metadata_json?.sources) {
                setStreamingSources(parsed.metadata_json.sources);
              }
              setIsRefining(false);
            }
          } catch (e) {
            console.error('Error parsing stream line:', line, e);
          }
        }
      }

      // Reload messages & chats after done
      const refreshed = await apiClient.get<Message[]>(`/chats/${activeChatId}/messages`);
      setMessages(refreshed.data);
      const threadsRes = await apiClient.get<ChatThread[]>('/chats');
      setChats(threadsRes.data);

    } catch (err) {
      console.error(err);
      setMessages((prev) => [
        ...prev.filter(m => m.id !== tempUserMsg.id),
        tempUserMsg,
        {
          id: Date.now() + 1,
          chat_id: activeChatId!,
          role: 'assistant',
          content: '⚠️ Streaming execution failed. Please verify your API key configuration.',
          created_at: new Date().toISOString()
        }
      ]);
    } finally {
      setSending(false);
      setStreamingThoughts([]);
      setStreamingSources([]);
      setActiveContent('');
      setAttemptNumber(0);
      setIsRefining(false);
      setContentStarted(false);
    }
  };

  const handleSendMessage = async (text: string) => {
    if (!text.trim() || activeChatId === null || sending) return;
    
    setComposerText('');
    setSending(true);
    
    // If an action mode is pending, this message is the user's input for that action.
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

    if (activeMode) {
      await runWorkflowStream('/actions/run/stream', {
        chat_id: activeChatId,
        mode: activeMode,
        message: text
      }, tempUserMsg);
    } else {
      await runWorkflowStream(`/chats/${activeChatId}/messages/stream`, {
        content: text
      }, tempUserMsg);
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

    await runWorkflowStream('/actions/run/stream', {
      chat_id: activeChatId,
      mode,
      message,
    }, tempUserMsg);
  };

  const handleFeedback = async (messageId: number, score: number) => {
    try {
      const msg = messages.find(m => m.id === messageId);
      if (!msg) return;

      const currentFeedback = msg.metadata_json?.user_feedback;
      const targetScore = currentFeedback === score ? 0 : score;

      await submitFeedback(messageId, targetScore);

      setMessages(prev => prev.map(m => {
        if (m.id === messageId) {
          const updatedMeta = { 
            ...(m.metadata_json || {}), 
            user_feedback: targetScore 
          };
          return { ...m, metadata_json: updatedMeta };
        }
        return m;
      }));

      if (targetScore !== 0) {
        showToast('Feedback submitted successfully! ✓', 'success');
      }
    } catch (err) {
      console.error('Failed to submit feedback:', err);
      showToast('Could not record feedback.', 'error');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  // ── Gmail handlers ────────────────────────────────────────────────────────

  /** Open the OAuth popup to connect Gmail via Composio */
  const handleConnectGmail = async () => {
    try {
      const { redirect_url } = await getGmailConnectUrl();
      // Open in a popup; after OAuth, Composio redirects to their success page
      const popup = window.open(redirect_url, 'gmail-oauth', 'width=600,height=700');
      // Poll until the popup closes, then re-check connection status
      const interval = setInterval(async () => {
        if (!popup || popup.closed) {
          clearInterval(interval);
          const { connected } = await getGmailStatus();
          setGmailConnected(connected);
          if (connected) showToast('Gmail connected successfully! ✓', 'success');
        }
      }, 1000);
    } catch (err) {
      showToast('Failed to start Gmail connection. Check that COMPOSIO_API_KEY is set.', 'error');
    }
  };

  /** Open the Send modal for an email_draft message */
  const handleOpenSendModal = async (msg: Message) => {
    setSendModal(prev => ({ ...prev, open: true, draft: msg.content, subject: '', body: '', to: '', cc: '', parsing: true, loading: false }));
    try {
      const { subject, body } = await parseDraft(msg.content);
      setSendModal(prev => ({ ...prev, subject, body, parsing: false }));
    } catch {
      setSendModal(prev => ({ ...prev, subject: 'Outreach Email', body: msg.content, parsing: false }));
    }
  };

  /** Execute the send via Composio GMAIL_SEND_EMAIL */
  const handleSendGmail = async () => {
    if (!sendModal.to) {
      showToast('Please enter a recipient email address.', 'error');
      return;
    }
    setSendModal(prev => ({ ...prev, loading: true }));
    try {
      const result = await sendGmailEmail({
        to: sendModal.to,
        subject: sendModal.subject,
        body: sendModal.body,
        cc: sendModal.cc || undefined,
      });
      setSendModal(prev => ({ ...prev, open: false, loading: false }));
      showToast(`✓ ${result.message || 'Email sent successfully!'}`, 'success');
    } catch (err: any) {
      setSendModal(prev => ({ ...prev, loading: false }));
      const detail = err?.response?.data?.detail || 'Failed to send email.';
      showToast(detail, 'error');
    }
  };

  if (loadingApp) {
    return <Spinner fullScreen />;
  }

  return (
    <>
      {/* Global Toast Notifications — positioned top-right, above everything */}
      <div
        style={{
          position: 'fixed',
          top: '16px',
          right: '16px',
          zIndex: 9999,
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          maxWidth: '360px',
          width: 'calc(100% - 32px)',
          pointerEvents: 'none',
        }}
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast-card toast-${toast.type} animate-fade-in`}
            style={{ pointerEvents: 'auto' }}
          >
            <span className="toast-text">{toast.message}</span>
            <button
              className="toast-close-btn"
              onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        ))}
      </div>

      {/* ── Send via Gmail Modal ──────────────────────────────────────────── */}
      {sendModal.open && (
        <div className="send-email-modal-overlay" onClick={() => setSendModal(prev => ({ ...prev, open: false }))}>
          <div className="send-email-modal" onClick={e => e.stopPropagation()}>
            <div className="send-email-modal-header">
              <div className="send-email-modal-title">
                <Mail size={16} style={{ color: 'var(--accent-purple)' }} />
                Send Email via Gmail
              </div>
              <button
                className="send-email-modal-close"
                onClick={() => setSendModal(prev => ({ ...prev, open: false }))}
                aria-label="Close"
              >
                <X size={16} />
              </button>
            </div>

            {sendModal.parsing ? (
              <div className="send-email-modal-parsing">
                <Loader2 size={20} className="spin-icon" style={{ color: 'var(--accent-purple)' }} />
                <span>Parsing email draft…</span>
              </div>
            ) : (
              <div className="send-email-modal-body">
                <div className="send-email-field">
                  <label className="send-email-label">To *</label>
                  <input
                    id="gmail-to"
                    type="email"
                    className="send-email-input"
                    placeholder="recipient@company.com"
                    value={sendModal.to}
                    onChange={e => setSendModal(prev => ({ ...prev, to: e.target.value }))}
                    autoFocus
                  />
                </div>
                <div className="send-email-field">
                  <label className="send-email-label">CC</label>
                  <input
                    id="gmail-cc"
                    type="email"
                    className="send-email-input"
                    placeholder="cc@company.com (optional)"
                    value={sendModal.cc}
                    onChange={e => setSendModal(prev => ({ ...prev, cc: e.target.value }))}
                  />
                </div>
                <div className="send-email-field">
                  <label className="send-email-label">Subject</label>
                  <input
                    id="gmail-subject"
                    type="text"
                    className="send-email-input"
                    value={sendModal.subject}
                    onChange={e => setSendModal(prev => ({ ...prev, subject: e.target.value }))}
                  />
                </div>
                <div className="send-email-field">
                  <label className="send-email-label">Body</label>
                  <textarea
                    id="gmail-body"
                    className="send-email-textarea"
                    rows={10}
                    value={sendModal.body}
                    onChange={e => setSendModal(prev => ({ ...prev, body: e.target.value }))}
                  />
                </div>
              </div>
            )}

            <div className="send-email-modal-footer">
              <button
                className="send-email-cancel-btn"
                onClick={() => setSendModal(prev => ({ ...prev, open: false }))}
                disabled={sendModal.loading}
              >
                Cancel
              </button>
              <button
                className="send-email-send-btn"
                onClick={handleSendGmail}
                disabled={sendModal.loading || sendModal.parsing || !sendModal.to}
              >
                {sendModal.loading ? (
                  <><Loader2 size={14} className="spin-icon" /> Sending…</>
                ) : (
                  <><Mail size={14} /> Send Email</>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      <AppLayout
        userEmail={userEmail}
        chats={chats}
        activeChatId={activeChatId}
        creatingChat={creatingChat}
        onSelectChat={(id) => {
          setActiveChatId(id);
          setShowMemorySettings(false);
        }}
        onCreateChat={() => handleCreateChat()}
        onDeleteChat={handleDeleteChat}
        onOpenMemorySettings={() => setShowMemorySettings(true)}
        onLogout={handleLogout}
        gmailConnected={gmailConnected}
        onConnectGmail={handleConnectGmail}
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
                    {msg.role === 'assistant'
                      ? renderMarkdown(msg.content, msg.metadata_json?.sources)
                      : <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>}
                    {/* Compact collapsible sources toggle — replaces old numbered SOURCES block */}
                    {msg.role === 'assistant' && msg.metadata_json?.sources && (
                      <SourcesToggle sources={msg.metadata_json.sources} />
                    )}
                    {/* User feedback buttons */}
                    {msg.role === 'assistant' && (
                      <div className="message-feedback-row">
                        <button
                          className={`feedback-btn ${msg.metadata_json?.user_feedback === 1 ? 'active' : ''}`}
                          onClick={() => handleFeedback(msg.id, 1)}
                          title="Thumbs up"
                        >
                          <ThumbsUp size={12} />
                        </button>
                        <button
                          className={`feedback-btn ${msg.metadata_json?.user_feedback === -1 ? 'active' : ''}`}
                          onClick={() => handleFeedback(msg.id, -1)}
                          title="Thumbs down"
                        >
                          <ThumbsDown size={12} />
                        </button>
                      </div>
                    )}
                    {/* Send via Gmail button — only on email_draft messages */}
                    {msg.role === 'assistant' && msg.metadata_json?.action_mode === 'email_draft' && (
                      <div className="send-gmail-action-row">
                        {gmailConnected ? (
                          <button
                            className="send-gmail-btn"
                            onClick={() => handleOpenSendModal(msg)}
                            title="Send this email via your connected Gmail account"
                          >
                            <Mail size={13} />
                            Send via Gmail
                          </button>
                        ) : (
                          <button
                            className="send-gmail-btn send-gmail-btn-connect"
                            onClick={handleConnectGmail}
                            title="Connect Gmail to send this email"
                          >
                            <Mail size={13} />
                            Connect Gmail to Send
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {/* Streaming assistant response bubble */}
            {sending && (
              <div className="message-card message-assistant animate-fade-in">
                <div className="avatar-badge avatar-badge-assistant">AI</div>
                <div className="message-body-content" style={{ display: 'flex', flexDirection: 'column', gap: '12px', width: '100%' }}>
                  
                  {/* Collapsible thoughts list — auto-collapses when content begins streaming */}
                  {streamingThoughts.length > 0 ? (
                    <details className="agent-thoughts-details" open={!contentStarted} style={{ width: '100%' }}>
                      <summary className="agent-thoughts-summary">
                        <Brain size={14} className={contentStarted ? '' : 'spin-icon'} style={{ color: 'var(--accent-purple)' }} />
                        <span>Agent Thinking Steps ({streamingThoughts.length})</span>
                        {contentStarted && (
                          <span style={{
                            marginLeft: 'auto',
                            fontSize: '10px',
                            color: 'var(--text-muted)',
                            fontWeight: 400
                          }}>click to expand</span>
                        )}
                      </summary>
                      <div className="agent-thoughts-list">
                        {streamingThoughts.map((thought, idx) => (
                          <div key={idx} className="agent-thought-step">
                            <span className="agent-thought-bullet">✓</span>
                            <span className="agent-thought-text">{thought}</span>
                          </div>
                        ))}
                      </div>
                    </details>
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Spinner size="sm" />
                      <span className="spinner-text" style={{ fontStyle: 'italic' }}>
                        Initializing multi-agent workflow...
                      </span>
                    </div>
                  )}

                  {/* Main streaming content area — single seamless view like ChatGPT/Perplexity */}
                  {(activeContent || isRefining) && (
                    <div className="active-draft-container animate-fade-in">
                      {/* Subtle attempt/refining header — only shown when actively composing */}
                      <div className="active-draft-header" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Sparkles size={12} className="spin-icon" />
                        {isRefining ? (
                          <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Refining response...</span>
                        ) : attemptNumber > 1 ? (
                          <span>Composing improved draft...</span>
                        ) : (
                          <span>Composing response...</span>
                        )}
                      </div>
                      <div className="streaming-markdown-content">
                        {renderMarkdown(activeContent, streamingSources)}
                      </div>
                    </div>
                  )}

                  {/* Compact collapsible sources toggle — shown after streaming completes */}
                  {streamingSources.length > 0 && (
                    <SourcesToggle sources={streamingSources} />
                  )}
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
    </>
  );
};
export default Chat;
