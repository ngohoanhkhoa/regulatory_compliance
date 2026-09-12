import { useState, useRef, useEffect, useCallback } from "react";
import * as api from "../api/client";
import { getSettings } from "../api/settings";
import { useChat } from "../api/ChatContext";
import {
  Send,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  ChevronRight,
  AlertTriangle,
  MessageSquare,
  Plus,
  Clock,
  ExternalLink,
  FileText,
  History,
  Maximize2,
  Database,
} from "lucide-react";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import Modal from "../components/ui/Modal";
import HistoryPage from "./History";

function formatText(text) {
  const blocks = text.split("\n\n");
  const out = [];

  const linkify = (s) =>
    s.replace(
      /(https?:\/\/[^\s<>"']+)/g,
      '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
    );

  const processLine = (line) => {
    let result = line;
    result = result.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    result = result.replace(/\*(.+?)\*/g, "<em>$1</em>");
    result = result.replace(/`([^`]+)`/g, '<code>$1</code>');
    result = result.replace(
      /\[(\d+)\]/g,
      '<sup class="footnote-ref">[$1]</sup>'
    );
    result = linkify(result);
    return result;
  };

  for (const block of blocks) {
    if (!block.trim()) continue;

    const lines = block.split("\n").map(l => l.trimEnd()).filter(l => l);

    const isList = lines.every(l => /^\s*[-*+]\s+/.test(l));
    if (isList) {
      const items = lines.map(l => l.replace(/^\s*[-*+]\s+/, ""));
      out.push(["ul", ...items.map(l => processLine(l))]);
      continue;
    }

    const hMatch = lines[0].match(/^#{1,3}\s+(.+)/);
    if (hMatch && lines.length === 1) {
      const level = Math.min(hMatch[0].match(/^#+/)[0].length, 3);
      const fontSize = {1: "1.2rem", 2: "1.1rem", 3: "1rem"};
      out.push(["p", `<strong style="font-size:${fontSize[level]};display:block;margin-top:.5rem">${linkify(hMatch[1])}</strong>`]);
      continue;
    }

    const html = lines.map(l => processLine(l)).join("<br>");
    out.push(["p", html]);
  }

  return out;
}

function LoadingStatus() {
  const [step, setStep] = useState(0);
  const steps = [
    { icon: MessageSquare, text: "Understanding your question…" },
    { icon: FileText, text: "Searching EU legislation…" },
    { icon: Send, text: "Generating response…" },
  ];

  useEffect(() => {
    const t1 = setTimeout(() => setStep(1), 1200);
    const t2 = setTimeout(() => setStep(2), 3500);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  const CurrentIcon = steps[step].icon;

  return (
    <div className="msg msg-assistant">
      <div className="msg-bubble assistant">
        <div className="status-line">
          <CurrentIcon className="w-4 h-4 text-[var(--accent)] animate-pulse" />
          <span className="text-[var(--text-dim)]">{steps[step].text}</span>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ msg }) {
  const [copied, setCopied] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(true);

  const copyAnswer = useCallback(() => {
    navigator.clipboard.writeText(msg.text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [msg.text]);

  const giveFeedback = async (rating) => {
    if (!msg.queryLogId) return;
    try {
      await api.submitFeedback(msg.queryLogId, rating, "");
    } catch { /* silent */ }
  };

  if (msg.role === "user") {
    return (
      <div className="msg msg-user">
        <div className="msg-bubble user">{msg.text}</div>
      </div>
    );
  }

  if (msg.role === "error") {
    return (
      <div className="msg msg-error">
        <div className="msg-bubble error">
          <AlertTriangle className="w-4 h-4 inline mr-2" />
          {msg.text}
        </div>
      </div>
    );
  }

  const formatted = formatText(msg.text);

  return (
    <div className="msg msg-assistant">
      <div className="msg-bubble assistant">
        {msg.intent && (
          <Badge variant={
            msg.intent === "explore" ? "warning" :
            msg.intent === "greeting" ? "success" : "info"
          }>
            {msg.intent === "explore" ? "Dataset Explorer" :
             msg.intent === "greeting" ? "Assistant" : "Q&A"}
          </Badge>
        )}

        <div className="answer-text">
          {formatted.map((el, i) => {
            const [tag, ...rest] = el;
            if (tag === "ul") return <ul key={i}>{rest.map((item, j) => <li key={j} dangerouslySetInnerHTML={{ __html: item }} />)}</ul>;
            if (tag === "p") return <p key={i} dangerouslySetInnerHTML={{ __html: rest[0] }} />;
            return null;
          })}
        </div>

        <div className="answer-actions">
          <button
            className={`flex items-center gap-1.5 ${copied ? "text-[var(--good)]" : ""}`}
            onClick={copyAnswer}
          >
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
          <button onClick={() => giveFeedback(1)} title="Helpful">
            <ThumbsUp className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => giveFeedback(-1)} title="Not helpful">
            <ThumbsDown className="w-3.5 h-3.5" />
          </button>
        </div>

        {msg.warnings?.length > 0 && (
          <div className="warnings">
            {msg.warnings.map((w, j) => (
              <div key={j} className="warning">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                {w}
              </div>
            ))}
          </div>
        )}

        {msg.sources?.length > 0 && (
          <div className="sources">
            <div className="sources-header" onClick={() => setSourcesOpen(o => !o)}>
              <ChevronRight className={`w-3.5 h-3.5 transition-transform ${sourcesOpen ? "rotate-90" : ""}`} />
              <FileText className="w-3.5 h-3.5" />
              {msg.sources.length} source{msg.sources.length > 1 ? "s" : ""}
            </div>
            {sourcesOpen && msg.sources.map((s, j) => (
              <div key={j} className="source-item" id={`source-${j + 1}`}>
                <div className="source-main">
                  <span className="source-num">[{j + 1}]</span>
                  <a href={s.link} target="_blank" rel="noreferrer" className="flex items-center gap-1">
                    {s.act_name || s.celex}
                    <ExternalLink className="w-3 h-3" />
                  </a>
                  {s.status && (
                    <Badge variant={s.status === "In Force" ? "success" : "warning"}>
                      {s.status}
                    </Badge>
                  )}
                  <span className="text-xs text-[var(--text-muted)]">{s.celex}</span>
                </div>
                {s.chunk_excerpt && (
                  <div className="source-excerpt">{s.chunk_excerpt}…</div>
                )}
              </div>
            ))}
          </div>
        )}

        {!msg.grounded && msg.ungrounded?.length > 0 && (
          <div className="grounding-warn">
            <AlertTriangle className="w-3.5 h-3.5 inline mr-1" />
            Answer references CELEX not in retrieved context: {msg.ungrounded.join(", ")}
          </div>
        )}

        {msg.disclaimer && <div className="disclaimer">{msg.disclaimer}</div>}
      </div>
    </div>
  );
}

export default function Chat() {
  const { messages, setMessages, activeConversationId, setActiveConversationId } = useChat();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [historyItems, setHistoryItems] = useState([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetIds, setSelectedDatasetIds] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("chatDatasetIds") || "[]");
    } catch {
      return [];
    }
  });
  const endRef = useRef(null);
  const inputRef = useRef(null);

  const refreshHistory = useCallback(() => {
    api.getHistory(50).then(setHistoryItems).catch(() => {});
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    api.getHistory(50).then(setHistoryItems).catch(() => setHistoryItems([]));
  }, []);

  useEffect(() => {
    api
      .getDatasets()
      .then((ds) => {
        setDatasets(ds);
        setSelectedDatasetIds((cur) => {
          const valid = cur.filter((id) => ds.some((d) => d.id === id));
          if (valid.length) return valid;
          return ds.filter((d) => d.kind === "regulatory").map((d) => d.id);
        });
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    localStorage.setItem("chatDatasetIds", JSON.stringify(selectedDatasetIds));
  }, [selectedDatasetIds]);

  const toggleDataset = (id) =>
    setSelectedDatasetIds((cur) =>
      cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]
    );

  const ask = async (e) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    const optimistic = { role: "user", text: question };
    setMessages((m) => [...m, optimistic]);
    try {
      const { includeRepealed } = getSettings();
      // Default (all regulatory datasets) keeps the legacy explore behavior;
      // an explicit narrowing sends the selection so retrieval is scoped.
      const regSorted = datasets
        .filter((d) => d.kind === "regulatory")
        .map((d) => d.id)
        .sort((a, b) => a - b);
      const sel = [...selectedDatasetIds].sort((a, b) => a - b);
      const isDefault =
        sel.length > 0 &&
        sel.length === regSorted.length &&
        sel.every((v, i) => v === regSorted[i]);
      const res = await api.chat(question, {
        include_repealed: includeRepealed,
        dataset_ids: isDefault ? null : selectedDatasetIds,
      });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: res.answer,
          sources: res.sources,
          warnings: res.warnings,
          disclaimer: res.disclaimer,
          grounded: res.grounded,
          ungrounded: res.ungrounded_celex,
          queryLogId: res.query_log_id,
          intent: res.intent,
        },
      ]);
      // Refresh sidebar history so the new exchange appears.
      refreshHistory();
    } catch (err) {
      setMessages((m) => [...m, { role: "error", text: err.message || "Query failed" }]);
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask(e);
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setActiveConversationId(null);
    inputRef.current?.focus();
  };

  const loadConversation = (item) => {
    const loaded = [
      { role: "user", text: item.question },
      {
        role: "assistant",
        text: item.answer,
        sources: item.sources,
        warnings: item.warnings,
        disclaimer: item.disclaimer,
        grounded: item.grounded,
        ungrounded: item.ungrounded_celex,
        queryLogId: item.id,
        intent: item.intent,
      },
    ];
    setMessages(loaded);
    setActiveConversationId(item.id);
  };

  const formatTime = (ts) => {
    if (!ts) return "";
    const ms = typeof ts === "number" ? ts * 1000 : Date.parse(ts + (ts.includes("Z") ? "" : "Z"));
    const d = new Date(ms);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="chat-page">
      {/* Sidebar */}
      <aside className="chat-sidebar">
        <div className="sidebar-header">
          <h3>Conversations</h3>
          <button className="sidebar-new-btn" onClick={startNewChat}>
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>
        <div className="chat-sidebar-list">
          {/* Current chat */}
          {messages.length > 0 && activeConversationId === null && (
            <div className="chat-sidebar-item active">
              <MessageSquare className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">{messages[0]?.text?.slice(0, 40) || "Current chat"}...</span>
            </div>
          )}

          {/* History */}
          <div className="chat-sidebar-section">
            <div className="chat-sidebar-section-title">
              <History className="w-3 h-3" />
              Recent History
              <button
                className="chat-sidebar-history-btn"
                onClick={() => setHistoryOpen(true)}
                title="Open full history"
              >
                <Maximize2 className="w-3 h-3" />
                Open
              </button>
            </div>
            {historyItems.length === 0 ? (
              <p className="chat-sidebar-empty">No recent chats yet</p>
            ) : (
              historyItems.map((item) => (
                <div
                  key={item.id}
                  className={`chat-sidebar-item ${activeConversationId === item.id ? "active" : ""}`}
                  onClick={() => loadConversation(item)}
                  title={item.question}
                >
                  <MessageSquare className="w-3.5 h-3.5 shrink-0" />
                  <div className="chat-sidebar-item-content">
                    <span className="truncate">{item.question?.slice(0, 40) || "Untitled"}...</span>
                    <span className="chat-sidebar-item-time">{formatTime(item.created_at)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </aside>

      {/* History Modal */}
      <Modal
        isOpen={historyOpen}
        onClose={() => {
          setHistoryOpen(false);
          refreshHistory();
        }}
        title="Chat History"
        size="lg"
      >
        <HistoryPage
          onDeleted={(id) => {
            setActiveConversationId((cur) => (cur === id ? null : cur));
            refreshHistory();
          }}
        />
      </Modal>

      {/* Main chat area */}
      <div className="chat-main">
        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="empty-hint">
              <MessageSquare className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-4" />
              <strong>Ask about EU regulations</strong>
              <p>Ask legal questions like "Is the GDPR still in force?" or explore the dataset with "How many acts are there?"</p>
            </div>
          )}
          {messages.map((m, i) => (
            <MessageBubble key={i} msg={m} />
          ))}
          {busy && <LoadingStatus />}
          <div ref={endRef} />
        </div>

        <div className="chat-input-wrapper">
          {datasets.length > 0 && (
            <div className="dataset-selector">
              <span className="dataset-selector-label">Datasets</span>
              <div className="dataset-chips">
                {datasets.map((d) => (
                  <button
                    key={d.id}
                    type="button"
                    className={`dataset-chip ${
                      selectedDatasetIds.includes(d.id) ? "active" : ""
                    }`}
                    onClick={() => toggleDataset(d.id)}
                    title={`${d.kind} · ${d.items} item(s)`}
                  >
                    {d.kind === "regulatory" ? (
                      <Database className="w-3 h-3" />
                    ) : (
                      <FileText className="w-3 h-3" />
                    )}
                    {d.name}
                  </button>
                ))}
              </div>
            </div>
          )}
          <form className="chat-input" onSubmit={ask}>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about EU regulations…"
              disabled={busy}
            />
            <button type="submit" disabled={busy || !input.trim()}>
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
