import { useEffect, useState, useMemo } from "react";
import * as api from "../api/client";
import {
  MessageSquare,
  CheckCircle,
  XCircle,
  Clock,
  TrendingUp,
  BookOpen,
  AlertTriangle,
  FileText,
  ArrowRight,
} from "lucide-react";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import LoadingSpinner from "../components/ui/LoadingSpinner";
import { Link } from "react-router-dom";

export default function Dashboard() {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getHistory(50)
      .then(setHistory)
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => {
    const total = history.length;
    const grounded = history.filter((h) => h.grounded).length;
    const ungrounded = total - grounded;
    const avgSources =
      total > 0
        ? history.reduce((sum, h) => sum + (h.sources?.length || 0), 0) / total
        : 0;

    // Recent trend (last 7 days)
    const now = new Date();
    const weekAgo = new Date(now - 7 * 24 * 60 * 60 * 1000);
    const recentQueries = history.filter((h) => {
      const d = new Date(h.created_at + (h.created_at?.includes("Z") ? "" : "Z"));
      return d > weekAgo;
    });

    return { total, grounded, ungrounded, avgSources, recentQueries };
  }, [history]);

  const recentActivity = history.slice(0, 10);

  if (loading) {
    return (
      <div className="dashboard-page">
        <LoadingSpinner text="Loading dashboard…" />
      </div>
    );
  }

  return (
    <div className="dashboard-page">
      <h2>Dashboard</h2>

      {/* Stats Grid */}
      <div className="stats-grid">
        <Card className="space-y-2">
          <div className="stat-icon blue">
            <MessageSquare className="w-4 h-4" />
          </div>
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">Total Queries</div>
        </Card>
        <Card className="space-y-2">
          <div className="stat-icon green">
            <CheckCircle className="w-4 h-4" />
          </div>
          <div className="stat-value">{stats.grounded}</div>
          <div className="stat-label">Grounded Answers</div>
        </Card>
        <Card className="space-y-2">
          <div className="stat-icon red">
            <XCircle className="w-4 h-4" />
          </div>
          <div className="stat-value">{stats.ungrounded}</div>
          <div className="stat-label">Ungrounded Answers</div>
        </Card>
        <Card className="space-y-2">
          <div className="stat-icon yellow">
            <BookOpen className="w-4 h-4" />
          </div>
          <div className="stat-value">{stats.avgSources.toFixed(1)}</div>
          <div className="stat-label">Avg Sources per Query</div>
        </Card>
      </div>

      {/* Recent Activity */}
      <div className="dashboard-section">
        <div className="flex items-center justify-between mb-4">
          <h3>Recent Activity</h3>
          <Link
            to="/history"
            className="text-sm text-[var(--accent)] hover:text-[var(--accent-hover)] flex items-center gap-1"
          >
            View all <ArrowRight className="w-4 h-4" />
          </Link>
        </div>

        {recentActivity.length === 0 ? (
          <Card>
            <div className="text-center py-8 text-[var(--text-muted)]">
              <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No queries yet. Start by asking a question in the Chat.</p>
            </div>
          </Card>
        ) : (
          <div className="activity-list">
            {recentActivity.map((h) => (
              <div key={h.id} className="activity-item">
                <div className="activity-icon">
                  <MessageSquare className="w-4 h-4" />
                </div>
                <div className="activity-content">
                  <div className="activity-title">{h.question}</div>
                  <div className="activity-meta flex items-center gap-2">
                    <Clock className="w-3 h-3" />
                    {new Date(
                      h.created_at + (h.created_at?.includes("Z") ? "" : "Z")
                    ).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                    <span>·</span>
                    <span>{h.sources?.length || 0} sources</span>
                  </div>
                </div>
                <div className="activity-badge">
                  <Badge variant={h.grounded ? "success" : "danger"}>
                    {h.grounded ? "Grounded" : "Ungrounded"}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="dashboard-section">
        <h3>Quick Actions</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link to="/chat">
            <Card className="hover:border-[var(--accent)] transition-colors cursor-pointer">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-[var(--accent-muted)] flex items-center justify-center">
                  <MessageSquare className="w-5 h-5 text-[var(--accent)]" />
                </div>
                <div>
                  <div className="font-medium text-[var(--text)]">New Chat</div>
                  <div className="text-sm text-[var(--text-dim)]">Ask a question</div>
                </div>
              </div>
            </Card>
          </Link>
          <Link to="/history">
            <Card className="hover:border-[var(--accent)] transition-colors cursor-pointer">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-[var(--good-muted)] flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-[var(--good)]" />
                </div>
                <div>
                  <div className="font-medium text-[var(--text)]">History</div>
                  <div className="text-sm text-[var(--text-dim)]">View past queries</div>
                </div>
              </div>
            </Card>
          </Link>
          <Link to="/settings">
            <Card className="hover:border-[var(--accent)] transition-colors cursor-pointer">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-[var(--warn-muted)] flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5 text-[var(--warn)]" />
                </div>
                <div>
                  <div className="font-medium text-[var(--text)]">Settings</div>
                  <div className="text-sm text-[var(--text-dim)]">Configure preferences</div>
                </div>
              </div>
            </Card>
          </Link>
        </div>
      </div>
    </div>
  );
}
