"use client";

import { useState, useEffect, useRef, useCallback, FormEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertCircle,
  ArrowUp,
  Calendar,
  Check,
  FileText,
  Globe,
  Mail,
  MessageCircle,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  ShieldAlert,
  Terminal,
  X,
} from "lucide-react";
import styles from "./page.module.css";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
// Static Capabilities & Starters (True to AgentVortex tools)
// ==========================================================

const CAPABILITIES = [
  {
    name: "Browser",
    description: "Navigate live sites, read pages, and extract structured content",
    Icon: Globe,
  },
  {
    name: "WhatsApp",
    description: "Send messages, files, reactions, search contacts, and manage groups",
    Icon: MessageCircle,
  },
  {
    name: "Gmail",
    description: "Search inbox threads and compose email replies",
    Icon: Mail,
  },
  {
    name: "Calendar",
    description: "Check upcoming schedule and create calendar events",
    Icon: Calendar,
  },
  {
    name: "Terminal",
    description: "Inspect files and execute local shell operations",
    Icon: Terminal,
  },
  {
    name: "Documents",
    description: "Generate formatted PDF reports and Excel workbooks",
    Icon: FileText,
  },
] as const;

const STARTER_PROMPTS = [
  "What are my most recent WhatsApp chats",
  "List my Google Calendar events for the next 7 days",
  "Browse https://news.ycombinator.com and summarize the top 5 stories",
] as const;

// ==========================================================
// Brand Mark (Flat geometric vortex aperture, no glow/gradient)
// ==========================================================

