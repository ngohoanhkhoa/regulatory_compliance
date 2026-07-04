import { useEffect, useState } from "react";
import * as api from "../api/client";

export default function History() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getHistory(100)
      .then(setItems)
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="history-page">
      <h2>Query History</h2>
      {loading && <p>Loading…</p>}
      {!loading && items.length === 0 && <p>No queries yet.</p>}
      <div className="history-list">
        {items.map((h) => (
          <div key={h.id} className="history-item">
            <div className="hist-q">{h.question}</div>
            <div className="hist-a">{h.answer.slice(0, 200)}{h.answer.length > 200 ? "…" : ""}</div>
            <div className="hist-meta">
              {h.sources?.length || 0} sources | grounded: {h.grounded ? "yes" : "no"} | {h.model}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}