import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { apiError } from "@/lib/api";
import { PageHeader } from "@/components/Layout";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Loader2, KeyRound, ArrowLeft } from "lucide-react";

export default function ChangePassword() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [np, setNp] = useState("");
  const [cp, setCp] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (np.length < 6) { toast.error("Password must be at least 6 characters"); return; }
    if (np !== cp) { toast.error("New password and confirmation do not match"); return; }
    setSaving(true);
    try {
      await api.post("/auth/change-password", { new_password: np, confirm_password: cp });
      toast.success("Password updated successfully");
      navigate(-1);
    } catch (err) { toast.error(apiError(err)); }
    finally { setSaving(false); }
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8">
      <PageHeader title="Change Password" subtitle="Account Security" description="Update the password for your account" />
      <button data-testid="cp-back" onClick={() => navigate(-1)} className="mb-4 flex items-center gap-1.5 text-xs font-semibold text-brand hover:underline">
        <ArrowLeft className="h-3.5 w-3.5" /> Back
      </button>
      <form onSubmit={submit} className="max-w-md space-y-4 rounded-xl border border-border bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
        <div>
          <Label className="text-xs">Email</Label>
          <Input data-testid="cp-email" value={user?.email || ""} disabled readOnly className="mt-1 cursor-not-allowed bg-slate-100 text-slate-600" />
        </div>
        <div>
          <Label className="text-xs">New password</Label>
          <Input data-testid="cp-new-password" type="password" value={np} onChange={(e) => setNp(e.target.value)} className="mt-1" placeholder="Enter new password" autoComplete="new-password" />
        </div>
        <div>
          <Label className="text-xs">Confirm new password</Label>
          <Input data-testid="cp-confirm-password" type="password" value={cp} onChange={(e) => setCp(e.target.value)} className="mt-1" placeholder="Re-enter new password" autoComplete="new-password" />
        </div>
        <Button data-testid="cp-submit" type="submit" disabled={saving} className="w-full">
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}
          Update Password
        </Button>
      </form>
    </div>
  );
}
