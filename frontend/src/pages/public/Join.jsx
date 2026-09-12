import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { API, apiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, CheckCircle2, Building2 } from "lucide-react";

const client = axios.create({ baseURL: API });
const empty = { name: "", phone: "", flat: "", tower: "", status: "Owner" };

export default function Join() {
  const { token } = useParams();
  const [society, setSociety] = useState(null); // null=loading, false=invalid, object=ok
  const [form, setForm] = useState(empty);
  const [saving, setSaving] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    client.get(`/public/join/${token}`)
      .then(({ data }) => setSociety(data))
      .catch(() => setSociety(false));
  }, [token]);

  const submit = async () => {
    setSaving(true);
    try {
      await client.post(`/public/join/${token}`, form);
      setDone(true);
    } catch (e) { toast.error(apiError(e)); }
    finally { setSaving(false); }
  };

  if (society === null)
    return <div className="flex min-h-screen items-center justify-center bg-slate-50"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;

  if (society === false)
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6" data-testid="join-invalid">
        <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <h1 className="font-cabinet text-xl font-bold text-slate-900">Link not found</h1>
          <p className="mt-2 text-sm text-slate-500">This registration link is invalid or has expired. Please ask your society admin for a new link.</p>
        </div>
      </div>
    );

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-slate-50 to-slate-100 p-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-md sm:p-8" data-testid="join-form-card">
        <img src="/propto-logo.png" alt="Propto" className="mx-auto h-16 w-auto object-contain" />
        {done ? (
          <div className="mt-6 text-center" data-testid="join-success">
            <CheckCircle2 className="mx-auto h-14 w-14 text-emerald-500" />
            <h1 className="mt-4 font-cabinet text-xl font-bold text-slate-900">Details submitted!</h1>
            <p className="mt-2 text-sm text-slate-500">
              Thanks for registering with <span className="font-semibold text-slate-700">{society.society_name}</span>.
              Your details are with the society admin for approval. Once approved you'll receive a WhatsApp group invite on the number you provided.
            </p>
          </div>
        ) : (
          <>
            <div className="mt-5 flex items-center justify-center gap-2 text-slate-500">
              <Building2 className="h-4 w-4" />
              <span className="text-sm font-medium">{society.society_name}{society.city ? `, ${society.city}` : ""}</span>
            </div>
            <h1 className="mt-3 text-center font-cabinet text-lg font-bold text-slate-900">Resident Registration</h1>
            <p className="mt-1 text-center text-xs text-slate-400">Fill in your details to join your society on Propto.</p>

            <div className="mt-6 grid grid-cols-2 gap-3">
              <div className="col-span-2"><Label className="text-xs">Full Name</Label><Input data-testid="join-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="mt-1" /></div>
              <div className="col-span-2"><Label className="text-xs">Phone (with country code)</Label><Input data-testid="join-phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="918111111101" className="mt-1" /></div>
              <div><Label className="text-xs">Flat</Label><Input data-testid="join-flat" value={form.flat} onChange={(e) => setForm({ ...form, flat: e.target.value })} placeholder="B302" className="mt-1" /></div>
              <div>
                <Label className="text-xs">Tower</Label>
                {society.towers?.length ? (
                  <Select value={form.tower} onValueChange={(v) => setForm({ ...form, tower: v })}>
                    <SelectTrigger data-testid="join-tower-select" className="mt-1"><SelectValue placeholder="Select" /></SelectTrigger>
                    <SelectContent>{society.towers.map((t) => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                  </Select>
                ) : (
                  <Input data-testid="join-tower" value={form.tower} onChange={(e) => setForm({ ...form, tower: e.target.value })} placeholder="B" className="mt-1" />
                )}
              </div>
              <div className="col-span-2">
                <Label className="text-xs">I am a</Label>
                <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                  <SelectTrigger data-testid="join-status-select" className="mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Owner">Owner</SelectItem>
                    <SelectItem value="Tenant">Tenant</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Button data-testid="join-submit" className="mt-6 w-full" onClick={submit} disabled={saving || !form.name || !form.phone || !form.flat}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Submit my details
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
