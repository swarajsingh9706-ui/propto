import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { API, apiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { Loader2, Ticket, XCircle, Repeat, UserCog } from "lucide-react";

const client = axios.create({ baseURL: API });

const PRIORITY_COLORS = {
  Critical: "bg-red-100 text-red-700 border-red-200",
  High: "bg-orange-100 text-orange-700 border-orange-200",
  Medium: "bg-amber-100 text-amber-700 border-amber-200",
  Low: "bg-emerald-100 text-emerald-700 border-emerald-200",
};
const STATUS_COLORS = {
  Open: "bg-blue-100 text-blue-700 border-blue-200",
  Pending: "bg-amber-100 text-amber-700 border-amber-200",
  Resolved: "bg-emerald-100 text-emerald-700 border-emerald-200",
  Cancelled: "bg-zinc-200 text-zinc-600 border-zinc-300",
};

function Row({ label, value }) {
  if (!value) return null;
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-100 py-2.5 last:border-0">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</span>
      <span className="text-right text-sm font-medium text-slate-800">{value}</span>
    </div>
  );
}

export default function TicketView() {
  const { token } = useParams();
  const [ticket, setTicket] = useState(null); // null=loading, false=invalid, object=ok
  const [categories, setCategories] = useState([]);
  const [busy, setBusy] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [reassignOpen, setReassignOpen] = useState(false);
  const [managerOpen, setManagerOpen] = useState(false);
  const [cat, setCat] = useState("");

  const load = () => {
    client.get(`/public/ticket/${token}`)
      .then(({ data }) => setTicket(data))
      .catch(() => setTicket(false));
  };

  useEffect(() => {
    load();
    client.get(`/public/ticket/${token}/categories`)
      .then(({ data }) => setCategories(data.categories || []))
      .catch(() => {});
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  const doCancel = async () => {
    setBusy(true);
    try {
      await client.post(`/public/ticket/${token}/cancel`);
      toast.success("Ticket cancelled");
      setCancelOpen(false);
      load();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  const doReassign = async () => {
    if (!cat) { toast.error("Please select a category"); return; }
    setBusy(true);
    try {
      const { data } = await client.post(`/public/ticket/${token}/reassign`, { target: "vendor", category: cat });
      toast.success(`Reassigned to ${data.assigned_to}`);
      setReassignOpen(false);
      setCat("");
      load();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  const doManager = async () => {
    setBusy(true);
    try {
      await client.post(`/public/ticket/${token}/reassign`, { target: "manager" });
      toast.success("Assigned to Society Manager");
      setManagerOpen(false);
      load();
    } catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };

  if (ticket === null)
    return <div className="flex min-h-screen items-center justify-center bg-slate-50"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;

  if (ticket === false)
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6" data-testid="ticket-invalid">
        <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <h1 className="font-cabinet text-xl font-bold text-slate-900">Ticket not found</h1>
          <p className="mt-2 text-sm text-slate-500">This ticket link is invalid or has expired.</p>
        </div>
      </div>
    );

  return (
    <div className="flex min-h-screen items-start justify-center bg-gradient-to-b from-slate-50 to-slate-100 p-4 py-8">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-md sm:p-7" data-testid="ticket-view-card">
        <img src="/propto-logo.png" alt="Propto" className="mx-auto h-12 w-auto object-contain" />

        <div className="mt-5 flex items-center justify-center gap-2 text-slate-500">
          <Ticket className="h-4 w-4" />
          <span className="font-mono text-sm font-semibold text-slate-700" data-testid="ticket-number">{ticket.ticket_number}</span>
        </div>
        {ticket.society_name && <p className="mt-1 text-center text-xs text-slate-400">{ticket.society_name}</p>}

        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          <Badge data-testid="ticket-status" variant="outline" className={STATUS_COLORS[ticket.status] || "bg-slate-100 text-slate-600"}>{ticket.status}</Badge>
          {ticket.priority && <Badge variant="outline" className={PRIORITY_COLORS[ticket.priority] || ""}>{ticket.priority}</Badge>}
        </div>

        <p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700" data-testid="ticket-description">{ticket.description}</p>

        <div className="mt-4">
          <Row label="Category" value={ticket.sub_category ? `${ticket.category} · ${ticket.sub_category}` : ticket.category} />
          <Row label="Flat" value={[ticket.tower, ticket.flat].filter(Boolean).join(" ")} />
          <Row label="Reported by" value={ticket.resident_name} />
          <Row label="Assigned to" value={ticket.assigned_to || "Not assigned yet"} />
        </div>

        {ticket.can_act ? (
          <div className="mt-6 space-y-2.5">
            <Button data-testid="ticket-reassign-btn" variant="outline" className="w-full justify-start" onClick={() => setReassignOpen(true)}>
              <Repeat className="mr-2 h-4 w-4" /> Reassign to a vendor
            </Button>
            <Button data-testid="ticket-manager-btn" variant="outline" className="w-full justify-start" onClick={() => setManagerOpen(true)}>
              <UserCog className="mr-2 h-4 w-4" /> Assign to Society Manager
            </Button>
            <Button data-testid="ticket-cancel-btn" variant="destructive" className="w-full justify-start" onClick={() => setCancelOpen(true)}>
              <XCircle className="mr-2 h-4 w-4" /> Cancel ticket
            </Button>
          </div>
        ) : (
          <p className="mt-6 text-center text-xs text-slate-400">This ticket is {ticket.status.toLowerCase()} — no further actions are available.</p>
        )}
      </div>

      {/* Cancel */}
      <AlertDialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <AlertDialogContent data-testid="ticket-cancel-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Cancel this ticket?</AlertDialogTitle>
            <AlertDialogDescription>Ticket {ticket.ticket_number} will be marked as cancelled and the assigned vendor (if any) will be notified. This can't be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep ticket</AlertDialogCancel>
            <AlertDialogAction data-testid="ticket-cancel-confirm" onClick={(e) => { e.preventDefault(); doCancel(); }} disabled={busy} className="bg-red-600 hover:bg-red-700">
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Yes, cancel
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Reassign to vendor */}
      <AlertDialog open={reassignOpen} onOpenChange={setReassignOpen}>
        <AlertDialogContent data-testid="ticket-reassign-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Reassign ticket</AlertDialogTitle>
            <AlertDialogDescription>Pick a category — the ticket will be assigned to the top-priority available vendor in that category.</AlertDialogDescription>
          </AlertDialogHeader>
          <div className="py-1">
            {categories.length ? (
              <Select value={cat} onValueChange={setCat}>
                <SelectTrigger data-testid="ticket-reassign-category"><SelectValue placeholder="Select category" /></SelectTrigger>
                <SelectContent>{categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
              </Select>
            ) : (
              <p className="text-sm text-slate-500">No vendor categories are configured for this society yet.</p>
            )}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Back</AlertDialogCancel>
            <AlertDialogAction data-testid="ticket-reassign-confirm" onClick={(e) => { e.preventDefault(); doReassign(); }} disabled={busy || !cat}>
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Reassign
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Assign to manager */}
      <AlertDialog open={managerOpen} onOpenChange={setManagerOpen}>
        <AlertDialogContent data-testid="ticket-manager-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>Assign to Society Manager?</AlertDialogTitle>
            <AlertDialogDescription>Ticket {ticket.ticket_number} will be handled in-house by the society manager.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Back</AlertDialogCancel>
            <AlertDialogAction data-testid="ticket-manager-confirm" onClick={(e) => { e.preventDefault(); doManager(); }} disabled={busy}>
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Assign to manager
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
