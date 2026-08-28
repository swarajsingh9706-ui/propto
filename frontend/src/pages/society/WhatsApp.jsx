import { useState, useEffect } from "react";
import api, { apiError } from "@/lib/api";
import { useScope } from "@/lib/useScope";
import { PageHeader } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, MessageSquare, Send, Wifi, WifiOff, CheckCircle2, XCircle, Bot, RefreshCw } from "lucide-react";

const WHAPI_WEBHOOK = `${process.env.REACT_APP_BACKEND_URL}/api/whapi/webhook`;

const SAMPLES = [
  "Water is leaking heavily from the ceiling in flat B302, please send a plumber",
  "The lift in Tower A is not working since morning, stuck at 3rd floor",
  "No power supply in flat C204 since last night, please check urgently",
  "Good morning everyone! Have a great day",
];

export default function WhatsApp({ societyId = null, embedded = false }) {
  const scopeCfg = useScope();
  const cfg = societyId ? { params: { society_id: societyId } } : scopeCfg;
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const reload = () =>
    api.get("/society/whatsapp/status", cfg).then((r) => setStatus(r.data)).finally(() => setLoading(false));
  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [societyId]);
  const [phone, setPhone] = useState("918111111102");
  const [text, setText] = useState(SAMPLES[0]);
  const [sending, setSending] = useState(false);
  const [feed, setFeed] = useState([]);
  const [groupName, setGroupName] = useState("");
  const [groupId, setGroupId] = useState("");
  const [groups, setGroups] = useState(null);
  const [loadingGroups, setLoadingGroups] = useState(false);
  const [editing, setEditing] = useState(false);
  const [conn, setConn] = useState(null);
  const [testPhone, setTestPhone] = useState("");
  const [testing, setTesting] = useState(false);

  const checkConn = async () => {
    setConn("loading");
    try { const { data } = await api.get("/society/whatsapp/check"); setConn(data); }
    catch (e) { setConn({ ok: false, detail: apiError(e) }); }
  };
  const sendTest = async () => {
    if (!testPhone.trim()) return;
    setTesting(true);
    try { await api.post("/society/whatsapp/test-send", { phone: testPhone.trim() }); toast.success("Test message sent — check WhatsApp"); }
    catch (e) { toast.error(apiError(e)); }
    finally { setTesting(false); }
  };

  const simulate = async () => {
    if (!text.trim()) return;
    setSending(true);
    setFeed((f) => [{ dir: "in", phone, text, at: new Date() }, ...f]);
    try {
      const { data } = await api.post("/society/whatsapp/simulate", { phone, text }, cfg);
      setFeed((f) => [{ dir: "sys", result: data, at: new Date() }, ...f]);
      toast.success(`Pipeline: ${data.status}`);
    } catch (e) { toast.error(apiError(e)); }
    finally { setSending(false); }
  };

  const loadGroups = async () => {
    setLoadingGroups(true);
    try { const { data } = await api.get("/society/whatsapp/groups", cfg); setGroups(data.groups || []); if (!data.groups?.length) toast.info("No groups found for the linked number"); }
    catch (e) { toast.error(apiError(e)); setGroups([]); }
    finally { setLoadingGroups(false); }
  };
  const pickGroup = (id) => {
    setGroupId(id);
    const g = (groups || []).find((x) => x.id === id);
    if (g) setGroupName(g.name);
  };
  const connect = async () => {
    try { await api.post("/society/whatsapp/connect", { group_name: groupName, group_id: groupId }, cfg); toast.success("Group connected"); setEditing(false); reload(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const startEdit = () => {
    setGroupName(status?.group?.group_name || "");
    setGroupId(status?.group?.group_id || "");
    setEditing(true);
    loadGroups();
  };
  const toggleMon = async () => { try { await api.post("/society/whatsapp/toggle-monitoring", {}, cfg); reload(); } catch (e) { toast.error(apiError(e)); } };

  return (
    <div className={embedded ? "" : "p-8"}>
      {!embedded && <PageHeader title="WhatsApp Integration" subtitle="Group & Live Simulator" />}
      {loading || !status ? <Loader2 className="h-6 w-6 animate-spin text-zinc-400" /> : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Group connection */}
          <div className="space-y-4">
            <div className="rounded-lg border border-border bg-card p-5">
              <div className="mb-4 flex items-center justify-between">
                <p className="overline">Society WhatsApp Group</p>
                <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${status.connected ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-zinc-200 bg-zinc-100 text-zinc-500"}`}>
                  {status.connected ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}{status.connected ? "Connected" : "Not connected"}
                </span>
              </div>
              {status.connected && !editing ? (
                <div className="space-y-3">
                  <div className="rounded-md bg-secondary p-3 text-sm">
                    <p className="font-medium">{status.group?.group_name}</p>
                    <p className="font-mono text-xs text-zinc-400">{status.group?.group_id}</p>
                  </div>
                  <label className="flex items-center justify-between rounded-md border border-border p-3 text-sm">
                    <span>Monitoring active</span>
                    <Switch data-testid="toggle-monitoring" checked={status.monitoring} onCheckedChange={toggleMon} />
                  </label>
                  <Button data-testid="change-group-btn" variant="outline" size="sm" onClick={startEdit} className="w-full">Change group</Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {status.whapi_configured && (
                    <div>
                      <div className="flex items-center justify-between">
                        <Label className="text-xs">Pick your WhatsApp group</Label>
                        <button type="button" data-testid="load-groups-btn" onClick={loadGroups} className="flex items-center gap-1 text-[11px] text-brand hover:underline">
                          <RefreshCw className={`h-3 w-3 ${loadingGroups ? "animate-spin" : ""}`} />{groups ? "Refresh" : "Load groups"}
                        </button>
                      </div>
                      {groups && groups.length > 0 && (
                        <Select value={groupId} onValueChange={pickGroup}>
                          <SelectTrigger data-testid="group-select" className="mt-1"><SelectValue placeholder="Select a group" /></SelectTrigger>
                          <SelectContent>
                            {groups.map((g) => <SelectItem key={g.id} value={g.id} data-testid={`group-opt-${g.id}`}>{g.name}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      )}
                      {groups && groups.length === 0 && <p className="mt-1 text-[11px] text-amber-600">No groups found — make sure the linked number is a member of the group, then Refresh. You can also enter the Chat ID manually below.</p>}
                      <p className="mt-1 text-[10px] text-zinc-400">Selecting a group fills the exact Chat ID automatically.</p>
                    </div>
                  )}
                  <div><Label className="text-xs">Group Name</Label><Input data-testid="group-name-input" value={groupName} onChange={(e) => setGroupName(e.target.value)} className="mt-1" /></div>
                  <div><Label className="text-xs">Group Chat ID {status.whapi_configured && <span className="text-zinc-400">(Whapi, ends in @g.us)</span>}</Label><Input data-testid="group-id-input" value={groupId} onChange={(e) => setGroupId(e.target.value)} placeholder="120363xxxxxxxxx@g.us" className="mt-1 font-mono text-xs" /></div>
                  <div className="flex gap-2">
                    <Button data-testid="connect-group-btn" onClick={connect} disabled={!groupName || !groupId} className="flex-1">{status.connected ? "Save group" : "Connect Group"}</Button>
                    {editing && <Button data-testid="cancel-edit-btn" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>}
                  </div>
                </div>
              )}
            </div>

            <div className={`rounded-lg border p-4 text-sm ${status.api_configured ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
              <p className="flex items-center gap-2 font-medium">{status.api_configured ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <XCircle className="h-4 w-4 text-amber-600" />}
                {status.provider === "whapi" ? "Whapi (Group Reader) connected" : status.provider === "meta" ? "WhatsApp Cloud API (Meta) configured" : "No transport configured"}</p>
              <p className="mt-1 text-xs text-zinc-500">
                {status.provider === "whapi"
                  ? "Whapi reads your society GROUP and feeds messages to the AI engine. Point your Whapi channel webhook to the URL below."
                  : status.provider === "meta"
                  ? "1:1 inbound webhook active. Note: Meta Cloud API cannot read WhatsApp groups — add a WHAPI_TOKEN for group monitoring."
                  : "Add WHAPI_TOKEN (group reading) or Meta keys to backend .env. Simulator works regardless."}
              </p>
              {status.whapi_configured && (
                <div className="mt-2 rounded-md bg-white/60 p-2">
                  <p className="text-[10px] uppercase tracking-wider text-zinc-400">Whapi webhook URL</p>
                  <code className="block break-all text-[11px] text-zinc-700">{WHAPI_WEBHOOK}</code>
                </div>
              )}
              {status.api_configured && (
                <div className="mt-3 space-y-2 border-t border-emerald-200/60 pt-3">
                  <div className="flex items-center gap-2">
                    <Button data-testid="check-connection-btn" size="sm" variant="outline" onClick={checkConn} disabled={conn === "loading"}>
                      {conn === "loading" ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Wifi className="mr-1.5 h-3.5 w-3.5" />}Test Connection
                    </Button>
                    {conn && conn !== "loading" && (conn.ok
                      ? <span className="text-xs text-emerald-700">✓ {conn.provider === "whapi" ? `Whapi channel: ${typeof conn.state === "string" ? conn.state : "linked"}` : `${conn.phone?.verified_name} · ${conn.phone?.display_phone_number} (${conn.phone?.quality_rating})`}</span>
                      : <span className="text-xs text-red-600">✗ {typeof conn.detail === "string" ? conn.detail.slice(0, 80) : "failed"}</span>)}
                  </div>
                  <div className="flex items-center gap-2">
                    <Input data-testid="test-phone-input" value={testPhone} onChange={(e) => setTestPhone(e.target.value)} placeholder="Your number e.g. 9199..." className="h-8 flex-1 font-mono text-xs" />
                    <Button data-testid="test-send-btn" size="sm" onClick={sendTest} disabled={testing || !testPhone}>
                      {testing ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <Send className="mr-1.5 h-3.5 w-3.5" />}Send test
                    </Button>
                  </div>
                  <p className="text-[10px] text-zinc-400">{status.provider === "whapi" ? "Sends from your linked Whapi number." : "Recipient must be an added/verified number while your Meta app is in test mode."}</p>
                </div>
              )}
            </div>
          </div>

          {/* Simulator */}
          <div className="rounded-lg border border-border bg-card p-5">
            <p className="overline mb-4 flex items-center gap-2"><MessageSquare className="h-4 w-4" />Live Simulator</p>
            <div className="space-y-3">
              <div><Label className="text-xs">Resident Phone</Label><Input data-testid="sim-phone-input" value={phone} onChange={(e) => setPhone(e.target.value)} className="mt-1 font-mono" /></div>
              <div><Label className="text-xs">Message</Label><Textarea data-testid="sim-text-input" value={text} onChange={(e) => setText(e.target.value)} rows={3} className="mt-1" /></div>
              <div className="flex flex-wrap gap-1.5">
                {SAMPLES.map((s, i) => <button key={i} onClick={() => setText(s)} className="rounded-full border border-border px-2.5 py-1 text-[11px] text-zinc-500 hover:bg-secondary">Sample {i + 1}</button>)}
              </div>
              <Button data-testid="sim-send-btn" onClick={simulate} disabled={sending} className="w-full">{sending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}Send to Group</Button>
            </div>

            <div className="mt-5 max-h-[320px] space-y-2 overflow-y-auto border-t border-border pt-4">
              {feed.length === 0 && <p className="text-center text-xs text-zinc-400">Send a message to watch the AI pipeline react.</p>}
              {feed.map((m, i) => m.dir === "in" ? (
                <div key={i} className="ml-auto max-w-[85%] rounded-lg rounded-tr-none bg-emerald-100 p-2.5 text-sm text-zinc-800">
                  <p className="text-[10px] text-emerald-700">{m.phone}</p>{m.text}
                </div>
              ) : (
                <div key={i} data-testid="sim-result" className="max-w-[90%] rounded-lg border border-border bg-secondary p-2.5 text-xs">
                  <p className="flex items-center gap-1 font-medium text-sky-600"><Bot className="h-3.5 w-3.5" />PROPTO AI · {m.result.status.replace("_", " ")}</p>
                  {m.result.ai && <p className="mt-1 text-zinc-500">{m.result.ai.category} · {m.result.ai.priority} · conf {(m.result.ai.confidence * 100).toFixed(0)}%</p>}
                  {m.result.ticket_number && <p className="mt-0.5 font-mono text-emerald-600">{m.result.ticket_number}</p>}
                  {m.result.reason && <p className="mt-0.5 text-zinc-400">{m.result.reason}</p>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
