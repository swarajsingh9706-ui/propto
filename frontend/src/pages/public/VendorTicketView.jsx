import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { API, apiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";
import { toast } from "sonner";
import { Loader2, Wrench, CheckCircle2, Phone, Lock } from "lucide-react";

const client = axios.create({ baseURL: API });
const STATUS_COLORS = {
  Open: "bg-blue-100 text-blue-700 border-blue-200",
  Pending: "bg-amber-100 text-amber-700 border-amber-200",
  Resolved: "bg-emerald-100 text-emerald-700 border-emerald-200",
  Cancelled: "bg-zinc-200 text-zinc-600 border-zinc-300",
};
const fmt = (iso) => (iso ? new Date(iso).toLocaleString() : "");

function Row({ label, value, testid }) {
  if (!value) return null;
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-100 py-2.5 last:border-0">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</span>
      <span className="text-right text-sm font-medium text-slate-800" data-testid={testid}>{value}</span>
    </div>
  );
}

function ResolveBox({ token, locked, onDone }) {
  const [otp, setOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const submit = async () => {
    setBusy(true); setErr("");
    try {
      await client.post(`/public/vendor/${token}/resolve`, { otp });
      toast.success("Ticket resolved");
      onDone();
    } catch (e) { setErr(apiError(e)); setOtp(""); onDone(true); }
    finally { setBusy(false); }
  };
  if (locked)
    return <p className="mt-6 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700" data-testid="vendor-otp-locked"><Lock className="h-4 w-4" />Too many wrong OTP attempts. Please contact the society manager.</p>;
  return (
    <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4" data-testid="vendor-resolve-box">
      <p className="text-sm font-semibold text-slate-800">Resolve this ticket</p>
      <p className="mt-1 text-xs text-slate-500">Ask the resident for the 6-digit OTP they received on WhatsApp after the work is done.</p>
      <div className="mt-3 flex justify-center">
        <InputOTP maxLength={6} value={otp} onChange={setOtp} data-testid="vendor-otp-input">
          <InputOTPGroup>{[0, 1, 2, 3, 4, 5].map((i) => <InputOTPSlot key={i} index={i} />)}</InputOTPGroup>
        </InputOTP>
      </div>
      {err && <p className="mt-2 text-center text-xs font-medium text-red-600" data-testid="vendor-otp-error">{err}</p>}
      <Button className="mt-3 w-full bg-emerald-600 hover:bg-emerald-700" disabled={busy || otp.length !== 6} onClick={submit} data-testid="vendor-resolve-btn">
        {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}Verify OTP &amp; Resolve
      </Button>
    </div>
  );
}

function Footer({ t, token, reload }) {
  if (t.can_resolve) return <ResolveBox token={token} locked={t.otp_locked} onDone={reload} />;
  if (t.status === "Resolved") return <p className="mt-6 text-center text-sm font-semibold text-emerald-600" data-testid="vendor-resolved-note">This ticket has been resolved. Thank you!</p>;
  if (!t.vendor_accepted && ["Open", "Pending"].includes(t.status))
    return <p className="mt-6 text-center text-xs text-slate-500" data-testid="vendor-accept-note">Accept the job on WhatsApp to enable resolving here.</p>;
  return <p className="mt-6 text-center text-xs text-slate-400">This ticket is {t.status?.toLowerCase()} — no actions available.</p>;
}

export default function VendorTicketView() {
  const { token } = useParams();
  const [t, setT] = useState(null);
  const load = (keep) => {
    client.get(`/public/vendor/${token}`).then(({ data }) => setT(data)).catch(() => { if (!keep) setT(false); });
  };
  useEffect(() => { load(); }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  if (t === null) return <div className="flex min-h-screen items-center justify-center bg-slate-50"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
  if (t === false)
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6" data-testid="vendor-ticket-invalid">
        <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <h1 className="font-cabinet text-xl font-bold text-slate-900">Job not found</h1>
          <p className="mt-2 text-sm text-slate-500">This job link is invalid or no longer assigned to you.</p>
        </div>
      </div>
    );

  return (
    <div className="flex min-h-screen items-start justify-center bg-gradient-to-b from-slate-50 to-slate-100 p-4 py-8">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-md sm:p-7" data-testid="vendor-ticket-card">
        <img src="/propto-logo.png" alt="Propto" className="mx-auto h-12 w-auto object-contain" />
        <div className="mt-5 flex items-center justify-center gap-2 text-slate-500">
          <Wrench className="h-4 w-4" />
          <span className="font-mono text-sm font-semibold text-slate-700" data-testid="vendor-ticket-number">{t.ticket_number}</span>
        </div>
        <p className="mt-1 text-center text-xs text-slate-400">{t.society_name} · Vendor view</p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          <Badge data-testid="vendor-ticket-status" variant="outline" className={STATUS_COLORS[t.status] || ""}>{t.status}</Badge>
          {t.priority && <Badge variant="outline">{t.priority}</Badge>}
          {t.vendor_accepted && <Badge variant="outline" className="bg-emerald-50 text-emerald-700">Accepted</Badge>}
        </div>
        <p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700" data-testid="vendor-ticket-complaint">{t.raw_message || t.description}</p>
        <div className="mt-4">
          <Row label="Category" value={t.sub_category ? `${t.category} · ${t.sub_category}` : t.category} />
          <Row label="Issue" value={t.issue_line} />
          <Row label="Target SLA" value={t.sla_target} />
          <Row label="Flat" value={[t.tower, t.flat].filter(Boolean).join(" ")} testid="vendor-ticket-flat" />
          <Row label="Location" value={t.location} />
          <Row label="Resident" value={t.resident_name} testid="vendor-ticket-resident" />
          <Row label="Phone" value={t.resident_phone && <a href={`tel:+${t.resident_phone}`} className="inline-flex items-center gap-1 text-brand"><Phone className="h-3 w-3" />{t.resident_phone}</a>} />
          <Row label="Reported" value={fmt(t.created_at)} />
          {!t.vendor_accepted && <Row label="Respond by" value={fmt(t.response_due_at)} />}
          <Row label="Assigned to" value={t.vendor_name} />
        </div>
        <Footer t={t} token={token} reload={load} />
      </div>
    </div>
  );
}
