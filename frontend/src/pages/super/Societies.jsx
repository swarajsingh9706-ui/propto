import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { apiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { StatusBadge } from "@/components/Badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import { Plus, Building2, ArrowRight, Loader2, Power } from "lucide-react";

const empty = { name: "", code: "", address: "", city: "", towers: "", admin_name: "", admin_email: "", admin_password: "" };

export default function Societies() {
  const { scopeInto } = useAuth();
  const navigate = useNavigate();
  const [societies, setSocieties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/super/societies");
      setSocieties(data);
    } catch (e) { toast.error(apiError(e)); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    setSaving(true);
    try {
      await api.post("/super/societies", {
        ...form,
        towers: form.towers.split(",").map((t) => t.trim()).filter(Boolean),
        admin_email: form.admin_email || null,
        admin_password: form.admin_password || null,
      });
      toast.success("Society created");
      setOpen(false); setForm(empty); load();
    } catch (e) { toast.error(apiError(e)); }
    finally { setSaving(false); }
  };

  const toggle = async (s) => {
    try {
      await api.put(`/super/societies/${s.id}`, { active: !s.active });
      load();
    } catch (e) { toast.error(apiError(e)); }
  };

  const manage = (s) => { scopeInto(s.id); navigate("/dashboard"); };

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="Society Management" subtitle="Super Admin">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="add-society-btn"><Plus className="mr-1.5 h-4 w-4" /> Add Society</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle className="font-cabinet">New Society</DialogTitle></DialogHeader>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Name" span><Input data-testid="society-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
              <Field label="Code"><Input data-testid="society-code-input" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="GRNVLY" /></Field>
              <Field label="City"><Input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} /></Field>
              <Field label="Address" span><Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} /></Field>
              <Field label="Towers (comma sep)" span><Input value={form.towers} onChange={(e) => setForm({ ...form, towers: e.target.value })} placeholder="A, B, C" /></Field>
              <div className="col-span-2 mt-1 border-t border-dashed pt-3"><p className="overline">Society Admin login (optional)</p></div>
              <Field label="Admin Name"><Input value={form.admin_name} onChange={(e) => setForm({ ...form, admin_name: e.target.value })} /></Field>
              <Field label="Admin Email"><Input value={form.admin_email} onChange={(e) => setForm({ ...form, admin_email: e.target.value })} /></Field>
              <Field label="Admin Password" span><Input type="text" value={form.admin_password} onChange={(e) => setForm({ ...form, admin_password: e.target.value })} /></Field>
            </div>
            <DialogFooter>
              <Button data-testid="save-society-btn" onClick={create} disabled={saving || !form.name || !form.code}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Create Society
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </PageHeader>

      {loading ? (
        <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
      ) : societies.length === 0 ? (
        <Empty />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {societies.map((s) => (
            <div key={s.id} data-testid={`society-card-${s.code}`} className="card-hover rounded-lg border border-border bg-card p-5">
              <div className="flex items-start justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-secondary">
                  <Building2 className="h-5 w-5 text-zinc-700" strokeWidth={1.75} />
                </div>
                <StatusBadge status={s.active ? "Resolved" : "Escalated"} testid={`society-status-${s.code}`} />
              </div>
              <h3 className="mt-4 font-cabinet text-lg font-bold tracking-tight">{s.name}</h3>
              <p className="text-xs text-zinc-400">{s.code} · {s.city || "—"}</p>
              <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4 text-center">
                <Metric label="Tickets" value={s.ticket_count} />
                <Metric label="Vendors" value={s.vendor_count} />
                <Metric label="Residents" value={s.resident_count} />
              </div>
              <div className="mt-4 flex items-center gap-2">
                <Button data-testid={`manage-society-${s.code}`} size="sm" className="flex-1" onClick={() => manage(s)}>
                  Manage <ArrowRight className="ml-1 h-3.5 w-3.5" />
                </Button>
                <Button data-testid={`toggle-society-${s.code}`} size="sm" variant="outline" onClick={() => toggle(s)}>
                  <Power className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const Field = ({ label, span, children }) => (
  <div className={span ? "col-span-2" : ""}>
    <Label className="text-xs">{label}</Label>
    <div className="mt-1">{children}</div>
  </div>
);
const Metric = ({ label, value }) => (
  <div><p className="font-cabinet text-lg font-bold">{value}</p><p className="text-[10px] uppercase tracking-wider text-zinc-400">{label}</p></div>
);
const Empty = () => (
  <div className="rounded-lg border border-dashed border-border bg-card p-12 text-center">
    <Building2 className="mx-auto h-8 w-8 text-zinc-300" />
    <p className="mt-3 text-sm text-zinc-500">No societies yet. Add your first society to get started.</p>
  </div>
);
