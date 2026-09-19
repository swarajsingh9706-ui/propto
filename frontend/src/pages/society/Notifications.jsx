import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api, { apiError } from "@/lib/api";
import { useScope } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Loader2, Bell, AlertTriangle, Package, Vote, Users, CheckCheck, Clock,
} from "lucide-react";

const META = {
  overdue: { icon: AlertTriangle, color: "#dc2626", bg: "#fee2e2" },
  escalated: { icon: AlertTriangle, color: "#ea580c", bg: "#ffedd5" },
  asset_overdue: { icon: Package, color: "#dc2626", bg: "#fee2e2" },
  asset_due: { icon: Package, color: "#d97706", bg: "#fef3c7" },
  suggestion: { icon: Vote, color: "#2563eb", bg: "#dbeafe" },
  resident: { icon: Users, color: "#16a34a", bg: "#dcfce7" },
};

function timeAgo(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 604800) return `${Math.floor(s / 86400)}d ago`;
  return d.toLocaleDateString();
}

export default function Notifications() {
  const cfg = useScope();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("all");

  const load = () => {
    setLoading(true);
    api.get("/society/notifications", cfg)
      .then((r) => { setItems(r.data.items); setUnread(r.data.unread); })
      .catch((e) => toast.error(apiError(e)))
      .finally(() => setLoading(false));
  };
  useEffect(load, [cfg.params?.society_id]); // eslint-disable-line

  const markAllRead = async () => {
    try { await api.post("/society/notifications/read", { all: true }, cfg); toast.success("All marked as read"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const markRead = async (id) => {
    try { await api.post("/society/notifications/read", { ids: [id] }, cfg); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const openItem = (n) => { if (!n.read) markRead(n.id); if (n.link) navigate(n.link); };

  const list = tab === "unread" ? items.filter((n) => !n.read) : items;

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="Notifications" subtitle="Alerts & Reminders">
        <Button data-testid="mark-all-read-btn" variant="outline" onClick={markAllRead} disabled={!unread}>
          <CheckCheck className="mr-1.5 h-4 w-4" /> Mark all read
        </Button>
      </PageHeader>

      <div className="mb-5 flex flex-wrap gap-2">
        {[["all", "All"], ["unread", "Unread"]].map(([k, l]) => (
          <button key={k} data-testid={`notif-tab-${k}`} onClick={() => setTab(k)}
            className={`rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-colors ${
              tab === k ? "border-brand bg-brand text-white" : "border-border bg-card text-zinc-600 hover:bg-secondary"}`}>
            {l}{k === "unread" && unread ? ` (${unread})` : ""}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex h-64 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-zinc-400" /></div>
      ) : list.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border bg-card p-12 text-center text-sm text-zinc-400">
          <Bell className="mx-auto mb-3 h-8 w-8 text-zinc-300" />
          {tab === "unread" ? "You're all caught up — no unread notifications." : "No notifications right now."}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-border bg-card shadow-[0_1px_3px_rgba(0,0,0,0.04)]" data-testid="notifications-list">
          {list.map((n) => {
            const m = META[n.type] || { icon: Bell, color: "#64748b", bg: "#f1f5f9" };
            const Icon = m.icon;
            return (
              <button key={n.id} data-testid={`notif-${n.id}`} onClick={() => openItem(n)}
                className={`flex w-full items-start gap-3 border-b border-border px-5 py-3.5 text-left transition-colors last:border-0 hover:bg-secondary/40 ${n.read ? "opacity-60" : ""}`}>
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg" style={{ background: m.bg }}>
                  <Icon className="h-[18px] w-[18px]" style={{ color: m.color }} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    {n.title}
                    {!n.read && <span className="h-2 w-2 flex-shrink-0 rounded-full bg-red-500" />}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-zinc-500">{n.detail}</p>
                </div>
                <span className="flex flex-shrink-0 items-center gap-1 whitespace-nowrap text-[11px] text-zinc-400">
                  <Clock className="h-3 w-3" />{timeAgo(n.time)}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
