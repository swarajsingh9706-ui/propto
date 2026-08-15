import { Search, Bell } from "lucide-react";

// Sticky top header shown on dashboards
export function TopHeader({ greeting, subtitle }) {
  return (
    <div
      data-testid="dash-topheader"
      className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-white px-7 py-4 shadow-[0_1px_3px_rgba(0,0,0,0.06)]"
    >
      <div>
        <div className="text-[19px] font-extrabold text-slate-900">{greeting}</div>
        <div className="mt-0.5 text-[13px] text-slate-400">{subtitle}</div>
      </div>
      <div className="flex items-center gap-2.5">
        <div className="hidden items-center gap-2 rounded-[9px] border border-border bg-slate-50 px-3.5 py-2 text-[13px] text-slate-500 sm:flex">
          <Search className="h-4 w-4" /> <span>Search tickets, vendors…</span>
        </div>
        <div className="relative flex h-[38px] w-[38px] cursor-pointer items-center justify-center rounded-full border border-border bg-slate-50">
          <Bell className="h-[17px] w-[17px] text-slate-500" />
          <span className="absolute right-[3px] top-[3px] h-[9px] w-[9px] rounded-full border-2 border-white bg-red-600" />
        </div>
      </div>
    </div>
  );
}

// Stat card with colored top border (matches reference)
export function DashStat({ value, label, sub, color, icon: Icon, iconBg, testid }) {
  return (
    <div
      data-testid={testid}
      className="flex-1 rounded-xl border border-border bg-white p-3.5 shadow-[0_1px_3px_rgba(0,0,0,0.04)]"
      style={{ borderTopWidth: 3, borderTopColor: color }}
    >
      <div className="mb-1 flex items-start justify-between">
        <div className="text-[28px] font-black leading-none" style={{ color }}>{value}</div>
        <div className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ background: iconBg }}>
          {Icon && <Icon className="h-4 w-4" style={{ color }} />}
        </div>
      </div>
      <div className="text-[13px] font-bold text-slate-900">{label}</div>
      <div className="mt-0.5 text-[11px] text-slate-400">{sub}</div>
    </div>
  );
}

export function Panel({ title, icon, action, danger, children, testid }) {
  return (
    <div
      data-testid={testid}
      className={`mb-4 overflow-hidden rounded-xl border bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)] ${danger ? "border-red-200" : "border-border"}`}
    >
      <div className={`flex items-center justify-between px-[18px] py-3 ${danger ? "border-b border-red-200" : "border-b border-border"}`}>
        <div className="flex items-center gap-2 text-[14px] font-extrabold text-slate-900">
          {icon}{title}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}

const PRIO_DOT = { Critical: "#dc2626", High: "#ef4444", Medium: "#d97706", Low: "#16a34a" };
export function PriorityDot({ priority }) {
  const c = PRIO_DOT[priority] || "#94a3b8";
  return (
    <span className="inline-flex items-center gap-1.5 text-[12px] font-bold" style={{ color: c }}>
      <span className="inline-block h-[7px] w-[7px] rounded-full" style={{ background: c }} />
      {priority || "—"}
    </span>
  );
}

// SLA progress bar computed from created_at + sla_hours
export function SLABar({ createdAt, slaHours }) {
  if (!slaHours) return <span className="text-[11px] text-slate-400">—</span>;
  const elapsed = (Date.now() - new Date(createdAt).getTime()) / 3600000;
  const pct = Math.min(100, Math.round((elapsed / slaHours) * 100));
  const over = elapsed >= slaHours;
  const warn = pct >= 75;
  const fill = over ? "#dc2626" : warn ? "#d97706" : "#16a34a";
  const track = over ? "#fee2e2" : warn ? "#fef3c7" : "#dcfce7";
  return (
    <div>
      <div className="mb-[3px] h-1.5 rounded" style={{ background: track }}>
        <div className="h-1.5 rounded" style={{ width: `${Math.max(6, pct)}%`, background: fill }} />
      </div>
      <div className="text-[10px] font-bold" style={{ color: fill }}>
        {elapsed.toFixed(1)}h / {slaHours}.0h SLA
      </div>
    </div>
  );
}
