import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { apiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Building2, Loader2, ArrowRight, Shield } from "lucide-react";

const HERO = "https://images.pexels.com/photos/18153132/pexels-photo-18153132.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";

export default function SocietyLogin() {
  const { login, logout } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const u = await login(email, password);
      if (u.role !== "society_admin") {
        await logout();
        setError("These are Super Admin credentials. Please use the Control Tower portal.");
        return;
      }
      navigate("/dashboard");
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <div className="flex w-full flex-col justify-center px-8 md:w-1/2 md:px-16 lg:px-24">
        <div className="mx-auto w-full max-w-sm">
          <img src="/propto-logo.png" alt="Propto" className="mb-6 h-16 w-auto object-contain" />

          <span className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-brand-green/20 bg-brand-green/5 px-3 py-1 text-xs font-medium text-brand">
            <Building2 className="h-3.5 w-3.5" /> Society Admin
          </span>
          <h1 className="mb-2 font-cabinet text-4xl font-bold tracking-tight text-brand">
            Manage your society
          </h1>
          <p className="mb-8 text-sm text-zinc-500">Sign in to handle complaints, tickets, vendors and residents.</p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" data-testid="login-email-input"
                value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@yoursociety.com" className="mt-1.5" required />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" data-testid="login-password-input"
                value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••" className="mt-1.5" required />
            </div>
            {error && <p data-testid="login-error" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
            <Button data-testid="login-submit-button" type="submit" disabled={loading} className="w-full">
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Sign in
            </Button>
          </form>

          <button data-testid="demo-society-btn" onClick={() => { setEmail("admin@greenvalley.com"); setPassword("Admin@123"); }}
            className="mt-6 block w-full rounded-lg border border-dashed border-brand-green/25 bg-brand-green/[0.04] p-3 text-left text-xs text-zinc-600 hover:bg-brand-green/[0.08]">
            <span className="overline text-brand">Demo</span><br />→ admin@greenvalley.com
          </button>

          <Link to="/admin/login" data-testid="goto-super-portal"
            className="mt-6 flex items-center gap-1.5 text-xs font-medium text-zinc-400 hover:text-brand">
            <Shield className="h-3.5 w-3.5" /> Super Admin? Go to Control Tower <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </div>

      <div className="relative hidden w-1/2 md:block">
        <img src={HERO} alt="Modern residential society" className="h-full w-full object-cover" />
        <div className="absolute inset-0 bg-brand-green/55" />
        <div className="absolute bottom-12 left-12 right-12 text-white">
          <div className="mb-4 h-1 w-16 rounded-full bg-brand-gold" />
          <p className="font-cabinet text-3xl font-bold leading-tight tracking-tight">
            Every complaint, handled — before it becomes a crisis.
          </p>
          <p className="mt-3 max-w-md text-sm text-white/80">
            Residents raise issues on WhatsApp. Propto detects, tickets, and routes them to the right vendor automatically.
          </p>
        </div>
      </div>
    </div>
  );
}
