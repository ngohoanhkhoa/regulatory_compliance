import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../api/client";
import { useAuth } from "../api/AuthContext";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";
import Badge from "../components/ui/Badge";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import {
  Database,
  FileText,
  Upload,
  Layers,
  CheckCircle,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";

function kindMeta(kind) {
  if (kind === "documents") {
    return { label: "Documents", variant: "info", icon: FileText };
  }
  return { label: "Regulatory", variant: "success", icon: Database };
}

export default function Datasets() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const fileRef = useRef(null);

  const load = useCallback(() => {
    return api
      .getDatasets()
      .then(setDatasets)
      .catch((err) => setError(err.message || "Failed to load datasets"));
  }, []);

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const onImport = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      const res = await api.importDataset(file);
      showToast(`Imported dataset “${res.dataset?.name}”`);
      await load();
    } catch (err) {
      setError(err.message || "Import failed");
    } finally {
      setImporting(false);
    }
  };

  if (loading) {
    return (
      <div className="data-page">
        <LoadingSpinner text="Loading datasets…" />
      </div>
    );
  }

  const regulatory = datasets.filter((d) => d.kind === "regulatory");
  const documents = datasets.filter((d) => d.kind === "documents");

  const renderCard = (d) => {
    const meta = kindMeta(d.kind);
    const Icon = meta.icon;
    return (
      <button
        key={d.id}
        className="dataset-card"
        onClick={() => navigate(`/datasets/${d.id}`)}
      >
        <div className="dataset-card-top">
          <div className={`stat-icon ${d.kind === "documents" ? "blue" : "green"}`}>
            <Icon className="w-4 h-4" />
          </div>
          <Badge variant={meta.variant}>{meta.label}</Badge>
        </div>
        <div className="dataset-card-name">{d.name}</div>
        <div className="dataset-card-desc">{d.description || "—"}</div>
        <div className="dataset-card-stats">
          <span>{d.items} item{d.items !== 1 ? "s" : ""}</span>
          <span>·</span>
          <span>{d.chunks} chunk{d.chunks !== 1 ? "s" : ""}</span>
          {d.vectors != null && (
            <>
              <span>·</span>
              <span>{d.vectors} vectors</span>
            </>
          )}
        </div>
        <span className="dataset-card-open">
          Open <ChevronRight className="w-3.5 h-3.5" />
        </span>
      </button>
    );
  };

  return (
    <div className="data-page">
      <div className="data-header">
        <div>
          <h2>Datasets</h2>
          <p className="data-subtitle">
            Your private documents and the regulatory text collections you can
            chat with. Regulatory datasets are shared read-only; admins can import
            or remove them.
          </p>
        </div>
        {user?.is_admin && (
          <>
            <input
              ref={fileRef}
              type="file"
              accept=".zip"
              hidden
              onChange={onImport}
            />
            <Button
              variant="primary"
              icon={Upload}
              isLoading={importing}
              onClick={() => fileRef.current?.click()}
            >
              Import regulatory dataset
            </Button>
          </>
        )}
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
            <AlertTriangle className="w-4 h-4" />
            {error}
          </div>
        </Card>
      )}

      <h3 className="documents-section-title">
        <Layers className="w-4 h-4 inline mr-2" />
        Regulatory texts ({regulatory.length})
      </h3>
      {regulatory.length === 0 ? (
        <div className="data-empty">
          <Database className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p>No regulatory datasets yet.</p>
        </div>
      ) : (
        <div className="dataset-grid">{regulatory.map(renderCard)}</div>
      )}

      <h3 className="documents-section-title" style={{ marginTop: "2rem" }}>
        <FileText className="w-4 h-4 inline mr-2" />
        My documents ({documents.length})
      </h3>
      <div className="dataset-grid">{documents.map(renderCard)}</div>
    </div>
  );
}
