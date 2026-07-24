const STATUS = {
  Open: "bg-blue-50 text-blue-700 border-blue-200",
  Pending: "bg-amber-50 text-amber-700 border-amber-200",
  Resolved: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Escalated: "bg-red-50 text-red-700 border-red-200",
};
const PRIORITY = {
  High: "bg-red-50 text-red-700 border-red-200",
  Medium: "bg-amber-50 text-amber-700 border-amber-200",
  Low: "bg-zinc-100 text-zinc-600 border-zinc-200",
};

export function StatusBadge({ status, testid }) {
  const cls = STATUS[status] || "bg-zinc-100 text-zinc-600 border-zinc-200";
  return (
    <span data-testid={testid} className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

export function PriorityBadge({ priority, testid }) {
  const cls = PRIORITY[priority] || PRIORITY.Low;
  return (
    <span data-testid={testid} className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {priority}
    </span>
  );
}
