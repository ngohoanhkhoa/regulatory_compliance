import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import * as api from "../api/client";
import { useAuth } from "../api/AuthContext";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import Modal from "../components/ui/Modal";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import Documents from "./Documents";
import {
  Database,
  FileText,
  Layers,
  Search,
  Trash2,
  Download,
  ArrowLeft,
  CheckCircle,
  AlertTriangle,
  ChevronUp,
  ChevronDown,
  Copy,
  Check,
} from "lucide-react";

const PAGE_SIZES = [10, 25, 50, 100];

function statusVariant(status) {
  if (!status) return "default";
  return status.toLowerCase() === "in force" ? "success" : "warning";
}

function columnWidth(key) {
  switch (key) {
    case "id":
      return "150px";
    case "title":
      return "minmax(220px, 1fr)";
    case "status":
      return "120px";
    case "date":
      return "110px";
    case "type":
      return "110px";
    case "chunks":
      return "80px";
    default:
      return "120px";
  }
}

function renderCell(item, key) {
  const value = item[key];
  if (key === "status") {
    return <Badge variant={statusVariant(value)}>{value || "—"}</Badge>;
  }
  if (key === "id") {
    return (
      <span className="data-celex" title={String(value || "")}>
        {value || "—"}
      </span>
    );
  }
  if (key === "title") {
    return (
      <span className="data-act-name" title={value || ""}>
        {value || "—"}
      </span>
    );
  }
  if (key === "date") {
    return <span className="data-date">{value || "—"}</span>;
  }
  if (key === "chunks") {
    return <span className="data-chunks">{value ?? 0}</span>;
  }
  return <span>{value || "—"}</span>;
}

