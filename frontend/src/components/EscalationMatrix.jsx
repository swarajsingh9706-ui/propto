import { useEffect, useState } from "react";
import api, { apiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, Plus, Pencil, Trash2, Phone, Bell, CalendarClock, Clock, AlertTriangle, Flame, MessageCircle } from "lucide-react";

const CARD = {
  blue: { bg: "#eff6ff", border: "#bfdbfe", pillBg: "#dbeafe", pillText: "#2563eb", icon: "#2563eb", iconBg: "#dbeafe", rail: "#2563eb" },
  amber: { bg: "#fffbeb", border: "#fde68a", pillBg: "#fef3c7", pillText: "#d97706", icon: "#d97706", iconBg: "#fef3c7", rail: "#d97706" },
  red: { bg: "#fef2f2", border: "#fecaca", pillBg: "#fee2e2", pillText: "#dc2626", icon: "#dc2626", iconBg: "#fee2e2", rail: "#dc2626" },
  purple: { bg: "#f5f3ff", border: "#ddd6fe", pillBg: "#ede9fe", pillText: "#7c3aed", icon: "#7c3aed", iconBg: "#ede9fe", rail: "#7c3aed" },
};
const RULE_ICON = { pre: CalendarClock, final: Clock, overdue: AlertTriangle, critical: Flame };
const ROLE_COLOR = { Secretary: "#2563eb", Vendor: "#0d9488", Chairman: "#7c3aed", Manager: "#d97706", "Society Manager": "#ea580c", Member: "#64748b" };
const COLORS = ["blue", "amber", "red", "purple"];
const ALL_ROLES = ["Secretary", "Vendor", "Chairman", "Manager"];
const CONTACT_ROLES = ["Secretary", "Chairman", "Society Manager", "Manager", "Member", "Vendor"];

const initials = (n) => (n || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

function NotifyChip({ role }) {
  const c = ROLE_COLOR[role] || "#64748b";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border bg-white px-2.5 py-1 text-[11px] font-semibold" style={{ borderColor: c + "55", color: c }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: c }} /> {role}
    </span>
  );
}