function VortexMark({ size = 18 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3a9 9 0 0 1 6.36 15.36" />
      <path d="M21 12a9 9 0 0 1-15.36 6.36" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

// ==========================================================
// Auth Helpers
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

function formatRiskLabel(level?: string): string {
  const normalized = (level || "low").toLowerCase();
  if (normalized === "high") return "High risk";
  if (normalized === "medium") return "Medium risk";
  return "Low risk";
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

  // Sidebar state (desktop defaults open; mobile drawer defaults closed)
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [desktopSidebarOpen, setDesktopSidebarOpen] = useState(true);
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  // Chat state
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [interrupt, setInterrupt] = useState<Interrupt | null>(null);
  const [streamingContent, setStreamingContent] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
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
  const fetchConversations = useCallback(async () => {
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
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    let active = true;
    const loadConversations = async () => {
      try {
        const res = await fetch(`${API}/api/conversations`, {
          headers: authHeaders(),
        });
        if (res.ok && active) {
          const data = await res.json();
          setConversations(data);
        }
      } catch (err) {
        console.error("Failed to fetch conversations", err);
      }
    };
    loadConversations();
    return () => {
      active = false;
    };
  }, [authenticated]);

  // ----------------------------------------------------------
  // Login
  // ----------------------------------------------------------
  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
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
        setAuthError("Incorrect password");
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
  const createConversationRecord = useCallback(async (): Promise<string | null> => {
    if (prevConvoRef.current) {
      extractMemories(prevConvoRef.current);
    }

    try {
      const res = await fetch(`${API}/api/conversations`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) return null;
      const data = await res.json();
      setConversationId(data.id);
      prevConvoRef.current = data.id;
      fetchConversations();
      return data.id;
    } catch (err) {
      console.error("Failed to create conversation", err);
      return null;
    }
  }, [fetchConversations]);

  const startNewConversation = async () => {
    const id = await createConversationRecord();
    if (!id) return;
    setMessages([]);
    setInterrupt(null);
    setStreamingContent("");

    if (window.innerWidth <= 768) setMobileDrawerOpen(false);
    textareaRef.current?.focus();
  };

  // ----------------------------------------------------------
  // Select existing conversation
  // ----------------------------------------------------------
  const selectConversation = async (id: string) => {
    if (prevConvoRef.current && prevConvoRef.current !== id) {
      extractMemories(prevConvoRef.current);
    }

    setConversationId(id);
    prevConvoRef.current = id;
    setMessages([]);
    setInterrupt(null);
    setStreamingContent("");
    setLoading(true);

    if (window.innerWidth <= 768) setMobileDrawerOpen(false);

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
    if (!input.trim() || loading || interrupt !== null) return;

    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);
    setStreamingContent("");

    if (
      textareaRef.current &&
      typeof CSS !== "undefined" &&
      !CSS.supports("field-sizing", "content")
    ) {
      textareaRef.current.style.height = "auto";
    }

    let activeConvoId = conversationId;
    if (!activeConvoId) {
      activeConvoId = await createConversationRecord();
      if (!activeConvoId) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "Could not start conversation thread." },
        ]);
        setLoading(false);
        return;
      }
    }

    try {
      const headers = authHeaders();
      const res = await fetch(`${API}/api/chat/${activeConvoId}/stream`, {
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
              const targetId = activeConvoId;
              setConversations((prev) =>
                prev.map((c) =>
                  c.id === targetId ? { ...c, title: event.content } : c
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
    } catch {
      setStreamingContent("");
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Connection error. Check that the backend service is running.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, conversationId, loading, interrupt, createConversationRecord]);

  const handleComposerSubmit = (e: FormEvent) => {
    e.preventDefault();
    sendMessage();
  };

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
  // IME-safe Enter to submit & auto-resize fallback
  // ----------------------------------------------------------
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (e.nativeEvent.isComposing || e.keyCode === 229) {
        return;
      }
      formRef.current?.requestSubmit();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    if (typeof CSS !== "undefined" && !CSS.supports("field-sizing", "content")) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
    }
  };

  const handleSelectStarter = (promptText: string) => {
    setInput(promptText);
    textareaRef.current?.focus();
  };

  // ==========================================================
  // Auth Screen
  // ==========================================================

  if (authChecking) {
    return (
      <main className={styles.authScreen}>
        <div className={styles.authCard}>
          <div className={styles.authHeader}>
            <div className={styles.authLogoRow}>
              <span className={styles.brandMark}>
                <VortexMark size={18} />
              </span>
              <h1 className={styles.authLogo}>AgentVortex</h1>
            </div>
            <p className={styles.authSubtext}>Connecting to operator service</p>
          </div>
        </div>
      </main>
    );
  }

  if (!authenticated) {
    return (
      <main className={styles.authScreen}>
        <div className={styles.authCard}>
          <div className={styles.authHeader}>
            <div className={styles.authLogoRow}>
              <span className={styles.brandMark}>
                <VortexMark size={18} />
              </span>
              <h1 className={styles.authLogo}>AgentVortex</h1>
            </div>
            <p className={styles.authSubtext}>Operator console</p>
          </div>

          <form className={styles.authForm} onSubmit={handleLogin}>
            <div className={styles.authField}>
              <label htmlFor="auth-password" className={styles.authLabel}>
                Password
              </label>
              <input
                id="auth-password"
                type="password"
                autoComplete="current-password"
                required
                placeholder="Enter password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={styles.authInput}
                autoFocus
              />
            </div>
            <button type="submit" className={styles.authButton}>
              Unlock
            </button>
          </form>

          {authError && (
            <div role="alert" className={styles.authError}>
              <AlertCircle size={16} strokeWidth={1.5} aria-hidden="true" />
              <span>{authError}</span>
            </div>
          )}
        </div>
      </main>
    );
  }

  // ==========================================================
  // Main App
  // ==========================================================

  const activeTitle = conversationId
    ? conversations.find((c) => c.id === conversationId)?.title || "New thread"
    : "Operator console";

  const riskLevel = (interrupt?.risk_level || "low").toLowerCase();
  const riskClassKey =
    riskLevel === "high"
      ? "high"
      : riskLevel === "medium"
        ? "medium"
        : "low";

  return (
    <div className={styles.appLayout}>
      <a
        href="#chat-input"
        className={`visually-hidden ${styles.skipLink}`}
      >
        Skip to message input
      </a>

      {/* Mobile overlay */}
      {mobileDrawerOpen && (
        <div
          className={styles.mobileOverlay}
          aria-hidden="true"
          onClick={() => setMobileDrawerOpen(false)}
        />
      )}

      {/* ===== SIDEBAR ===== */}
      <aside
        aria-label="Conversations"
        className={`${styles.sidebar} ${
          desktopSidebarOpen ? "" : styles.sidebarClosed
        } ${mobileDrawerOpen ? "" : styles.sidebarMobileClosed}`}
      >
        <div className={styles.sidebarHeader}>
          <div className={styles.brandLockup}>
            <span className={styles.brandMark}>
              <VortexMark size={18} />
            </span>
            <span className={styles.sidebarLogo}>AgentVortex</span>
          </div>
          <button
            type="button"
            className={styles.iconButton}
            onClick={() => {
              if (window.innerWidth <= 768) {
                setMobileDrawerOpen(false);
              } else {
                setDesktopSidebarOpen(false);
              }
            }}
            aria-label="Close sidebar"
          >
            <PanelLeftClose size={16} strokeWidth={1.5} aria-hidden="true" />
          </button>
        </div>

        <div className={styles.sidebarControls}>
          <button
            type="button"
            className={styles.newChatBtn}
            onClick={startNewConversation}
          >
            <Plus size={16} strokeWidth={1.5} aria-hidden="true" />
            <span>New thread</span>
          </button>
        </div>

        <div className={styles.sidebarSectionHeader}>
          <span className={styles.sidebarSectionLabel}>Threads</span>
          <span className={styles.sidebarCount}>{conversations.length}</span>
        </div>

        <nav aria-label="Conversation history" className={styles.conversationNav}>
          <div className={styles.conversationList}>
            {conversations.map((convo) => {
              const isActive = conversationId === convo.id;
              return (
                <button
                  type="button"
                  key={convo.id}
                  className={`${styles.conversationItem} ${
                    isActive ? styles.conversationActive : ""
                  }`}
                  onClick={() => selectConversation(convo.id)}
                  aria-current={isActive ? "page" : undefined}
                >
                  <span className={styles.conversationIconBox} aria-hidden="true">
                    {isActive ? (
                      <span className={styles.activeDot} />
                    ) : (
                      <MessageSquare size={16} strokeWidth={1.5} />
                    )}
                  </span>
                  <span className={styles.conversationTitle}>{convo.title}</span>
                </button>
              );
            })}

            {conversations.length === 0 && (
              <p className={styles.noConversations}>No threads recorded</p>
            )}
          </div>
        </nav>
      </aside>

      {/* ===== MAIN WORKSPACE ===== */}
      <main id="main-content" className={styles.main}>
        {/* Top bar (56px height synced with sidebarHeader) */}
        <header className={styles.header}>
          <div className={styles.headerLeft}>
            {!desktopSidebarOpen && (
              <button
                type="button"
                className={`${styles.iconButton} ${styles.desktopMenuBtn}`}
                onClick={() => setDesktopSidebarOpen(true)}
                aria-label="Open sidebar"
                aria-expanded={desktopSidebarOpen}
              >
                <PanelLeftOpen size={16} strokeWidth={1.5} aria-hidden="true" />
              </button>
            )}
            {!mobileDrawerOpen && (
              <button
                type="button"
                className={`${styles.iconButton} ${styles.mobileMenuBtn}`}
                onClick={() => setMobileDrawerOpen(true)}
                aria-label="Open sidebar"
                aria-expanded={mobileDrawerOpen}
              >
                <PanelLeftOpen size={16} strokeWidth={1.5} aria-hidden="true" />
              </button>
            )}
            <h1 className={styles.headerTitle}>{activeTitle}</h1>
          </div>

          <div className={styles.statusIndicator}>
            <span
              className={`${styles.statusDot} ${
                interrupt
                  ? styles.statusDotPending
                  : loading
                    ? styles.statusDotBusy
                    : ""
              }`}
              aria-hidden="true"
            />
            <span>
              {interrupt
                ? "Clearance pending"
                : loading
                  ? "Executing"
                  : "Ready"}
            </span>
          </div>
        </header>

        {/* Chat Stream */}
        <div className={styles.chatContainer}>
          <div className={styles.messagesList}>
            <div className={styles.messagesInner}>
              {!conversationId && messages.length === 0 && (
                <section
                  className={styles.workspaceOverview}
                  aria-label="Workspace overview"
                >
                  <div className={styles.overviewIntro}>
                    <div className={styles.overviewEyebrow}>
                      <span className={styles.brandMark}>
                        <VortexMark size={16} />
                      </span>
                      <span>Multi-tool LangGraph console</span>
                    </div>
                    <h2 className={styles.overviewTitle}>
                      Personal AI operator console
                    </h2>
                    <p className={styles.overviewSubtitle}>
                      Delegate tasks across web browsing, shell execution,
                      WhatsApp, Gmail, Calendar, and documents with explicit
                      approval before medium or high-risk actions run
                    </p>
                  </div>

                  <div className={styles.capabilitiesGrid}>
                    {CAPABILITIES.map(({ name, description, Icon }) => (
                      <div key={name} className={styles.capabilityCard}>
                        <div className={styles.capabilityHeader}>
                          <span className={styles.capabilityIcon}>
                            <Icon size={16} strokeWidth={1.5} aria-hidden="true" />
                          </span>
                          <span>{name}</span>
                        </div>
                        <p className={styles.capabilityDesc}>{description}</p>
                      </div>
                    ))}
                  </div>

                  <div className={styles.starterSection}>
                    <span className={styles.starterLabel}>
                      Starter instructions
                    </span>
                    <div className={styles.starterList}>
                      {STARTER_PROMPTS.map((promptText) => (
                        <button
                          type="button"
                          key={promptText}
                          className={styles.starterBtn}
                          onClick={() => handleSelectStarter(promptText)}
                        >
                          <span>{promptText}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </section>
              )}

              {conversationId && messages.length === 0 && !loading && (
                <div className={styles.emptyThreadState}>
                  <h2 className={styles.emptyThreadTitle}>Empty thread</h2>
                  <p className={styles.emptyThreadSubtitle}>
                    Enter an instruction below to plan and execute a task
                  </p>
                </div>
              )}

              {messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`${styles.messageWrapper} ${
                    msg.role === "user"
                      ? styles.wrapperUser
                      : styles.wrapperAssistant
                  }`}
                >
                  {msg.role === "user" ? (
                    <div className={styles.userBubble}>{msg.content}</div>
                  ) : (
                    <>
                      <div className={styles.assistantMeta}>
                        <span className={styles.brandMark}>
                          <VortexMark size={16} />
                        </span>
                        <span>AgentVortex</span>
                      </div>
                      <div className={styles.assistantBody}>
                        <div className={styles.markdownBody}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              ))}

              {/* Streaming response */}
              {streamingContent && (
                <div
                  className={`${styles.messageWrapper} ${styles.wrapperAssistant}`}
                >
                  <div className={styles.assistantMeta}>
                    <span className={styles.brandMark}>
                      <VortexMark size={16} />
                    </span>
                    <span>AgentVortex</span>
                  </div>
                  <div className={styles.assistantBody}>
                    <div className={styles.markdownBody}>
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {streamingContent}
                      </ReactMarkdown>
                    </div>
                    <span className={styles.streamingCaret} aria-hidden="true" />
                  </div>
                </div>
              )}

              {/* Planning / Running indicator */}
              {loading && !streamingContent && !interrupt && (
                <div
                  className={`${styles.messageWrapper} ${styles.wrapperAssistant}`}
                >
                  <div className={styles.assistantMeta}>
                    <span className={styles.brandMark}>
                      <VortexMark size={16} />
                    </span>
                    <span>AgentVortex</span>
                  </div>
                  <div className={styles.statusMessage} role="status">
                    <span>Planning execution</span>
                  </div>
                </div>
              )}

              {/* Moment: HITL Approval Gate */}
              {interrupt && (
                <section
                  className={styles.interruptCard}
                  aria-label="Execution clearance required"
                >
                  <div className={styles.interruptHeader}>
                    <div className={styles.interruptHeaderTitleGroup}>
                      <span
                        className={`${styles.interruptIcon} ${styles[`interruptIcon_${riskClassKey}`]}`}
                      >
                        <ShieldAlert
                          size={18}
                          strokeWidth={1.5}
                          aria-hidden="true"
                        />
                      </span>
                      <h3>Approval required</h3>
                    </div>
                    <span
                      className={`${styles.riskBadge} ${styles[`risk_${riskClassKey}`]}`}
                    >
                      {formatRiskLabel(interrupt.risk_level)}
                    </span>
                  </div>

                  <div className={styles.interruptBody}>
                    <div className={styles.interruptSection}>
                      <h4 className={styles.interruptSectionLabel}>
                        Execution plan
                      </h4>
                      <ol className={styles.planList}>
                        {interrupt.plan.map((step, i) => (
                          <li key={i} className={styles.planItem}>
                            <span className={styles.planStepIndex}>
                              {String(i + 1).padStart(2, "0")}
                            </span>
                            <span>{step}</span>
                          </li>
                        ))}
                      </ol>
                    </div>

                    <div className={styles.interruptSection}>
                      <h4 className={styles.interruptSectionLabel}>
                        Tools requested
                      </h4>
                      <div className={styles.toolsList}>
                        {interrupt.planned_tools.map((tool, i) => (
                          <span key={i} className={styles.toolBadge}>
                            {tool}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className={styles.interruptActions}>
                    <button
                      type="button"
                      className={styles.btnDeny}
                      onClick={() => handleApprove(false)}
                    >
                      <X size={16} strokeWidth={1.5} aria-hidden="true" />
                      <span>Deny</span>
                    </button>
                    <button
                      type="button"
                      className={styles.btnApprove}
                      onClick={() => handleApprove(true)}
                    >
                      <Check size={16} strokeWidth={1.5} aria-hidden="true" />
                      <span>Approve and run</span>
                    </button>
                  </div>
                </section>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Composer */}
          <div className={styles.inputArea}>
            <form
              ref={formRef}
              onSubmit={handleComposerSubmit}
              className={styles.composerForm}
            >
              <div className={styles.inputWrapper}>
                <label htmlFor="chat-input" className="visually-hidden">
                  Message AgentVortex
                </label>
                <textarea
                  ref={textareaRef}
                  id="chat-input"
                  rows={1}
                  placeholder="Message AgentVortex"
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  disabled={loading || interrupt !== null}
                  className={styles.composerTextarea}
                />
                <button
                  type="submit"
                  className={styles.sendButton}
                  aria-label="Send message"
                  disabled={!input.trim() || loading || interrupt !== null}
                >
                  <ArrowUp size={16} strokeWidth={1.5} aria-hidden="true" />
                </button>
              </div>
              <div className={styles.composerFooter}>
                <span>
                  Medium and high-risk tool calls pause for approval before
                  execution
                </span>
                <div className={styles.shortcutGroup} aria-hidden="true">
                  <span className={styles.shortcutHint}>
                    <kbd className={styles.keycap}>Shift</kbd>
                    <kbd className={styles.keycap}>Enter</kbd>
                    <span>New line</span>
                  </span>
                  <span className={styles.shortcutHint}>
                    <kbd className={styles.keycap}>Enter</kbd>
                    <span>Send</span>
                  </span>
                </div>
              </div>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}