function RegulatoryPanel({ dataset, isAdmin, onDeleted }) {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [columns, setColumns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [sort, setSort] = useState("date");
  const [order, setOrder] = useState("desc");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [includeEmbeddings, setIncludeEmbeddings] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [itemOpen, setItemOpen] = useState(false);
  const [item, setItem] = useState(null);
  const [itemLoading, setItemLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const loadActs = useCallback(() => {
    return api
      .getDatasetActs(dataset.id, {
        query: appliedQuery,
        limit: pageSize,
        offset: page * pageSize,
        sort,
        order,
      })
      .then((data) => {
        setItems(data.items || []);
        setTotal(data.total || 0);
        setColumns(data.columns || []);
      })
      .catch((err) => setError(err.message || "Failed to load items"));
  }, [dataset.id, appliedQuery, pageSize, page, sort, order]);

  useEffect(() => {
    setLoading(true);
    loadActs().finally(() => setLoading(false));
  }, [loadActs]);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const runSearch = (e) => {
    e.preventDefault();
    setPage(0);
    setAppliedQuery(query);
  };

  const onSort = (key) => {
    if (sort === key) {
      setOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSort(key);
      setOrder(key === "date" || key === "chunks" ? "desc" : "asc");
    }
    setPage(0);
  };

  const openItem = async (id) => {
    setItemOpen(true);
    setItem(null);
    setItemLoading(true);
    setCopied(false);
    try {
      setItem(await api.getDatasetItem(dataset.id, id));
    } catch (err) {
      setError(err.message || "Failed to load item");
    } finally {
      setItemLoading(false);
    }
  };

  const copyItem = () => {
    if (!item) return;
    const text = item.chunks
      .map((c) => (c.boundary ? `${c.boundary}\n${c.text}` : c.text))
      .join("\n\n");
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const doExport = async () => {
    setExporting(true);
    setError("");
    try {
      const { blob, filename } = await api.downloadDataset(
        dataset.id,
        includeEmbeddings
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast(`Exported ${filename}`);
    } catch (err) {
      setError(err.message || "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const doDelete = async () => {
    setDeleting(true);
    try {
      await api.deleteDataset(dataset.id);
      onDeleted();
    } catch (err) {
      setError(err.message || "Failed to remove dataset");
      setDeleting(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : page * pageSize + 1;
  const end = Math.min(total, (page + 1) * pageSize);
  const gridTemplate = columns.map((c) => columnWidth(c.key)).join(" ") || "1fr";

  return (
    <>
      {toast && (
        <div className="toast">
          <CheckCircle className="w-4 h-4 inline mr-2" />
          {toast}
        </div>
      )}
      {error && (
        <Card className="mb-6 border-[var(--bad)]/30 bg-[var(--bad-muted)]">
          <div className="flex items-center gap-2 text-[var(--bad)] text-sm">
            <AlertTriangle className="w-4 h-4" />
            {error}
          </div>
        </Card>
      )}

      <div className="dataset-toolbar">
        <label className="dataset-embed-toggle">
          <input
            type="checkbox"
            checked={includeEmbeddings}
            onChange={(e) => setIncludeEmbeddings(e.target.checked)}
          />
          Include embeddings (larger file)
        </label>
        <div className="topic-form-actions">
          <Button
            variant="secondary"
            icon={Download}
            isLoading={exporting}
            onClick={doExport}
          >
            Export bundle
          </Button>
          {isAdmin && (
            <Button
              variant="danger"
              icon={Trash2}
              onClick={() => setConfirmOpen(true)}
            >
              Remove dataset
            </Button>
          )}
        </div>
      </div>

      <div className="stats-grid">
        <Card className="space-y-2">
          <div className="stat-icon blue">
            <Layers className="w-4 h-4" />
          </div>
          <div className="stat-value">{dataset.items}</div>
          <div className="stat-label">Items</div>
        </Card>
        <Card className="space-y-2">
          <div className="stat-icon green">
            <FileText className="w-4 h-4" />
          </div>
          <div className="stat-value">{dataset.chunks}</div>
          <div className="stat-label">Text chunks</div>
        </Card>
        <Card className="space-y-2">
          <div className="stat-icon yellow">
            <Database className="w-4 h-4" />
          </div>
          <div className="stat-value">{dataset.vectors ?? "—"}</div>
          <div className="stat-label">Indexed vectors</div>
        </Card>
        <Card className="space-y-2">
          <div className="stat-icon red">
            <Download className="w-4 h-4" />
          </div>
          <div className="stat-value">{dataset.source}</div>
          <div className="stat-label">Source</div>
        </Card>
      </div>

      <form className="data-toolbar" onSubmit={runSearch}>
        <div className="history-search">
          <Search className="w-4 h-4" />
          <input
            type="text"
            placeholder="Search by ID, title, or status…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>

      {loading ? (
        <LoadingSpinner size="sm" text="Loading items…" />
      ) : items.length === 0 ? (
        <div className="data-empty">
          <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No items found.</p>
        </div>
      ) : (
        <>
          <div className="data-table">
            <div className="data-table-head" style={{ gridTemplateColumns: gridTemplate }}>
              {columns.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  className={`th-sort ${sort === c.key ? "active" : ""} ${
                    c.key === "chunks" ? "text-right" : ""
                  }`}
                  onClick={() => onSort(c.key)}
                >
                  {c.label}
                  {sort === c.key &&
                    (order === "asc" ? (
                      <ChevronUp className="w-3 h-3" />
                    ) : (
                      <ChevronDown className="w-3 h-3" />
                    ))}
                </button>
              ))}
            </div>
            {items.map((it, idx) => (
              <div
                key={it.id ?? idx}
                className="data-table-row clickable"
                style={{ gridTemplateColumns: gridTemplate }}
                role="button"
                tabIndex={0}
                onClick={() => openItem(it.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    openItem(it.id);
                  }
                }}
              >
                {columns.map((c) => (
                  <span
                    key={c.key}
                    className={c.key === "chunks" ? "text-right" : ""}
                  >
                    {renderCell(it, c.key)}
                  </span>
                ))}
              </div>
            ))}
          </div>

          <div className="pager">
            <span className="pager-info">
              Showing {start}–{end} of {total}
            </span>
            <div className="pager-controls">
              <button
                className="pager-btn"
                disabled={page === 0}
                onClick={() => setPage(0)}
              >
                « First
              </button>
              <button
                className="pager-btn"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                ‹ Prev
              </button>
              <span className="pager-page">
                Page {page + 1} / {totalPages}
              </span>
              <button
                className="pager-btn"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                Next ›
              </button>
              <button
                className="pager-btn"
                disabled={page >= totalPages - 1}
                onClick={() => setPage(totalPages - 1)}
              >
                Last »
              </button>
            </div>
            <select
              className="pager-size"
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(0);
              }}
            >
              {PAGE_SIZES.map((n) => (
                <option key={n} value={n}>
                  {n} / page
                </option>
              ))}
            </select>
          </div>
        </>
      )}

      <Modal
        isOpen={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Remove regulatory dataset"
      >
        <p className="modal-confirm-text">
          Remove <strong>{dataset.name}</strong>? This deletes its chunks and
          vectors from this instance. You can re-add it later by importing the
          dataset bundle.
        </p>
        <div className="topic-form-actions">
          <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            icon={Trash2}
            isLoading={deleting}
            onClick={doDelete}
          >
            Remove dataset
          </Button>
        </div>
      </Modal>

      <Modal
        isOpen={itemOpen}
        onClose={() => setItemOpen(false)}
        title={item?.title || item?.id || "Item"}
        size="lg"
      >
        {itemLoading ? (
          <LoadingSpinner size="sm" text="Loading item…" />
        ) : item ? (
          <div className="item-view">
            <div className="item-view-head">
              <div className="item-view-tags">
                {item.id && <span className="data-celex">{item.id}</span>}
                {item.status && (
                  <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
                )}
                {item.date && <span className="data-date">{item.date}</span>}
                {item.type && <Badge variant="info">{item.type}</Badge>}
              </div>
              <button className="pager-btn" onClick={copyItem}>
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5" /> Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" /> Copy
                  </>
                )}
              </button>
            </div>

            {Object.keys(item.fields || {}).length > 0 && (
              <dl className="item-fields">
                {Object.entries(item.fields).map(([k, v]) => (
                  <div className="item-field" key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            )}

            <div className="item-chunks">
              {item.chunks.map((c, i) => (
                <section className="chunk-section" key={i}>
                  {c.boundary && <div className="chunk-boundary">{c.boundary}</div>}
                  <div className="chunk-text">{c.text}</div>
                </section>
              ))}
            </div>
          </div>
        ) : null}
      </Modal>
    </>
  );
}

export default function DatasetDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [dataset, setDataset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .getDataset(id)
      .then(setDataset)
      .catch((err) => setError(err.message || "Dataset not found"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="data-page">
        <LoadingSpinner text="Loading dataset…" />
      </div>
    );
  }

  if (error || !dataset) {
    return (
      <div className="data-page">
        <Button variant="ghost" icon={ArrowLeft} onClick={() => navigate("/datasets")}>
          Back to datasets
        </Button>
        <Card className="mt-4 border-[var(--bad)]/30 bg-[var(--bad-muted)]">
          <div className="text-[var(--bad)] text-sm">{error || "Not found"}</div>
        </Card>
      </div>
    );
  }

  const isAdmin = !!user?.is_admin;
  const isDocuments = dataset.kind === "documents";

  return (
    <div className="data-page">
      <div className="data-header">
        <div>
          <Button
            variant="ghost"
            icon={ArrowLeft}
            onClick={() => navigate("/datasets")}
          >
            All datasets
          </Button>
          <h2 className="mt-2">{dataset.name}</h2>
          <p className="data-subtitle">
            {dataset.description ||
              (isDocuments
                ? "Your private uploaded documents."
                : "Shared regulatory text collection.")}
          </p>
        </div>
      </div>

      {isDocuments ? (
        <Documents />
      ) : (
        <RegulatoryPanel
          dataset={dataset}
          isAdmin={isAdmin}
          onDeleted={() => navigate("/datasets")}
        />
      )}
    </div>
  );
}
