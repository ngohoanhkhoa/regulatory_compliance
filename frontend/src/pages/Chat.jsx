import { useState, useRef, useEffect } from "react";
import * as api from "../api/client";

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [includeRepealed, setIncludeRepealed] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ask = async (e) => {
    e.preventDefault();
    const question = input.trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    const optimistic = { role: "user", text: question };
    setMessages((m) => [...m, optimistic]);
    try {
      const res = await api.query(question, { include_repealed: includeRepealed });
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
        },
      ]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: "error", text: err.message || "Query failed" },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const giveFeedback = async (msg, rating) => {
    if (!msg.queryLogId) return;
    try {
      await api.submitFeedback(msg.queryLogId, rating, "");
    } catch {
      // silent
    }
  };

  return (
    <div className="chat-page">
      <div className="chat-controls">
        <label>
          <input
            type="checkbox"
            checked={includeRepealed}
            onChange={(e) => setIncludeRepealed(e.target.checked)}
          />
          Include repealed / superseded acts
        </label>
      </div>
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-hint">
            Ask a question about EU regulations, e.g.{" "}
            <em>"Is the GDPR still in force?"</em>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg msg-${m.role}`}>
            {m.role === "user" && <div className="msg-bubble user">{m.text}</div>}
            {m.role === "assistant" && (
              <div className="msg-bubble assistant">
                <div className="answer-text">{m.text}</div>
                {m.warnings?.length > 0 && (
                  <div className="warnings">
                    {m.warnings.map((w, j) => (
                      <div key={j} className="warning">
                        ⚠ {w}
                      </div>
                    ))}
                  </div>
                )}
                {m.sources?.length > 0 && (
                  <div className="sources">
                    <h4>Sources</h4>
                    {m.sources.map((s, j) => (
                      <div key={j} className="source-item">
                        <a href={s.link} target="_blank" rel="noreferrer">
                          {s.act_name || s.celex}
                        </a>
                        <span className={`badge ${s.status === "In Force" ? "ok" : "bad"}`}>
                          {s.status}
                        </span>
                        <span className="celex">{s.celex}</span>
                      </div>
                    ))}
                  </div>
                )}
                {!m.grounded && (
                  <div className="grounding-warn">
                    ⚠ Answer references CELEX not in retrieved context:{" "}
                    {m.ungrounded?.join(", ")}
                  </div>
                )}
                {m.disclaimer && (
                  <div className="disclaimer">{m.disclaimer}</div>
                )}
                {m.queryLogId && (
                  <div className="feedback">
                    <button onClick={() => giveFeedback(m, 1)}>👍</button>
                    <button onClick={() => giveFeedback(m, -1)}>👎</button>
                  </div>
                )}
              </div>
            )}
            {m.role === "error" && (
              <div className="msg-bubble error">Error: {m.text}</div>
            )}
          </div>
        ))}
        {busy && <div className="msg msg-assistant"><div className="msg-bubble loading">Thinking…</div></div>}
        <div ref={endRef} />
      </div>
      <form className="chat-input" onSubmit={ask}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about EU regulations…"
          disabled={busy}
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}