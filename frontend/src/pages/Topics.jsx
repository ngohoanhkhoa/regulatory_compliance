import { useState, useEffect, useCallback } from "react";
import * as api from "../api/client";
import { useI18n } from "../i18n";
import Button from "../components/ui/Button";
import Input from "../components/ui/Input";
import Badge from "../components/ui/Badge";
import Toggle from "../components/ui/Toggle";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import Modal from "../components/ui/Modal";
import {
  Plus,
  Trash2,
  Pencil,
  RefreshCw,
  ExternalLink,
  Clock,
  Search,
  Layers,
} from "lucide-react";

function formatDate(value) {
  if (!value) return "Date unknown";
  const iso = value.slice(0, 10);
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatDateTime(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function emptyForm() {
  return {
    name: "",
    description: "",
    search_query: "",
    status: "",
    subject_matter: "",
    eurovoc: "",
    include_repealed: false,
  };
}

function formFromTopic(topic) {
  return {
    name: topic.name || "",
    description: topic.description || "",
    search_query: topic.search_query || "",
    status: topic.filters?.status || "",
    subject_matter: topic.filters?.subject_matter || "",
    eurovoc: topic.filters?.eurovoc || "",
    include_repealed: !!topic.include_repealed,
  };
}

function effectiveQuery(topic) {
  if (topic?.search_query?.trim()) return topic.search_query.trim();
  return [topic?.name, topic?.description].filter(Boolean).join(" ");
}

function buildFilters(form) {
  const filters = {};
  if (form.status?.trim()) filters.status = form.status.trim();
  if (form.subject_matter?.trim()) filters.subject_matter = form.subject_matter.trim();
  if (form.eurovoc?.trim()) filters.eurovoc = form.eurovoc.trim();
  return Object.keys(filters).length ? filters : null;
}

function statusVariant(status) {
  if (!status) return "default";
  return status.toLowerCase() === "in force" ? "success" : "warning";
}

function TimelineView({ timeline, loading, refreshing }) {
  if (loading) return <LoadingSpinner text="Researching regulatory texts…" />;
  if (!timeline) return null;

  const { items } = timeline;
  if (!items.length) {
    return (
      <div className="topic-empty">
        <Layers className="w-10 h-10 mx-auto mb-3 text-[var(--text-muted)]" />
        <strong>{refreshing ? "Researching…" : "No matching acts found"}</strong>
        {!refreshing && <p>Try a broader topic name or different filters, then Refresh.</p>}
      </div>
    );
  }

  return (
    <>
      <div className="timeline-summary">
        <Clock className="w-4 h-4" />
        {items.length} act{items.length > 1 ? "s" : ""} found
        {refreshing ? (
          <span className="timeline-refreshing">
            <RefreshCw className="w-3 h-3 animate-spin" /> Refreshing…
          </span>
        ) : (
          timeline.generated_at && (
            <span className="timeline-refreshed">
              · Last refreshed {formatDateTime(timeline.generated_at)}
            </span>
          )
        )}
      </div>
      <ol className="topic-timeline">
        {items.map((item) => (
          <li className="timeline-item" key={item.celex}>
            <span className="timeline-dot" />
            <div className="timeline-card">
              <div className="timeline-date">{formatDate(item.date_document)}</div>
              <a
                className="timeline-title"
                href={item.link || "#"}
                target="_blank"
                rel="noopener noreferrer"
              >
                {item.act_name || item.celex}
                {item.link && <ExternalLink className="w-3 h-3" />}
              </a>
              <div className="timeline-meta">
                {item.status && <Badge variant={statusVariant(item.status)}>{item.status}</Badge>}
                {item.temporal_status && (
                  <span className="timeline-temporal">{item.temporal_status}</span>
                )}
                <span className="timeline-celex">{item.celex}</span>
              </div>
              {item.subject_matter && (
                <div className="timeline-subject">{item.subject_matter}</div>
              )}
              {item.summary && <p className="timeline-summary-text">{item.summary}</p>}
              {item.excerpt && <p className="timeline-excerpt">{item.excerpt}…</p>}
            </div>
          </li>
        ))}
      </ol>
    </>
  );
}

export default function Topics() {
  const { t } = useI18n();
  const [topics, setTopics] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [filterText, setFilterText] = useState("");

  const [view, setView] = useState("empty"); // "empty" | "view" | "form"
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [saving, setSaving] = useState(false);

  const [loadingTopics, setLoadingTopics] = useState(true);
  const [loadingTimeline, setLoadingTimeline] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(null);

  const loadTopics = useCallback(async (selectId) => {
    setLoadingTopics(true);
    try {
      const list = await api.getTopics();
      setTopics(list);
      return list;
    } catch (err) {
      setError(err.message || "Failed to load topics");
      return [];
    } finally {
      setLoadingTopics(false);
    }
  }, []);

  useEffect(() => {
    loadTopics();
  }, [loadTopics]);

  const loadTimeline = useCallback(async (topicId) => {
    // Switching topics: clear the old list and show a full spinner.
    setTimeline(null);
    setLoadingTimeline(true);
    setError("");
    try {
      const data = await api.getTopicTimeline(topicId);
      setTimeline(data);
    } catch (err) {
      setTimeline(null);
      setError(err.message || "Failed to load timeline");
    } finally {
      setLoadingTimeline(false);
    }
  }, []);

  const refreshTimeline = useCallback(async (topicId) => {
    // Keep the current list on screen; replace it when the new results arrive.
    setRefreshing(true);
    setError("");
    try {
      const data = await api.refreshTopic(topicId);
      setTimeline(data);
    } catch (err) {
      setError(err.message || "Failed to refresh timeline");
    } finally {
      setRefreshing(false);
    }
  }, []);

  const selectTopic = (topic) => {
    setSelectedId(topic.id);
    setView("view");
    setEditingId(null);
    loadTimeline(topic.id);
  };

  const startCreate = () => {
    setForm(emptyForm());
    setEditingId(null);
    setView("form");
    setError("");
  };

  const startEdit = (topic) => {
    setForm(formFromTopic(topic));
    setEditingId(topic.id);
    setView("form");
    setError("");
  };

  const cancelForm = () => {
    setView(selectedId ? "view" : "empty");
    setError("");
  };

  const save = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setError("Topic name is required");
      return;
    }
    setSaving(true);
    setError("");
    const payload = {
      name: form.name.trim(),
      description: form.description.trim(),
      search_query: form.search_query.trim() || null,
      filters: buildFilters(form),
      include_repealed: form.include_repealed,
    };
    try {
      const saved = editingId
        ? await api.updateTopic(editingId, payload)
        : await api.createTopic(payload);
      await loadTopics();
      setSelectedId(saved.id);
      setView("view");
      setEditingId(null);
      loadTimeline(saved.id);
    } catch (err) {
      setError(err.message || "Failed to save topic");
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async () => {
    if (!confirmDelete) return;
    const id = confirmDelete.id;
    setConfirmDelete(null);
    try {
      await api.deleteTopic(id);
      const list = await loadTopics();
      if (selectedId === id) {
        setSelectedId(null);
        setTimeline(null);
        setView(list.length ? "empty" : "empty");
      }
    } catch (err) {
      setError(err.message || "Failed to delete topic");
    }
  };

  const selectedTopic = topics.find((t) => t.id === selectedId) || null;
  const visibleTopics = topics.filter((t) =>
    t.name.toLowerCase().includes(filterText.trim().toLowerCase())
  );

  return (
    <div className="topics-page">
      <aside className="topics-sidebar">
        <div className="sidebar-header">
          <h3>{t("Topics")}</h3>
          <button className="sidebar-new-btn" onClick={startCreate}>
            <Plus className="w-4 h-4" />
            {t("New Topic")}
          </button>
        </div>

        <div className="topics-search">
          <Search className="w-4 h-4" />
          <input
            type="text"
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            placeholder={t("Filter topics…")}
          />
        </div>

        <div className="topics-list">
          {loadingTopics ? (
            <LoadingSpinner size="sm" text="" />
          ) : visibleTopics.length === 0 ? (
            <p className="topics-empty">
              {topics.length === 0 ? t("No topics yet") : t("No topics match your filter")}
            </p>
          ) : (
            visibleTopics.map((topic) => (
              <div
                key={topic.id}
                className={`topic-item ${selectedId === topic.id ? "active" : ""}`}
                onClick={() => selectTopic(topic)}
                title={topic.name}
              >
                <Layers className="w-4 h-4 shrink-0" />
                <div className="topic-item-content">
                  <span className="truncate">{topic.name}</span>
                  {topic.description && (
                    <span className="topic-item-desc truncate">{topic.description}</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </aside>

      <main className="topics-main">
        {error && <div className="topics-error">{error}</div>}

        {view === "form" && (
          <form className="topic-form" onSubmit={save}>
            <h2>{editingId ? t("Edit Topic") : t("New Topic")}</h2>
            <p className="topic-form-hint">
              Give the topic a name. We search the EurLex corpus for acts that match it and
              plot them on a timeline by document date.
            </p>

            <Input
              label="Topic name"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Data protection"
              maxLength={120}
              required
            />

            <label className="topic-field">
              <span className="topic-field-label">Description</span>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="What this topic covers (optional)"
                rows={3}
                maxLength={2000}
              />
            </label>

            <Input
              label="Search query"
              value={form.search_query}
              onChange={(e) => setForm({ ...form, search_query: e.target.value })}
              placeholder="Defaults to the topic name"
              maxLength={2000}
            />

            <fieldset className="topic-fieldset">
              <legend>Optional filters</legend>
              <div className="topic-filter-grid">
                <Input
                  label="Status"
                  value={form.status}
                  onChange={(e) => setForm({ ...form, status: e.target.value })}
                  placeholder="e.g. In Force"
                />
                <Input
                  label="Subject matter"
                  value={form.subject_matter}
                  onChange={(e) => setForm({ ...form, subject_matter: e.target.value })}
                  placeholder="e.g. data protection"
                />
                <Input
                  label="EUROVOC"
                  value={form.eurovoc}
                  onChange={(e) => setForm({ ...form, eurovoc: e.target.value })}
                  placeholder="e.g. personal data"
                />
              </div>
            </fieldset>

            <Toggle
              label="Include repealed acts"
              description="Also match acts that are no longer in force."
              checked={form.include_repealed}
              onChange={(v) => setForm({ ...form, include_repealed: v })}
            />

            <div className="topic-form-actions">
              <Button type="button" variant="ghost" onClick={cancelForm}>
                Cancel
              </Button>
              <Button type="submit" isLoading={saving}>
                {editingId ? t("Save changes") : t("Create topic")}
              </Button>
            </div>
          </form>
        )}

        {view === "view" && selectedTopic && (
          <div className="topic-view">
            <div className="topic-view-header">
              <div>
                <h2>{selectedTopic.name}</h2>
                {selectedTopic.description && (
                  <p className="topic-view-desc">{selectedTopic.description}</p>
                )}
                <div className="topic-view-meta">
                  <Badge variant="info">query: {effectiveQuery(selectedTopic)}</Badge>
                  {selectedTopic.include_repealed && <Badge variant="warning">incl. repealed</Badge>}
                  {Object.entries(selectedTopic.filters || {}).map(([k, v]) => (
                    <Badge key={k} variant="default">
                      {k}: {v}
                    </Badge>
                  ))}
                </div>
              </div>
              <div className="topic-view-actions">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={RefreshCw}
                  isLoading={refreshing}
                  onClick={() => refreshTimeline(selectedTopic.id)}
                  disabled={refreshing || loadingTimeline}
                >
                  {refreshing ? t("Refreshing…") : t("Refresh")}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={Pencil}
                  onClick={() => startEdit(selectedTopic)}
                >
                  Edit
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  icon={Trash2}
                  onClick={() => setConfirmDelete(selectedTopic)}
                >
                  Delete
                </Button>
              </div>
            </div>

            <TimelineView
              timeline={timeline}
              loading={loadingTimeline}
              refreshing={refreshing}
            />
          </div>
        )}

        {view === "empty" && (
          <div className="topics-empty-main">
            <Layers className="w-14 h-14 mx-auto mb-4 text-[var(--text-muted)]" />
            <strong>{t("Track a regulatory topic")}</strong>
            <p>
              Create a topic to see how EU regulation on a subject changes over time. We
              search the corpus and lay the matching acts out on a timeline.
            </p>
            <Button icon={Plus} onClick={startCreate}>
              {t("Create your first topic")}
            </Button>
          </div>
        )}
      </main>

      <Modal
        isOpen={!!confirmDelete}
        onClose={() => setConfirmDelete(null)}
        title={t("Delete topic")}
      >
        <p className="modal-confirm-text">
          Delete “{confirmDelete?.name}”? This cannot be undone.
        </p>
        <div className="topic-form-actions">
          <Button variant="ghost" onClick={() => setConfirmDelete(null)}>
            Cancel
          </Button>
          <Button variant="danger" icon={Trash2} onClick={doDelete}>
            Delete
          </Button>
        </div>
      </Modal>
    </div>
  );
}
