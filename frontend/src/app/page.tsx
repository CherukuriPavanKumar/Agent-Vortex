"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import styles from "./page.module.css";

const API = "http://localhost:8000";

// ==========================================================
// Types
// ==========================================================

type Message = {
  role: "user" | "assistant";
  content: string;
};

type Conversation = {
  id: string;
  title: string;
  created_at: string;
};

type Interrupt = {
  risk_level: string;
  plan: string[];
  planned_tools: string[];
};

// ==========================================================
// Auth helpers
// ==========================================================

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("agent_token");
}

function setToken(token: string) {
  localStorage.setItem("agent_token", token);
}

function clearToken() {
  localStorage.removeItem("agent_token");
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) return { "Content-Type": "application/json" };
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

// ==========================================================
// Component
// ==========================================================

export default function Home() {
  // Auth state
  const [authenticated, setAuthenticated] = useState(false);
  const [authChecking, setAuthChecking] = useState(true);
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState("");

  // Sidebar state
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Chat state
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [interrupt, setInterrupt] = useState<Interrupt | null>(null);
  const [streamingContent, setStreamingContent] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const prevConvoRef = useRef<string | null>(null);

  // ----------------------------------------------------------
  // Auto-scroll
  // ----------------------------------------------------------
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, interrupt]);

  // ----------------------------------------------------------
  // Check existing auth on mount
  // ----------------------------------------------------------
  useEffect(() => {
    const checkAuth = async () => {
      const token = getToken();
      if (!token) {
        // Try unauthenticated — maybe password is disabled
        try {
          const res = await fetch(`${API}/api/conversations`);
          if (res.ok) {
            setAuthenticated(true);
          }
        } catch {
          // Backend not reachable
        }
        setAuthChecking(false);
        return;
      }

      try {
        const res = await fetch(`${API}/api/conversations`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          setAuthenticated(true);
        } else {
          clearToken();
        }
      } catch {
        // Backend not reachable
      }
      setAuthChecking(false);
    };
    checkAuth();
  }, []);

  // ----------------------------------------------------------
  // Load conversations after auth
  // ----------------------------------------------------------
  useEffect(() => {
    if (authenticated) {
      fetchConversations();
    }
  }, [authenticated]);

  const fetchConversations = async () => {
    try {
      const res = await fetch(`${API}/api/conversations`, {
        headers: authHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch (err) {
      console.error("Failed to fetch conversations", err);
    }
  };

  // ----------------------------------------------------------
  // Login
  // ----------------------------------------------------------
  const handleLogin = async () => {
    setAuthError("");
    try {
      const res = await fetch(`${API}/api/auth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });

      if (res.ok) {
        const data = await res.json();
        if (data.token) {
          setToken(data.token);
        }
        setAuthenticated(true);
      } else {
        setAuthError("Wrong password");
      }
    } catch {
      setAuthError("Cannot connect to backend");
    }
  };

  // ----------------------------------------------------------
  // Memory extraction on conversation switch
  // ----------------------------------------------------------
  const extractMemories = async (convoId: string) => {
    try {
      await fetch(`${API}/api/conversations/${convoId}/memories`, {
        method: "POST",
        headers: authHeaders(),
      });
    } catch {
      // Silent fail — memory extraction is best-effort
    }
  };

  // ----------------------------------------------------------
  // Create new conversation
  // ----------------------------------------------------------
  const startNewConversation = async () => {
    // Extract memories from previous conversation
    if (prevConvoRef.current) {
      extractMemories(prevConvoRef.current);
    }

    try {
      const res = await fetch(`${API}/api/conversations`, {
        method: "POST",
        headers: authHeaders(),
      });
      const data = await res.json();
      setConversationId(data.id);
      prevConvoRef.current = data.id;
      setMessages([]);
      setInterrupt(null);
      setStreamingContent("");
      fetchConversations();

      // Close sidebar on mobile
      if (window.innerWidth <= 768) setSidebarOpen(false);
    } catch (err) {
      console.error("Failed to create conversation", err);
    }
  };

  // ----------------------------------------------------------
  // Select existing conversation
  // ----------------------------------------------------------
  const selectConversation = async (id: string) => {
    // Extract memories from previous conversation
    if (prevConvoRef.current && prevConvoRef.current !== id) {
      extractMemories(prevConvoRef.current);
    }

    setConversationId(id);
    prevConvoRef.current = id;
    setMessages([]);
    setInterrupt(null);
    setStreamingContent("");
    setLoading(true);

    // Close sidebar on mobile
    if (window.innerWidth <= 768) setSidebarOpen(false);

    try {
      const res = await fetch(`${API}/api/chat/${id}`, {
        headers: authHeaders(),
      });
      const data = await res.json();
      setMessages(data.messages || []);
      if (data.interrupt) {
        setInterrupt(data.interrupt);
      }
    } catch (err) {
      console.error("Failed to load history", err);
    } finally {
      setLoading(false);
    }
  };

  // ----------------------------------------------------------
  // Send message (SSE streaming)
  // ----------------------------------------------------------
  const sendMessage = useCallback(async () => {
    if (!input.trim() || !conversationId || loading) return;

    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);
    setStreamingContent("");

    // Reset textarea height
    const textarea = document.querySelector("textarea");
    if (textarea) textarea.style.height = "auto";

    try {
      const headers = authHeaders();
      const res = await fetch(`${API}/api/chat/${conversationId}/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({ message: userMsg }),
      });

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let accumulated = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          try {
            const event = JSON.parse(raw);

            if (event.type === "token") {
              accumulated += event.content;
              setStreamingContent(accumulated);
            } else if (event.type === "interrupt") {
              setStreamingContent("");
              setInterrupt({
                risk_level: event.risk_level,
                plan: event.plan,
                planned_tools: event.planned_tools,
              });
            } else if (event.type === "done") {
              const finalContent = event.content || accumulated;
              setStreamingContent("");
              setMessages((prev) => [
                ...prev,
                { role: "assistant", content: finalContent },
              ]);
            } else if (event.type === "title") {
              // Update sidebar with the generated title
              setConversations((prev) =>
                prev.map((c) =>
                  c.id === conversationId
                    ? { ...c, title: event.content }
                    : c
                )
              );
            } else if (event.type === "error") {
              setStreamingContent("");
              setMessages((prev) => [
                ...prev,
                { role: "assistant", content: `Error: ${event.content}` },
              ]);
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }
    } catch (err) {
      setStreamingContent("");
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Connection error. Is the backend running?" },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, conversationId, loading]);

  // ----------------------------------------------------------
  // Handle approval
  // ----------------------------------------------------------
  const handleApprove = async (approved: boolean) => {
    if (!conversationId) return;

    setInterrupt(null);
    setLoading(true);

    try {
      const res = await fetch(`${API}/api/approve/${conversationId}`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ approved }),
      });

      const data = await res.json();

      if (data.status === "success") {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.message },
        ]);
      } else if (data.status === "interrupt") {
        setInterrupt({
          risk_level: data.risk_level,
          plan: data.plan,
          planned_tools: data.planned_tools,
        });
      } else if (data.status === "error") {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error: ${data.error}` },
        ]);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Connection error." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // ----------------------------------------------------------
  // Textarea auto-resize & Enter to send
  // ----------------------------------------------------------
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };

  // ==========================================================
  // Auth Screen
  // ==========================================================

  if (authChecking) {
    return (
      <div className={styles.authScreen}>
        <div className={styles.authCard}>
          <div className={styles.authLogo}>AgentVortex</div>
          <p className={styles.authSubtext}>Connecting...</p>
        </div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className={styles.authScreen}>
        <div className={styles.authCard}>
          <div className={styles.authLogo}>AgentVortex</div>
          <p className={styles.authSubtext}>Enter your password to continue</p>

          <div className={styles.authForm}>
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
              className={styles.authInput}
              autoFocus
            />
            <button className={styles.authButton} onClick={handleLogin}>
              Unlock
            </button>
          </div>

          {authError && <p className={styles.authError}>{authError}</p>}
        </div>
      </div>
    );
  }

  // ==========================================================
  // Main App
  // ==========================================================

  return (
    <div className={styles.appLayout}>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className={styles.mobileOverlay}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ===== SIDEBAR ===== */}
      <aside className={`${styles.sidebar} ${sidebarOpen ? styles.sidebarOpen : styles.sidebarClosed}`}>
        <div className={styles.sidebarHeader}>
          <span className={styles.sidebarLogo}>AgentVortex</span>
          <button className={styles.sidebarToggle} onClick={() => setSidebarOpen(false)} title="Close sidebar">
            ✕
          </button>
        </div>

        <button className={styles.newChatBtn} onClick={startNewConversation}>
          + New Chat
        </button>

        <div className={styles.conversationList}>
          {conversations.map((convo) => (
            <button
              key={convo.id}
              className={`${styles.conversationItem} ${conversationId === convo.id ? styles.conversationActive : ""}`}
              onClick={() => selectConversation(convo.id)}
              title={convo.title}
            >
              <span className={styles.conversationTitle}>{convo.title}</span>
            </button>
          ))}

          {conversations.length === 0 && (
            <p className={styles.noConversations}>No conversations yet</p>
          )}
        </div>
      </aside>

      {/* ===== MAIN AREA ===== */}
      <main className={styles.main}>
        {/* Header */}
        <header className={styles.header}>
          {!sidebarOpen && (
            <button className={styles.menuBtn} onClick={() => setSidebarOpen(true)} title="Open sidebar">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
          )}
          <div className={styles.headerTitle}>
            {conversationId
              ? conversations.find((c) => c.id === conversationId)?.title || "Chat"
              : "AgentVortex"}
          </div>
        </header>

        {/* Messages */}
        <div className={styles.chatContainer}>
          <div className={styles.messagesList}>
            {!conversationId && messages.length === 0 && (
              <div className={styles.emptyState}>
                <div className={styles.emptyIcon}>⚡</div>
                <h2>Welcome to AgentVortex</h2>
                <p>Start a new conversation or select one from the sidebar.</p>
                <button className={styles.emptyNewChat} onClick={startNewConversation}>
                  + New Chat
                </button>
              </div>
            )}

            {conversationId && messages.length === 0 && !loading && (
              <div className={styles.emptyState}>
                <div className={styles.emptyIcon}>💬</div>
                <h2>Start chatting</h2>
                <p>Type a message below to begin.</p>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`${styles.messageWrapper} ${msg.role === "user" ? styles.wrapperUser : styles.wrapperAssistant}`}
              >
                <div className={`${styles.messageBubble} ${msg.role === "user" ? styles.userBubble : styles.assistantBubble}`}>
                  {msg.role === "assistant" ? (
                    <div className={styles.markdownBody}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            ))}

            {/* Streaming bubble */}
            {streamingContent && (
              <div className={`${styles.messageWrapper} ${styles.wrapperAssistant}`}>
                <div className={`${styles.messageBubble} ${styles.assistantBubble}`}>
                  <div className={styles.markdownBody}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {streamingContent}
                    </ReactMarkdown>
                  </div>
                  <span className={styles.cursor}>▊</span>
                </div>
              </div>
            )}

            {/* Loading dots */}
            {loading && !streamingContent && !interrupt && (
              <div className={`${styles.messageWrapper} ${styles.wrapperAssistant}`}>
                <div className={`${styles.messageBubble} ${styles.assistantBubble}`}>
                  <span className={styles.typingIndicator}>
                    <span></span><span></span><span></span>
                  </span>
                </div>
              </div>
            )}

            {/* Interrupt Card */}
            {interrupt && (
              <div className={styles.interruptCard}>
                <div className={styles.interruptHeader}>
                  <span className={styles.warningIcon}>⚠️</span>
                  <h3>Approval Required</h3>
                  <span className={`${styles.riskBadge} ${styles[`risk_${interrupt.risk_level || 'low'}`]}`}>
                    {(interrupt.risk_level || 'low').toUpperCase()}
                  </span>
                </div>

                <div className={styles.interruptBody}>
                  <h4>Planned Actions</h4>
                  <ol>
                    {interrupt.plan.map((step, i) => (
                      <li key={i}>{step}</li>
                    ))}
                  </ol>

                  <h4>Tools</h4>
                  <div className={styles.toolsList}>
                    {interrupt.planned_tools.map((tool, i) => (
                      <span key={i} className={styles.toolBadge}>{tool}</span>
                    ))}
                  </div>
                </div>

                <div className={styles.interruptActions}>
                  <button className={styles.btnDeny} onClick={() => handleApprove(false)}>
                    Deny
                  </button>
                  <button className={styles.btnApprove} onClick={() => handleApprove(true)}>
                    Approve & Execute
                  </button>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          {conversationId && (
            <div className={styles.inputArea}>
              <div className={styles.inputWrapper}>
                <textarea
                  rows={1}
                  placeholder="Type your message... (Shift+Enter for new line)"
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  disabled={loading || interrupt !== null}
                />
                <button
                  className={styles.sendButton}
                  onClick={sendMessage}
                  disabled={!input.trim() || loading || interrupt !== null}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 2L11 13" />
                    <path d="M22 2L15 22L11 13L2 9L22 2Z" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
