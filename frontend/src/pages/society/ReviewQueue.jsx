import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useScope, useFetch } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, ClipboardCheck, AlertTriangle, Check, X } from "lucide-react";

const CATEGORIES = ["Plumbing", "Electrical", "Lift", "Security", "Housekeeping", "Civil", "Parking", "Gardening", "Water Supply", "DG Set", "Pest Control", "Pool AMC Vendor"];
const PRIORITIES = ["High", "Medium", "Low"];

export default function ReviewQueue() {
  const cfg = useScope();
  const { data: items, loading, reload } = useFetch("/society/ai/review-queue");
  const [edits, setEdits] = useState({});
  const [busy, setBusy] = useState(null);

  const getEdit = (item) => edits[item.id] || {
    category: item.ai_result?.category || "", flat: item.ai_result?.flat || "",
    tower: item.ai_result?.tower || "", priority: item.ai_result?.priority || "Medium",
    description: item.ai_result?.description || item.text,
  };
  const setEdit = (id, patch) => setEdits((e) => ({ ...e, [id]: { ...getEdit({ id, ai_result: {} }), ...e[id], ...patch } }));

  const decide = async (item, action) => {
    setBusy(item.id + action);
    try {
      const body = action === "approve" ? { action, ...getEdit(item) } : { action };
      const { data } = await api.post(`/society/ai/review-queue/${item.id}`, body, cfg);
      toast.success(action === "approve" ? `Ticket ${data.ticket_number} created` : "Rejected as false positive");
      reload();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(null); }
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="Human Review Queue" subtitle="HITL · Low Confidence" />
      {loading ? <Loader2 className="h-6 w-6 animate-spin text-zinc-400" /> : (items || []).length === 0 ? (
        <div className="rounded-lg border border-dashed p-12 text-center text-sm text-zinc-400"><ClipboardCheck className="mx-auto mb-3 h-8 w-8 text-zinc-300" />Queue is clear — no low-confidence messages pending review.</div>
      ) : (
        <div className="space-y-4">
          {items.map((item) => {
            const ed = getEdit(item);
            const conf = (item.confidence * 100).toFixed(0);
            return (
              <div key={item.id} data-testid={`review-item-${item.id}`} className="rounded-lg border border-amber-200 bg-card p-5">
                <div className="mb-3 flex items-center justify-between">
                  <span className="flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700"><AlertTriangle className="h-3.5 w-3.5" />Confidence {conf}%</span>
                  <span className="font-mono text-xs text-zinc-400">{item.phone}</span>
                </div>
                <p className="mb-4 rounded-md bg-secondary p-3 text-sm italic text-zinc-600">"{item.text}"</p>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <div><Label className="text-xs">Category</Label>
                    <Select value={ed.category} onValueChange={(v) => setEdit(item.id, { category: v })}>
                      <SelectTrigger data-testid={`review-cat-${item.id}`} className="mt-1"><SelectValue placeholder="Select" /></SelectTrigger>
                      <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div><Label className="text-xs">Flat</Label><Input className="mt-1" value={ed.flat} onChange={(e) => setEdit(item.id, { flat: e.target.value })} /></div>
                  <div><Label className="text-xs">Tower</Label><Input className="mt-1" value={ed.tower} onChange={(e) => setEdit(item.id, { tower: e.target.value })} /></div>
                  <div><Label className="text-xs">Priority</Label>
                    <Select value={ed.priority} onValueChange={(v) => setEdit(item.id, { priority: v })}>
                      <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                      <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="mt-3"><Label className="text-xs">Description</Label><Input className="mt-1" value={ed.description} onChange={(e) => setEdit(item.id, { description: e.target.value })} /></div>
                <div className="mt-4 flex gap-2">
                  <Button data-testid={`approve-review-${item.id}`} size="sm" disabled={busy || !ed.category} onClick={() => decide(item, "approve")}>
                    {busy === item.id + "approve" ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : <Check className="mr-1 h-3.5 w-3.5" />}Approve & Create
                  </Button>
                  <Button data-testid={`reject-review-${item.id}`} size="sm" variant="outline" disabled={busy} onClick={() => decide(item, "reject")}>
                    <X className="mr-1 h-3.5 w-3.5" />Reject
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
