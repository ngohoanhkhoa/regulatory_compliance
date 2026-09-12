import { useEffect, useState, useMemo } from "react";
import * as api from "../api/client";
import {
  Search,
  Clock,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  FileText,
  BookOpen,
  AlertCircle,
  RotateCcw,
  Trash2,
} from "lucide-react";
import Badge from "../components/ui/Badge";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import Card from "../components/ui/Card";

export default function HistoryPage({ onDeleted }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [searchQuery, setSearchQuery] = useState("");
  const [filter, setFilter] = useState("all"); // all, grounded, ungrounded
  const [deletingId, setDeletingId] = useState(null);

  const loadHistory = () => {
    setLoading(true);
    setError(null);
    api
      .getHistory(200)
      .then((data) => {
        setItems(data);
        setError(null);
      })
      .catch((err) => {
        setItems([]);
        setError(err.message || "Failed to load history");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const toggleExpand = (id) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm("Delete this conversation? This cannot be undone.")) return;
    setDeletingId(id);
    try {
      await api.deleteHistory(id);
      setItems((prev) => prev.filter((h) => h.id !== id));
      onDeleted?.(id);
    } catch (err) {
      setError(err.message || "Failed to delete conversation");
    } finally {
      setDeletingId(null);
    }
  };

  const formatTime = (ts) => {
    if (!ts) return "";
    // Backend returns created_at as a Unix timestamp (seconds).
    const ms = typeof ts === "number" ? ts * 1000 : Date.parse(ts + (ts.includes("Z") ? "" : "Z"));
    const d = new Date(ms);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const filteredItems = useMemo(() => {
    let result = items;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (h) =>
          h.question?.toLowerCase().includes(q) ||
          h.answer?.toLowerCase().includes(q)
      );
    }

    if (filter === "grounded") {
      result = result.filter((h) => h.grounded);
    } else if (filter === "ungrounded") {
      result = result.filter((h) => !h.grounded);
    }

    return result;
  }, [items, searchQuery, filter]);

  const stats = useMemo(() => {
    const total = items.length;
    const grounded = items.filter((h) => h.grounded).length;
    return { total, grounded, ungrounded: total - grounded };
  }, [items]);

  if (loading) {
    return (
      <div className="history-page">
        <LoadingSpinner text="Loading history…" />
      </div>
    );
  }

  return (
    <div className="history-page">
      <h2>Query History</h2>

      {/* Stats cards */}
      <div className="stats-grid mb-6">
        <Card padding="sm">
          <div className="flex items-center gap-3">
            <div className="stat-icon blue">
              <BookOpen className="w-4 h-4" />
            </div>
            <div>
              <div className="stat-value">{stats.total}</div>
              <div className="stat-label">Total Queries</div>
            </div>
          </div>
        </Card>
        <Card padding="sm">
          <div className="flex items-center gap-3">
            <div className="stat-icon green">
              <CheckCircle className="w-4 h-4" />
            </div>
            <div>
              <div className="stat-value">{stats.grounded}</div>
              <div className="stat-label">Grounded</div>
            </div>
          </div>
        </Card>
        <Card padding="sm">
          <div className="flex items-center gap-3">
            <div className="stat-icon red">
              <XCircle className="w-4 h-4" />
            </div>
            <div>
              <div className="stat-value">{stats.ungrounded}</div>
              <div className="stat-label">Ungrounded</div>
            </div>
          </div>
        </Card>
      </div>

      {/* Error state */}
      {error && (
        <Card className="mb-6 border-[var(--bad)]/30 bg-[var(--bad-muted)]">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-[var(--bad)] flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-[var(--bad)] font-medium">Unable to load history</p>
              <p className="text-[var(--text-dim)] text-sm mt-1">{error}</p>
            </div>
            <button
              onClick={loadHistory}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg bg-[var(--surface)] text-[var(--text)] hover:bg-[var(--surface2)] transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
              Retry
            </button>
          </div>
        </Card>
      )}

      {/* Toolbar */}
      <div className="history-toolbar">
        <div className="history-search">
          <Search className="w-4 h-4" />
          <input
            type="text"
            placeholder="Search queries…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="history-filters">
          <button
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              filter === "all"
                ? "bg-[var(--accent)] text-white"
                : "bg-[var(--surface2)] text-[var(--text-dim)] hover:text-[var(--text)]"
            }`}
            onClick={() => setFilter("all")}
          >
            All
          </button>
          <button
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              filter === "grounded"
                ? "bg-[var(--good)] text-white"
                : "bg-[var(--surface2)] text-[var(--text-dim)] hover:text-[var(--text)]"
            }`}
            onClick={() => setFilter("grounded")}
          >
            <CheckCircle className="w-3.5 h-3.5 inline mr-1" />
            Grounded
          </button>
          <button
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              filter === "ungrounded"
                ? "bg-[var(--bad)] text-white"
                : "bg-[var(--surface2)] text-[var(--text-dim)] hover:text-[var(--text)]"
            }`}
            onClick={() => setFilter("ungrounded")}
          >
            <XCircle className="w-3.5 h-3.5 inline mr-1" />
            Ungrounded
          </button>
        </div>
      </div>

      {/* Results count */}
      <p className="text-sm text-[var(--text-muted)] mb-4">
        Showing {filteredItems.length} of {items.length} queries
      </p>

      {filteredItems.length === 0 ? (
        <div className="text-center py-12 text-[var(--text-muted)]">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No queries found matching your criteria.</p>
        </div>
      ) : (
        <div className="history-list">
          {filteredItems.map((h) => {
            const longAnswer = (h.answer?.length || 0) > 300;
            const isExpanded = expanded[h.id] || false;
            return (
              <div
                key={h.id}
                className="history-item"
                onClick={() => longAnswer && toggleExpand(h.id)}
              >
                <div className="hist-header">
                  <div className="hist-q">{h.question}</div>
                  {h.created_at != null && (
                    <div className="hist-time flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatTime(h.created_at)}
                    </div>
                  )}
                </div>
                <div className={`hist-a ${isExpanded ? "expanded" : ""}`}>
                  {h.answer || <em className="text-[var(--text-muted)]">No answer</em>}
                </div>
                {longAnswer && (
                  <button
                    className="hist-expand-btn flex items-center gap-1"
                    onClick={(e) => { e.stopPropagation(); toggleExpand(h.id); }}
                  >
                    {isExpanded ? (
                      <>Show less <ChevronUp className="w-3 h-3" /></>
                    ) : (
                      <>Show more <ChevronDown className="w-3 h-3" /></>
                    )}
                  </button>
                )}
                <div className="hist-footer">
                  <span className="flex items-center gap-1">
                    <FileText className="w-3 h-3" />
                    {h.sources?.length || 0} source{(h.sources?.length || 0) !== 1 ? "s" : ""}
                  </span>
                  <Badge variant={h.grounded ? "success" : "danger"}>
                    {h.grounded ? (
                      <><CheckCircle className="w-3 h-3" /> grounded</>
                    ) : (
                      <><XCircle className="w-3 h-3" /> ungrounded</>
                    )}
                  </Badge>
                  {h.model && <span className="text-[var(--text-muted)]">{h.model}</span>}
                  <button
                    className="hist-delete-btn"
                    onClick={(e) => handleDelete(h.id, e)}
                    disabled={deletingId === h.id}
                    title="Delete conversation"
                    aria-label="Delete conversation"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
