import { useEffect, useState } from "react";
import api from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import WhatsApp from "@/pages/society/WhatsApp";
import { Loader2, MessageSquare } from "lucide-react";

export default function SuperWhatsApp() {
  const [societies, setSocieties] = useState([]);
  const [sel, setSel] = useState("");

  useEffect(() => {
    api.get("/super/societies")
      .then((r) => { setSocieties(r.data); if (r.data[0]) setSel(r.data[0].id); })
      .catch(() => {});
  }, []);

  const current = societies.find((s) => s.id === sel);

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="WhatsApp Integration" subtitle="Super Admin">
        <Select value={sel} onValueChange={setSel}>
          <SelectTrigger data-testid="wa-society-select" className="w-64">
            <SelectValue placeholder="Select a society" />
          </SelectTrigger>
          <SelectContent>
            {societies.map((s) => (
              <SelectItem key={s.id} value={s.id} data-testid={`wa-society-${s.code}`}>{s.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </PageHeader>

      {societies.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-card p-12 text-center text-sm text-zinc-500">
          <MessageSquare className="mx-auto mb-3 h-8 w-8 text-zinc-300" />
          No societies yet. Add a society first to configure WhatsApp.
        </div>
      ) : !sel ? (
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      ) : (
        <div>
          <p className="mb-4 text-xs text-zinc-400">
            Configuring WhatsApp for <span className="font-medium text-brand">{current?.name}</span>
          </p>
          <WhatsApp societyId={sel} embedded key={sel} />
        </div>
      )}
    </div>
  );
}
