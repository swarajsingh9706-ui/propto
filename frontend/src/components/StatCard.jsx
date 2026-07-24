export function StatCard({ label, value, icon: Icon, accent = "text-zinc-900", testid }) {
  return (
    <div data-testid={testid} className="card-hover rounded-lg border border-border bg-card p-5">
      <div className="flex items-start justify-between">
        <span className="overline">{label}</span>
        {Icon && <Icon className="h-4 w-4 text-zinc-400" strokeWidth={1.75} />}
      </div>
      <p className={`mt-3 font-cabinet text-4xl font-bold tracking-tight ${accent}`}>{value}</p>
    </div>
  );
}
