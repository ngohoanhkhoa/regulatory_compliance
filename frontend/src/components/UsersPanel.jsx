import { useState, useEffect, useCallback } from "react";
import * as api from "../api/client";
import { useAuth } from "../api/AuthContext";
import Card from "./ui/Card";
import Button from "./ui/Button";
import Badge from "./ui/Badge";
import Input from "./ui/Input";
import Modal from "./ui/Modal";
import LoadingSpinner from "./ui/LoadingSpinner";
import {
  Plus,
  Trash2,
  KeyRound,
  Pencil,
  ShieldCheck,
  ShieldOff,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";

function formatDate(ts) {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

const EMPTY_CREATE = { username: "", password: "", is_admin: false };

export default function UsersPanel() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(EMPTY_CREATE);
  const [savingCreate, setSavingCreate] = useState(false);

  const [renameTarget, setRenameTarget] = useState(null);
  const [renameValue, setRenameValue] = useState("");

  const [pwTarget, setPwTarget] = useState(null);
  const [pwValue, setPwValue] = useState("");

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(
    () =>
      api
        .listUsers()
        .then(setUsers)
        .catch((err) => setError(err.message || "Failed to load users")),
    []
  );

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  };

  const doCreate = async (e) => {
    e.preventDefault();
    setSavingCreate(true);
    setError("");
    try {
      await api.createUser(createForm);
      showToast(`Created “${createForm.username}”`);
      setCreateOpen(false);
      setCreateForm(EMPTY_CREATE);
      await load();
    } catch (err) {
      setError(err.message || "Failed to create user");
    } finally {
      setSavingCreate(false);
    }
  };

  const doRename = async () => {
    if (renameValue.trim().length < 3) return;
    try {
      await api.adminSetUsername(renameTarget.id, renameValue.trim());
      showToast("Username updated");
      setRenameTarget(null);
      await load();
    } catch (err) {
      setError(err.message || "Failed to rename user");
    }
  };

  const doResetPassword = async () => {
    if (pwValue.length < 8) return;
    try {
      await api.adminSetPassword(pwTarget.id, pwValue);
      showToast(`Password reset for “${pwTarget.username}”`);
      setPwTarget(null);
      setPwValue("");
    } catch (err) {
      setError(err.message || "Failed to reset password");
    }
  };

  const doToggleAdmin = async (u) => {
    if (u.is_admin && !window.confirm(`Remove admin rights from “${u.username}”?`)) {
      return;
    }
    try {
      await api.adminSetAdmin(u.id, !u.is_admin);
      showToast(u.is_admin ? "Admin rights removed" : "Admin rights granted");
      await load();
    } catch (err) {
      setError(err.message || "Failed to update user");
    }
  };

  const doDelete = async () => {
    if (deleteConfirm.trim() !== deleteTarget.username) return;
    setDeleting(true);
    try {
      await api.deleteUser(deleteTarget.id);
      showToast(`Deleted “${deleteTarget.username}”`);
      setDeleteTarget(null);
      setDeleteConfirm("");
      await load();
    } catch (err) {
      setError(err.message || "Failed to delete user");
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return <LoadingSpinner size="sm" text="Loading users…" />;
  }

  const deleteNameMatches =
    deleteTarget && deleteConfirm.trim() === deleteTarget.username;

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

      <div className="users-header">
        <h3 className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-[var(--accent)]" />
          Users ({users.length})
        </h3>
        <Button
          variant="secondary"
          icon={Plus}
          onClick={() => {
            setCreateForm(EMPTY_CREATE);
            setCreateOpen(true);
          }}
        >
          Add user
        </Button>
      </div>

      <div className="users-table">
        <div className="users-table-head">
          <span>Username</span>
          <span>Role</span>
          <span>Created</span>
          <span className="text-right">Actions</span>
        </div>
        {users.map((u) => (
          <div className="users-table-row" key={u.id}>
            <span className="users-name">
              {u.username}
              {me?.id === u.id && <em className="users-you">you</em>}
            </span>
            <span>
              {u.is_admin ? (
                <Badge variant="success">admin</Badge>
              ) : (
                <Badge>user</Badge>
              )}
            </span>
            <span className="data-date">{formatDate(u.created_at)}</span>
            <span className="users-actions">
              <button
                className="icon-btn"
                title="Rename user"
                onClick={() => {
                  setRenameValue(u.username);
                  setRenameTarget(u);
                }}
              >
                <Pencil className="w-3.5 h-3.5" />
              </button>
              <button
                className="icon-btn"
                title="Reset password"
                onClick={() => {
                  setPwValue("");
                  setPwTarget(u);
                }}
              >
                <KeyRound className="w-3.5 h-3.5" />
              </button>
              <button
                className="icon-btn"
                title={u.is_admin ? "Remove admin" : "Make admin"}
                disabled={me?.id === u.id}
                onClick={() => doToggleAdmin(u)}
              >
                {u.is_admin ? (
                  <ShieldOff className="w-3.5 h-3.5" />
                ) : (
                  <ShieldCheck className="w-3.5 h-3.5" />
                )}
              </button>
              <button
                className="icon-btn danger"
                title="Delete user"
                disabled={me?.id === u.id}
                onClick={() => {
                  setDeleteConfirm("");
                  setDeleteTarget(u);
                }}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </span>
          </div>
        ))}
      </div>

      {/* Create user */}
      <Modal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Add user"
      >
        <form className="topic-form" onSubmit={doCreate}>
          <Input
            label="Username"
            value={createForm.username}
            onChange={(e) =>
              setCreateForm({ ...createForm, username: e.target.value })
            }
            placeholder="At least 3 characters"
            minLength={3}
            maxLength={40}
            required
          />
          <Input
            label="Password"
            type="password"
            value={createForm.password}
            onChange={(e) =>
              setCreateForm({ ...createForm, password: e.target.value })
            }
            placeholder="At least 8 characters"
            minLength={8}
            required
          />
          <label className="users-checkbox">
            <input
              type="checkbox"
              checked={createForm.is_admin}
              onChange={(e) =>
                setCreateForm({ ...createForm, is_admin: e.target.checked })
              }
            />
            Grant admin rights
          </label>
          <div className="topic-form-actions">
            <Button
              type="button"
              variant="ghost"
              onClick={() => setCreateOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" icon={Plus} isLoading={savingCreate}>
              Create user
            </Button>
          </div>
        </form>
      </Modal>

      {/* Rename user */}
      <Modal
        isOpen={!!renameTarget}
        onClose={() => setRenameTarget(null)}
        title="Change username"
      >
        <Input
          label="New username"
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          minLength={3}
          maxLength={40}
        />
        <div className="topic-form-actions">
          <Button variant="ghost" onClick={() => setRenameTarget(null)}>
            Cancel
          </Button>
          <Button
            disabled={renameValue.trim().length < 3}
            onClick={doRename}
          >
            Save
          </Button>
        </div>
      </Modal>

      {/* Reset password */}
      <Modal
        isOpen={!!pwTarget}
        onClose={() => setPwTarget(null)}
        title={`Reset password — ${pwTarget?.username || ""}`}
      >
        <Input
          label="New password"
          type="password"
          value={pwValue}
          onChange={(e) => setPwValue(e.target.value)}
          placeholder="At least 8 characters"
          minLength={8}
        />
        <div className="topic-form-actions">
          <Button variant="ghost" onClick={() => setPwTarget(null)}>
            Cancel
          </Button>
          <Button disabled={pwValue.length < 8} icon={KeyRound} onClick={doResetPassword}>
            Reset password
          </Button>
        </div>
      </Modal>

      {/* Delete user */}
      <Modal
        isOpen={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Delete user"
      >
        <div className="danger-notice">
          <AlertTriangle className="w-5 h-5" />
          <div>
            <strong>
              This permanently deletes “{deleteTarget?.username}”.
            </strong>
            <ul>
              <li>Removes their documents, files, and indexed vectors.</li>
              <li>Removes their topics, query history, and feedback.</li>
              <li>This action cannot be undone.</li>
            </ul>
          </div>
        </div>
        <label className="confirm-type">
          <span>
            Type <strong>{deleteTarget?.username}</strong> to confirm:
          </span>
          <input
            type="text"
            value={deleteConfirm}
            onChange={(e) => setDeleteConfirm(e.target.value)}
            placeholder={deleteTarget?.username}
            disabled={deleting}
          />
        </label>
        <div className="topic-form-actions">
          <Button
            variant="ghost"
            onClick={() => setDeleteTarget(null)}
            disabled={deleting}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            icon={Trash2}
            isLoading={deleting}
            disabled={!deleteNameMatches}
            onClick={doDelete}
          >
            Delete user
          </Button>
        </div>
      </Modal>
    </>
  );
}
