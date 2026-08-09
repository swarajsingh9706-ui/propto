import { useState } from "react";
import api, { apiError } from "@/lib/api";
import { useScope, useFetch } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { StatCard } from "@/components/StatCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Loader2, Vote, ThumbsUp, ThumbsDown, MessageSquare, CheckCircle2, User, Trash2 } from "lucide-react";

const CATEGORIES = ["Infrastructure", "Security", "Maintenance", "Community", "Amenities", "Water Supply", "Parking", "General"];
const STATUSES = ["Under Review", "Approved", "Pending", "Declined"];
const STATUS_CLS = {
  "Under Review": "bg-amber-50 text-amber-700 border-amber-200",
  "Approved": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Pending": "bg-zinc-100 text-zinc-600 border-zinc-200",
  "Declined": "bg-red-50 text-red-700 border-red-200",
};

const empty = { title: "", category: "Infrastructure", author_name: "", flat: "" };

export default function Suggestions() {
  const cfg = useScope();
  const { data, loading, reload } = useFetch("/society/suggestions");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState("All");

  const create = async () => {
    setSaving(true);
    try {
      const { data: res } = await api.post("/society/suggestions", form, cfg);
      toast.success(res.poll_posted ? "Suggestion added & poll posted to WhatsApp group" : "Suggestion added (group poll not sent — connect group / check Whapi plan)");
      setOpen(false); setForm(empty); reload();
    } catch (e) { toast.error(apiError(e)); }
    finally { setSaving(false); }
  };
  const setStatus = async (s, status) => {
    try { await api.put(`/society/suggestions/${s.id}`, { status }); reload(); toast.success(`Marked ${status}`); }
    catch (e) { toast.error(apiError(e)); }
  };
  const castVote = async (s, vote) => {
    try { await api.post(`/society/suggestions/${s.id}/vote`, { vote }, cfg); reload(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const del = async (s) => {
    try { await api.delete(`/society/suggestions/${s.id}`); reload(); toast.success("Removed"); }
    catch (e) { toast.error(apiError(e)); }
  };

  if (loading || !data) return <div className="flex h-96 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-zinc-400" /></div>;

  const { suggestions, stats } = data;
  const counts = {
    All: suggestions.length,
    "Under Review": stats.under_review, Approved: stats.approved,
    Pending: stats.pending, Declined: stats.declined,
  };
  const list = filter === "All" ? suggestions : suggestions.filter((s) => s.status === filter);

  return (
    <div className="p-8">
      <PageHeader title="Resident Suggestions" subtitle="Community Voting">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="add-suggestion-btn"><Plus className="mr-1.5 h-4 w-4" /> Add Suggestion</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-cabinet">New Suggestion</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label className="text-xs">Suggestion</Label><Input data-testid="suggestion-title-input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Install a borewell of our own" className="mt-1" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs">Category</Label>
                  <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                    <SelectTrigger data-testid="suggestion-category" className="mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div><Label className="text-xs">Flat</Label><Input value={form.flat} onChange={(e) => setForm({ ...form, flat: e.target.value })} placeholder="B-1204" className="mt-1" /></div>
              </div>
              <div><Label className="text-xs">Raised by</Label><Input value={form.author_name} onChange={(e) => setForm({ ...form, author_name: e.target.value })} placeholder="Resident name" className="mt-1" /></div>
              <p className="flex items-center gap-1.5 rounded-md bg-brand-green/[0.06] px-3 py-2 text-xs text-brand"><MessageSquare className="h-3.5 w-3.5" /> A Yes/No poll will be posted to the society WhatsApp group.</p>
            </div>
            <DialogFooter><Button data-testid="save-suggestion-btn" onClick={create} disabled={saving || !form.title}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Add & Post Poll</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </PageHeader>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard testid="sg-total" label="Total Suggestions" value={stats.total} icon={Vote} />
        <StatCard testid="sg-review" label="Under Review" value={stats.under_review} icon={MessageSquare} accent="text-amber-600" />
        <StatCard testid="sg-approved" label="Approved" value={stats.approved} icon={CheckCircle2} accent="text-emerald-600" />
        <StatCard testid="sg-votes" label="Total Votes" value={stats.total_votes} icon={ThumbsUp} accent="text-brand" />
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {["All", ...STATUSES].map((f) => (
          <button key={f} data-testid={`filter-${f.replace(/\s/g, "-").toLowerCase()}`} onClick={() => setFilter(f)}
            className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors ${filter === f ? "border-brand-green bg-brand-green text-white" : "border-border bg-card text-zinc-600 hover:bg-secondary"}`}>
            {f} ({counts[f] ?? 0})
          </button>
        ))}
      </div>

      <div className="mt-4 space-y-4">
        {list.length === 0 ? (
          <div className="rounded-lg border border-dashed p-12 text-center text-sm text-zinc-400"><Vote className="mx-auto mb-3 h-8 w-8 text-zinc-300" />No suggestions in this view.</div>
        ) : list.map((s) => {
          const total = (s.yes_votes || 0) + (s.no_votes || 0);
          const yesPct = total ? Math.round((s.yes_votes / total) * 100) : 0;
          const noPct = total ? 100 - yesPct : 0;
          return (
            <div key={s.id} data-testid={`suggestion-${s.id}`} className="rounded-lg border border-border bg-card p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="font-cabinet text-lg font-bold tracking-tight text-zinc-900">{s.title}</h3>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                    <span className="flex items-center gap-1"><User className="h-3 w-3" />{s.author_name}</span>
                    {s.flat && <><span>·</span><span>{s.flat}</span></>}
                    <span>·</span>
                    <span className="rounded-full bg-brand-green/[0.08] px-2 py-0.5 font-medium text-brand">{s.category}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${STATUS_CLS[s.status]}`}>{s.status}</span>
                  <Select value={s.status} onValueChange={(v) => setStatus(s, v)}>
                    <SelectTrigger data-testid={`status-${s.id}`} className="h-8 w-36 text-xs"><SelectValue /></SelectTrigger>
                    <SelectContent>{STATUSES.map((st) => <SelectItem key={st} value={st}>{st}</SelectItem>)}</SelectContent>
                  </Select>
                  <button data-testid={`delete-suggestion-${s.id}`} onClick={() => del(s)} className="text-zinc-300 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
                </div>
              </div>

              <div className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-red-100">
                <div className="h-full bg-emerald-500" style={{ width: `${yesPct}%` }} />
                <div className="h-full bg-red-400" style={{ width: `${noPct}%` }} />
              </div>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-4 text-sm">
                  <span className="font-medium text-emerald-600">✓ Yes {s.yes_votes} ({yesPct}%)</span>
                  <span className="font-medium text-red-500">✗ No {s.no_votes} ({noPct}%)</span>
                  <span className="text-xs text-zinc-400">{total} total votes</span>
                </div>
                <div className="flex items-center gap-2">
                  <Button data-testid={`vote-yes-${s.id}`} size="sm" variant="outline" onClick={() => castVote(s, "yes")}><ThumbsUp className="mr-1.5 h-3.5 w-3.5 text-emerald-600" />Yes ({s.yes_votes})</Button>
                  <Button data-testid={`vote-no-${s.id}`} size="sm" variant="outline" onClick={() => castVote(s, "no")}><ThumbsDown className="mr-1.5 h-3.5 w-3.5 text-red-500" />No ({s.no_votes})</Button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