export default function EscalationMatrix({ cfg }) {
  const [timeline, setTimeline] = useState(null);
  const [committee, setCommittee] = useState([]);
  const [rule, setRule] = useState(null);     // editing rule { index, ...fields }
  const [contact, setContact] = useState(null); // { id?, name, role, phone, email, tower }
  const [saving, setSaving] = useState(false);

  const loadCommittee = () => api.get("/society/committee", cfg).then((r) => setCommittee(r.data)).catch(() => {});
  useEffect(() => {
    api.get("/society/escalation-timeline", cfg).then((r) => setTimeline(r.data.timeline)).catch((e) => toast.error(apiError(e)));
    loadCommittee();
    // eslint-disable-next-line
  }, []);

  const saveRule = async () => {
    setSaving(true);
    const next = timeline.map((r, i) => (i === rule.index ? {
      ...r, timing: rule.timing, title: rule.title, description: rule.description,
      notify: rule.notify, offset_days: Number(rule.offset_days) || 0, direction: rule.direction,
    } : r));
    try {
      await api.put("/society/escalation-timeline", { timeline: next }, cfg);
      setTimeline(next); setRule(null); toast.success("Rule updated");
    } catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };

  const saveContact = async () => {
    setSaving(true);
    const body = { name: contact.name, role: contact.role, phone: contact.phone, email: contact.email, tower: contact.tower };
    try {
      if (contact.id) await api.put(`/society/committee/${contact.id}`, body, cfg);
      else await api.post("/society/committee", body, cfg);
      toast.success(contact.id ? "Contact updated" : "Contact added");
      setContact(null); loadCommittee();
    } catch (e) { toast.error(apiError(e)); } finally { setSaving(false); }
  };

  const delContact = async (c) => {
    try { await api.delete(`/society/committee/${c.id}`); loadCommittee(); toast.success("Contact removed"); }
    catch (e) { toast.error(apiError(e)); }
  };

  const toggleNotify = (role) => setRule((s) => ({ ...s, notify: s.notify.includes(role) ? s.notify.filter((r) => r !== role) : [...s.notify, role] }));

  if (timeline === null) return <div className="flex justify-center p-10"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div>;

  return (
    <div data-testid="escalation-matrix-section">
      {/* Legend */}
      <div className="mb-4 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-xl border border-border bg-white px-4 py-3 text-[12px] shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
        <span className="font-extrabold uppercase tracking-wide text-slate-400">Legend</span>
        <span className="font-semibold text-slate-500">Health →</span>
        {[["Healthy", "#16a34a"], ["Warning", "#d97706"], ["Critical", "#dc2626"]].map(([t, c]) => (
          <span key={t} className="inline-flex items-center gap-1.5 font-semibold" style={{ color: c }}><span className="h-2 w-2 rounded-full" style={{ background: c }} />{t}</span>
        ))}
        <span className="ml-2 font-semibold text-slate-500">Service Status →</span>
        {[["Scheduled", "#2563eb"], ["Due Soon", "#d97706"], ["Overdue", "#dc2626"]].map(([t, c]) => (
          <span key={t} className="inline-flex items-center gap-1.5 font-semibold" style={{ color: c }}><span className="h-2 w-2 rounded-full" style={{ background: c }} />{t}</span>
        ))}
      </div>

      {/* Header */}
      <div className="mb-4 flex items-center justify-between rounded-xl border border-border bg-white px-5 py-4 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
        <div className="flex items-center gap-2.5">
          <Bell className="h-5 w-5 text-amber-500" />
          <div>
            <div className="text-[15px] font-extrabold text-slate-900">Escalation Matrix</div>
            <div className="text-[12px] text-slate-500">Automated WhatsApp alerts based on service due dates. Click the pencil on any rule to customise timing and recipients.</div>
          </div>
        </div>
        <Button data-testid="add-contact-btn" onClick={() => setContact({ name: "", role: "Member", phone: "", email: "", tower: "" })}><Plus className="mr-1.5 h-4 w-4" />Add Contact</Button>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.4fr_1fr]">
        {/* Notification timeline */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-slate-400">Notification Timeline</span>
            <span className="text-[11px] text-slate-400">Click the pencil to edit any rule</span>
          </div>
          <div className="space-y-3">
            {timeline.map((r, i) => {
              const col = CARD[r.color] || CARD.blue;
              const Icon = RULE_ICON[r.key] || Bell;
              return (
                <div key={i} className="flex gap-3" data-testid={`timeline-rule-${i}`}>
                  <div className="flex flex-col items-center pt-1">
                    <span className="flex h-8 w-8 items-center justify-center rounded-full border-2 bg-white" style={{ borderColor: col.rail }}>
                      <Icon className="h-4 w-4" style={{ color: col.icon }} />
                    </span>
                    {i < timeline.length - 1 && <span className="mt-1 w-px flex-1" style={{ background: col.rail + "55" }} />}
                  </div>
                  <div className="relative flex-1 rounded-xl border p-4" style={{ background: col.bg, borderColor: col.border }}>
                    <button data-testid={`timeline-edit-${i}`} onClick={() => setRule({ index: i, ...r })}
                      className="absolute right-3 top-3 flex h-7 w-7 items-center justify-center rounded-md border bg-white/70 text-slate-500 hover:bg-white" style={{ borderColor: col.border }}>
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <span className="inline-block rounded-md px-2.5 py-1 text-[11px] font-extrabold" style={{ background: col.pillBg, color: col.pillText }}>{r.timing}</span>
                    <div className="mt-2 text-[14px] font-bold text-slate-900">{r.title}</div>
                    <div className="mt-0.5 text-[12px] text-slate-600">{r.description}</div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className="text-[11px] font-semibold text-slate-400">Notify:</span>
                      {r.notify.map((n) => <NotifyChip key={n} role={n} />)}
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400"><MessageCircle className="h-3.5 w-3.5" />{r.channel}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Committee contacts */}
        <div>
          <div className="mb-3 text-[11px] font-extrabold uppercase tracking-wider text-slate-400">Committee Contacts</div>
          <div className="space-y-2.5">
            {committee.length === 0 && <div className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-slate-400">No contacts yet. Add one to receive alerts.</div>}
            {committee.map((c) => {
              const col = ROLE_COLOR[c.role] || "#64748b";
              return (
                <div key={c.id} data-testid={`contact-row-${c.id}`} className="flex items-center gap-3 rounded-xl border border-border bg-white px-4 py-3 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 text-[13px] font-bold" style={{ borderColor: col + "55", color: col, background: col + "14" }}>{initials(c.name)}</span>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[14px] font-bold text-slate-900">{c.name}</div>
                    <div className="mt-0.5 flex items-center gap-2 text-[12px]">
                      <span className="font-semibold" style={{ color: col }}>{c.role}</span>
                      {c.phone && <span className="inline-flex items-center gap-1 text-slate-500"><Phone className="h-3 w-3 text-rose-400" />{c.phone}</span>}
                    </div>
                  </div>
                  <button data-testid={`contact-edit-${c.id}`} onClick={() => setContact({ id: c.id, name: c.name || "", role: c.role || "Member", phone: c.phone || "", email: c.email || "", tower: c.tower || "" })}
                    className="flex h-8 w-8 items-center justify-center rounded-md bg-orange-50 text-orange-500 hover:bg-orange-100"><Pencil className="h-3.5 w-3.5" /></button>
                  <button data-testid={`contact-delete-${c.id}`} onClick={() => delContact(c)}
                    className="flex h-8 w-8 items-center justify-center rounded-md bg-red-50 text-red-400 hover:bg-red-100"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              );
            })}
          </div>
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-[12px] text-amber-800">
            <span className="font-bold">💡 How it works:</span> WhatsApp messages are auto-sent to the contacts above when a rule triggers. Click the pencil on any timeline rule to change when reminders go out and who receives them.
          </div>
        </div>
      </div>

      {/* Edit rule dialog */}
      <Dialog open={!!rule} onOpenChange={(o) => !o && setRule(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle className="font-cabinet">Edit Rule</DialogTitle></DialogHeader>
          {rule && (
            <div className="space-y-3">
              <div><Label className="text-xs">Timing label</Label><Input data-testid="rule-timing-input" value={rule.timing} onChange={(e) => setRule({ ...rule, timing: e.target.value })} className="mt-1" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs">Days offset</Label><Input data-testid="rule-offset-input" type="number" min="0" value={rule.offset_days} onChange={(e) => setRule({ ...rule, offset_days: e.target.value })} className="mt-1" /></div>
                <div><Label className="text-xs">Relative to due date</Label>
                  <Select value={rule.direction} onValueChange={(v) => setRule({ ...rule, direction: v })}><SelectTrigger data-testid="rule-direction-select" className="mt-1"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="before">Before</SelectItem><SelectItem value="after">After</SelectItem></SelectContent></Select>
                </div>
              </div>
              <div><Label className="text-xs">Title</Label><Input data-testid="rule-title-input" value={rule.title} onChange={(e) => setRule({ ...rule, title: e.target.value })} className="mt-1" /></div>
              <div><Label className="text-xs">Description</Label><Textarea data-testid="rule-desc-input" value={rule.description} onChange={(e) => setRule({ ...rule, description: e.target.value })} rows={2} className="mt-1" /></div>
              <div>
                <Label className="text-xs">Notify</Label>
                <div className="mt-1.5 flex flex-wrap gap-2">
                  {ALL_ROLES.map((role) => {
                    const on = rule.notify.includes(role);
                    const c = ROLE_COLOR[role];
                    return (
                      <button key={role} type="button" data-testid={`rule-notify-${role.toLowerCase()}`} onClick={() => toggleNotify(role)}
                        className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-semibold transition-colors"
                        style={on ? { background: c + "18", borderColor: c, color: c } : { background: "#fff", borderColor: "#e2e8f0", color: "#94a3b8" }}>
                        <span className="h-1.5 w-1.5 rounded-full" style={{ background: on ? c : "#cbd5e1" }} />{role}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
          <DialogFooter><Button data-testid="save-rule-btn" onClick={saveRule} disabled={saving}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Save Rule</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add / edit contact dialog */}
      <Dialog open={!!contact} onOpenChange={(o) => !o && setContact(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle className="font-cabinet">{contact?.id ? "Edit Contact" : "Add Contact"}</DialogTitle></DialogHeader>
          {contact && (
            <div className="space-y-3">
              <div><Label className="text-xs">Name</Label><Input data-testid="contact-name-input" value={contact.name} onChange={(e) => setContact({ ...contact, name: e.target.value })} className="mt-1" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs">Role</Label>
                  <Select value={contact.role} onValueChange={(v) => setContact({ ...contact, role: v })}><SelectTrigger data-testid="contact-role-select" className="mt-1"><SelectValue /></SelectTrigger><SelectContent>{CONTACT_ROLES.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent></Select>
                </div>
                <div><Label className="text-xs">Tower</Label><Input data-testid="contact-tower-input" value={contact.tower} onChange={(e) => setContact({ ...contact, tower: e.target.value })} className="mt-1" /></div>
              </div>
              <div><Label className="text-xs">Phone</Label><Input data-testid="contact-phone-input" value={contact.phone} onChange={(e) => setContact({ ...contact, phone: e.target.value })} className="mt-1" placeholder="98980 00001" /></div>
              <div><Label className="text-xs">Email</Label><Input data-testid="contact-email-input" value={contact.email} onChange={(e) => setContact({ ...contact, email: e.target.value })} className="mt-1" /></div>
            </div>
          )}
          <DialogFooter><Button data-testid="save-contact-btn" onClick={saveContact} disabled={saving || !contact?.name}>{saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{contact?.id ? "Save Changes" : "Add Contact"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
