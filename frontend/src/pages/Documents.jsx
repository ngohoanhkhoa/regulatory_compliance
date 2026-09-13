import { useState, useEffect, useCallback, useRef } from "react";
import * as api from "../api/client";
import { useI18n } from "../i18n";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import {
  Upload,
  FileText,
  Trash2,
  Search,
  CheckCircle,
  AlertTriangle,
  Loader2,
} from "lucide-react";

const ACCEPT = ".pdf,.docx,.txt,.md,.markdown,.csv";

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(value >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatDate(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Documents() {
  const { t } = useI18n();
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [tags, setTags] = useState("");
  const inputRef = useRef(null);

  const loadDocs = useCallback(() => {
    return api
      .getDocuments()
      .then(setDocs)
      .catch((err) => setError(err.message || "Failed to load documents"));
  }, []);

  useEffect(() => {
    loadDocs().finally(() => setLoading(false));
  }, [loadDocs]);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const onFiles = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    if (!files.length) return;
    setUploading(true);
    setError("");
    const failures = [];
    for (const file of files) {
      try {
        await api.uploadDocument(file, tags.trim());
      } catch (err) {
        failures.push(`${file.name}: ${err.message}`);
      }
    }
    await loadDocs();
    setUploading(false);
    if (failures.length) setError(failures.join("  ·  "));
    else showToast(`Uploaded ${files.length} file${files.length > 1 ? "s" : ""}`);
  };

  const doDelete = async (id) => {
    if (!window.confirm(t("Delete this document and its indexed chunks?"))) return;
    setDeletingId(id);
    try {
      await api.deleteDocument(id);
      setResults(null);
      await loadDocs();
    } catch (err) {
      setError(err.message || "Failed to delete document");
    } finally {
      setDeletingId(null);
    }
  };

  const runSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setResults(null);
      return;
    }
    setSearching(true);
    setError("");
    try {
      setResults(await api.searchDocuments(searchQuery, 5));
    } catch (err) {
      setError(err.message || "Search failed");
    } finally {
      setSearching(false);
    }
  };

  if (loading) {
    return (
      <div className="documents-page">
        <LoadingSpinner text="Loading documents…" />
      </div>
    );
  }

  return (
    <div className="documents-page">
      <div className="data-header">
        <div>
          <h2>{t("My Documents")}</h2>
          <p className="data-subtitle">
            {t(
              "Add your own files (PDF, DOCX, TXT, MD, CSV). They are stored in your private library and indexed for semantic search — separate from the regulatory corpus."
            )}
          </p>
        </div>
      </div>

      {toast && (
        <div className="toast">
          <CheckCircle className="w-4 h-4 inline mr-2" />
          {toast}
        </div>
      )}

      {error && (
        <Card className="mb-6 border-[var(--bad)]/30 bg-[var(--bad-muted)]">
          <div className="flex items-center gap-2 text-[var(--bad)] text-sm">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {error}
          </div>
        </Card>
      )}

      {/* Tags */}
      <input
        className="document-tags-input"
        type="text"
        placeholder={t("Tags / collection (optional) — e.g. contracts, 2024")}
        value={tags}
        onChange={(e) => setTags(e.target.value)}
        disabled={uploading}
      />

      {/* Upload */}
      <label className={`upload-drop ${uploading ? "busy" : ""}`}>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          onChange={onFiles}
          disabled={uploading}
        />
        {uploading ? (
          <>
            <Loader2 className="w-6 h-6 animate-spin" />
            <span>{t("Uploading and indexing…")}</span>
          </>
        ) : (
          <>
            <Upload className="w-6 h-6" />
            <span>
              {t("Choose files or drop them here — PDF, DOCX, TXT, MD, CSV")}
            </span>
          </>
        )}
      </label>

      {/* Library */}
      <h3 className="documents-section-title">{t("Library")} ({docs.length})</h3>
      {docs.length === 0 ? (
        <div className="data-empty">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>{t("No documents yet. Add your first file above.")}</p>
        </div>
      ) : (
        <div className="document-list">
          {docs.map((doc) => (
            <div className="document-item" key={doc.id}>
              <div className="document-icon">
                <FileText className="w-5 h-5" />
              </div>
              <div className="document-main">
                <div className="document-name" title={doc.filename}>
                  {doc.filename}
                </div>
                <div className="document-meta">
                  <span>{formatBytes(doc.size_bytes)}</span>
                  <span>·</span>
                  <span>{doc.num_chunks} chunk{doc.num_chunks !== 1 ? "s" : ""}</span>
                  <span>·</span>
                  <span>{formatDate(doc.created_at)}</span>
                  {doc.tags && <Badge variant="info">{doc.tags}</Badge>}
                  {doc.status === "error" && (
                    <Badge variant="danger">error</Badge>
                  )}
                </div>
                {doc.error && <div className="document-error">{doc.error}</div>}
              </div>
              <button
                className="data-delete-btn"
                onClick={() => doDelete(doc.id)}
                disabled={deletingId === doc.id}
                title="Delete document"
                aria-label={`Delete ${doc.filename}`}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Search */}
      <h3 className="documents-section-title">{t("Search my documents")}</h3>
      <form className="data-toolbar" onSubmit={runSearch}>
        <div className="history-search">
          <Search className="w-4 h-4" />
          <input
            type="text"
            placeholder={t("Ask something about your documents…")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <Button type="submit" variant="secondary" isLoading={searching}>
          Search
        </Button>
      </form>

      {searching && <LoadingSpinner size="sm" text={t("Searching…")} />}

      {results && results.length === 0 && (
        <div className="data-empty">
          <Search className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>{t("No matches in your documents.")}</p>
        </div>
      )}

      {results && results.length > 0 && (
        <div className="doc-search-results">
          {results.map((r) => (
            <Card key={r.chunk_id} padding="sm">
              <div className="doc-result-head">
                <FileText className="w-3.5 h-3.5" />
                <span className="doc-result-name">{r.filename}</span>
                <span className="doc-result-score">
                  {Math.round((r.score || 0) * 100)}%
                </span>
              </div>
              <p className="doc-result-text">{r.text}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
