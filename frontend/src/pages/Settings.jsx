import { useState, useEffect } from "react";
import { getSettings, setSetting, LANGUAGES } from "../api/settings";
import { useAuth } from "../api/AuthContext";
import { useI18n } from "../i18n";
import * as api from "../api/client";
import {
  Filter,
  Bell,
  Moon,
  Globe,
  Database,
  Server,
  Info,
  CheckCircle,
  User,
  Lock,
} from "lucide-react";
import Toggle from "../components/ui/Toggle";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";
import Button from "../components/ui/Button";
import UsersPanel from "../components/UsersPanel";

function Message({ msg }) {
  if (!msg?.text) return null;
  return (
    <p className={`settings-msg ${msg.type === "ok" ? "ok" : "err"}`}>
      {msg.text}
    </p>
  );
}

export default function SettingsPage() {
  const { user, refresh } = useAuth();
  const { lang, setLang, t } = useI18n();
  const [includeRepealed, setIncludeRepealed] = useState(false);
  const [darkMode, setDarkMode] = useState(true);
  const [notifications, setNotifications] = useState(true);
  const [autoExpandSources, setAutoExpandSources] = useState(true);
  const [saved, setSaved] = useState(false);

  const [username, setUsername] = useState(user?.username || "");
  const [usernameMsg, setUsernameMsg] = useState({ type: "", text: "" });
  const [savingUsername, setSavingUsername] = useState(false);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwMsg, setPwMsg] = useState({ type: "", text: "" });
  const [savingPw, setSavingPw] = useState(false);

  useEffect(() => {
    const s = getSettings();
    setIncludeRepealed(s.includeRepealed || false);
  }, []);

  useEffect(() => {
    setUsername(user?.username || "");
  }, [user?.username]);

  const flashSaved = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleLanguage = (code) => {
    setLang(code);
    flashSaved();
  };

  const handleToggle = (key, value, setter) => {
    setter(value);
    if (key) setSetting(key, value);
    flashSaved();
  };

  const saveUsername = async (e) => {
    e.preventDefault();
    setSavingUsername(true);
    setUsernameMsg({ type: "", text: "" });
    try {
      await api.updateUsername(username.trim());
      await refresh();
      setUsernameMsg({ type: "ok", text: t("Username updated.") });
    } catch (err) {
      setUsernameMsg({
        type: "err",
        text: err.message || "Failed to update username",
      });
    } finally {
      setSavingUsername(false);
    }
  };

  const savePassword = async (e) => {
    e.preventDefault();
    if (newPw.length < 8) {
      setPwMsg({
        type: "err",
        text: t("New password must be at least 8 characters."),
      });
      return;
    }
    if (newPw !== confirmPw) {
      setPwMsg({ type: "err", text: t("New passwords do not match.") });
      return;
    }
    setSavingPw(true);
    setPwMsg({ type: "", text: "" });
    try {
      await api.updatePassword(currentPw, newPw);
      setCurrentPw("");
      setNewPw("");
      setConfirmPw("");
      setPwMsg({ type: "ok", text: t("Password changed.") });
    } catch (err) {
      setPwMsg({
        type: "err",
        text: err.message || "Failed to change password",
      });
    } finally {
      setSavingPw(false);
    }
  };

  return (
    <div className="settings-page">
      <h2>{t("Settings")}</h2>

      {saved && (
        <div className="toast">
          <CheckCircle className="w-4 h-4 inline mr-2" />
          {t("Settings saved")}
        </div>
      )}

      {/* Account */}
      <Card className="mb-6">
        <div className="settings-group">
          <h3 className="flex items-center gap-2">
            <User className="w-4 h-4 text-[var(--accent)]" />
            {t("Account")}
          </h3>

          <form className="settings-subform" onSubmit={saveUsername}>
            <Input
              label={t("Username")}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              minLength={3}
              maxLength={40}
              required
            />
            <Message msg={usernameMsg} />
            <div className="settings-subform-actions">
              <Button
                type="submit"
                variant="secondary"
                isLoading={savingUsername}
                disabled={!username.trim() || username.trim() === user?.username}
              >
                {t("Save username")}
              </Button>
            </div>
          </form>

          <form className="settings-subform" onSubmit={savePassword}>
            <h4 className="settings-subtitle">
              <Lock className="w-3.5 h-3.5" /> {t("Change password")}
            </h4>
            <Input
              label={t("Current password")}
              type="password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              required
            />
            <Input
              label={t("New password")}
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              minLength={8}
              required
            />
            <Input
              label={t("Confirm new password")}
              type="password"
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              minLength={8}
              required
            />
            <Message msg={pwMsg} />
            <div className="settings-subform-actions">
              <Button
                type="submit"
                variant="secondary"
                isLoading={savingPw}
                disabled={!currentPw || !newPw || !confirmPw}
              >
                {t("Change password")}
              </Button>
            </div>
          </form>
        </div>
      </Card>

      {/* Retrieval Settings */}
      <Card className="mb-6">
        <div className="settings-group">
          <h3 className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-[var(--accent)]" />
            {t("Retrieval")}
          </h3>
          <div className="settings-row">
            <div className="flex-1">
              <label className="block text-sm font-medium text-[var(--text)]">
                {t("Include repealed / superseded acts")}
              </label>
              <p className="settings-desc">
                {t(
                  "When enabled, search results include legislation that has been repealed, expired, or superseded. Disabled by default — only In Force acts are returned."
                )}
              </p>
            </div>
            <div className="settings-control">
              <Toggle
                checked={includeRepealed}
                onChange={(v) => handleToggle("includeRepealed", v, setIncludeRepealed)}
              />
            </div>
          </div>
        </div>
      </Card>

      {/* Display Settings */}
      <Card className="mb-6">
        <div className="settings-group">
          <h3 className="flex items-center gap-2">
            <Moon className="w-4 h-4 text-[var(--accent)]" />
            {t("Display")}
          </h3>
          <div className="settings-row">
            <div className="flex-1">
              <label className="block text-sm font-medium text-[var(--text)]">
                {t("Dark mode")}
              </label>
              <p className="settings-desc">
                {t("Use dark color scheme throughout the application.")}
              </p>
            </div>
            <div className="settings-control">
              <Toggle
                checked={darkMode}
                onChange={(v) => handleToggle(null, v, setDarkMode)}
              />
            </div>
          </div>
          <div className="settings-row">
            <div className="flex-1">
              <label className="block text-sm font-medium text-[var(--text)]">
                {t("Auto-expand sources")}
              </label>
              <p className="settings-desc">
                {t("Automatically expand the sources panel in chat responses.")}
              </p>
            </div>
            <div className="settings-control">
              <Toggle
                checked={autoExpandSources}
                onChange={(v) => handleToggle(null, v, setAutoExpandSources)}
              />
            </div>
          </div>
        </div>
      </Card>

      {/* Language */}
      <Card className="mb-6">
        <div className="settings-group">
          <h3 className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-[var(--accent)]" />
            {t("Language")}
          </h3>
          <div className="settings-row">
            <div className="flex-1">
              <label className="block text-sm font-medium text-[var(--text)]">
                {t("Interface & answers")}
              </label>
              <p className="settings-desc">
                {t(
                  "Changes the interface language and the language the assistant replies in. CELEX numbers, act titles, and links stay unchanged."
                )}
              </p>
            </div>
            <div className="settings-control">
              <select
                className="settings-select"
                value={lang}
                onChange={(e) => handleLanguage(e.target.value)}
              >
                {LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      </Card>

      {/* Notifications */}
      <Card className="mb-6">
        <div className="settings-group">
          <h3 className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-[var(--accent)]" />
            {t("Notifications")}
          </h3>
          <div className="settings-row">
            <div className="flex-1">
              <label className="block text-sm font-medium text-[var(--text)]">
                {t("Enable notifications")}
              </label>
              <p className="settings-desc">
                {t("Receive browser notifications for long-running queries.")}
              </p>
            </div>
            <div className="settings-control">
              <Toggle
                checked={notifications}
                onChange={(v) => handleToggle(null, v, setNotifications)}
              />
            </div>
          </div>
        </div>
      </Card>

      {/* API Information */}
      <Card className="mb-6">
        <div className="settings-group">
          <h3 className="flex items-center gap-2">
            <Server className="w-4 h-4 text-[var(--accent)]" />
            {t("API Information")}
          </h3>
          <div className="space-y-3">
            <div className="settings-info">
              <Database className="w-4 h-4" />
              <span>{t("Local vector store with CEPS EurLex dataset")}</span>
            </div>
            <div className="settings-info">
              <Globe className="w-4 h-4" />
              <span>{t("LLM generation via OpenRouter API")}</span>
            </div>
            <div className="settings-info">
              <Info className="w-4 h-4" />
              <span>{t("Dataset frozen at August 2019")}</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Users (admin only) */}
      {user?.is_admin && (
        <Card className="mb-6">
          <div className="settings-group">
            <UsersPanel />
          </div>
        </Card>
      )}
    </div>
  );
}
