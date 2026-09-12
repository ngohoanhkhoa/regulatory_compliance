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
} from "lucide-react";

function statusVariant(status) {
  if (!status) return "default";
  return status.toLowerCase() === "in force" ? "success" : "warning";
}

function RegulatoryPanel({ dataset, isAdmin, onDeleted }) {
  const [acts, setActs] = useState([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [includeEmbeddings, setIncludeEmbeddings] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const loadActs = useCallback(
    (q = "") => {
      return api
        .getDatasetActs(dataset.id, { query: q, limit: 100 })
        .then((data) => {
          setActs(data.items);
          setTotal(data.total);
        })
        .catch((err) => setError(err.message || "Failed to load acts"));
    },
    [dataset.id]
  );

  useEffect(() => {
    setLoading(true);
    loadActs("").finally(() => setLoading(false));
  }, [loadActs]);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const runSearch = (e) => {
    e.preventDefault();
    loadActs(query);
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
          <div className="stat-label">Regulatory acts</div>
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
            placeholder="Search by CELEX, name, or status…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>

      <p className="data-count">
        Showing {acts.length} of {total} acts
      </p>

      {loading ? (
        <LoadingSpinner size="sm" text="Loading acts…" />
      ) : acts.length === 0 ? (
        <div className="data-empty">
          <Database className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No acts found.</p>
        </div>
      ) : (
        <div className="data-table">
          <div className="data-table-head">
            <span>CELEX</span>
            <span>Act name</span>
            <span>Status</span>
            <span>Date</span>
            <span className="text-right">Chunks</span>
          </div>
          {acts.map((a) => (
            <div className="data-table-row" key={a.celex}>
              <span className="data-celex">{a.celex}</span>
              <span className="data-act-name" title={a.act_name || ""}>
                {a.act_name || "—"}
              </span>
              <span>
                <Badge variant={statusVariant(a.status)}>{a.status || "—"}</Badge>
              </span>
              <span className="data-date">{a.date_document || "—"}</span>
              <span className="data-chunks text-right">{a.chunk_count}</span>
            </div>
          ))}
        </div>
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
