import { useState, useEffect } from "react";
import { getSettings, setSetting } from "../api/settings";
import {
  Filter,
  Bell,
  Moon,
  Globe,
  Database,
  Server,
  Info,
  CheckCircle,
} from "lucide-react";
import Toggle from "../components/ui/Toggle";
import Card from "../components/ui/Card";

export default function SettingsPage() {
  const [includeRepealed, setIncludeRepealed] = useState(false);
  const [darkMode, setDarkMode] = useState(true);
  const [notifications, setNotifications] = useState(true);
  const [autoExpandSources, setAutoExpandSources] = useState(true);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const s = getSettings();
    setIncludeRepealed(s.includeRepealed || false);
  }, []);

  const handleToggle = (key, value, setter) => {
    setter(value);
    if (key) setSetting(key, value);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="settings-page">
      <h2>Settings</h2>

      {saved && (
        <div className="toast">
          <CheckCircle className="w-4 h-4 inline mr-2" />
          Settings saved
        </div>
      )}

      {/* Retrieval Settings */}
      <Card className="mb-6">
        <div className="settings-group">
          <h3 className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-[var(--accent)]" />
            Retrieval
          </h3>
          <div className="settings-row">
            <div className="flex-1">
              <label className="block text-sm font-medium text-[var(--text)]">
                Include repealed / superseded acts
              </label>
              <p className="settings-desc">
                When enabled, search results include legislation that has been repealed,
                expired, or superseded. Disabled by default — only <em>In Force</em> acts
                are returned.
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
            Display
          </h3>
          <div className="settings-row">
            <div className="flex-1">
              <label className="block text-sm font-medium text-[var(--text)]">
                Dark mode
              </label>
              <p className="settings-desc">
                Use dark color scheme throughout the application.
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
                Auto-expand sources
              </label>
              <p className="settings-desc">
                Automatically expand the sources panel in chat responses.
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

      {/* Notifications */}
      <Card className="mb-6">
        <div className="settings-group">
          <h3 className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-[var(--accent)]" />
            Notifications
          </h3>
          <div className="settings-row">
            <div className="flex-1">
              <label className="block text-sm font-medium text-[var(--text)]">
                Enable notifications
              </label>
              <p className="settings-desc">
                Receive browser notifications for long-running queries.
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
            API Information
          </h3>
          <div className="space-y-3">
            <div className="settings-info">
              <Database className="w-4 h-4" />
              <span>Local vector store with CEPS EurLex dataset</span>
            </div>
            <div className="settings-info">
              <Globe className="w-4 h-4" />
              <span>LLM generation via OpenRouter API</span>
            </div>
            <div className="settings-info">
              <Info className="w-4 h-4" />
              <span>Dataset frozen at August 2019</span>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
