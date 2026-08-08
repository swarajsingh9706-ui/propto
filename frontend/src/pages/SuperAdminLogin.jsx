import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { apiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, ShieldCheck, ArrowRight, Terminal } from "lucide-react";

export default function SuperAdminLogin() {
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
      if (u.role !== "super_admin") {
        await logout();
        setError("These are Society Admin credentials. Please use the Society portal.");
        return;
      }
      navigate("/super/societies");
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-6" style={{ background: "#082E1B" }}>
      {/* backdrop grid + gold glow */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.18]"
        style={{ backgroundImage: "linear-gradient(rgba(198,160,44,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(198,160,44,0.5) 1px, transparent 1px)", backgroundSize: "48px 48px" }} />
      <div className="pointer-events-none absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-brand-gold/25 blur-[120px]" />

      <div className="relative z-10 w-full max-w-md">
        <div className="mb-6 flex justify-center">
          <div className="rounded-2xl bg-white/95 px-6 py-4 shadow-lg">
            <img src="/propto-logo.png" alt="Propto" className="h-16 w-auto object-contain" />
          </div>
        </div>

        <div className="rounded-2xl border border-brand-gold/25 bg-white/[0.04] p-8 backdrop-blur-xl">
          <span className="mb-4 inline-flex items-center gap-1.5 rounded-full border border-brand-gold/40 bg-brand-gold/10 px-3 py-1 font-mono text-[11px] uppercase tracking-wider text-brand-goldLight">
            <ShieldCheck className="h-3.5 w-3.5" /> Super Admin Access
          </span>
          <h1 className="mb-1 font-cabinet text-3xl font-bold tracking-tight text-white">Control Tower</h1>
          <p className="mb-7 flex items-center gap-1.5 font-mono text-xs text-emerald-200/60">
            <Terminal className="h-3.5 w-3.5" /> societies · vendors · analytics
          </p>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <Label htmlFor="email" className="text-emerald-100/70">Email</Label>
              <Input id="email" type="email" data-testid="login-email-input"
                value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="superadmin@propto.com"
                className="mt-1.5 border-white/15 bg-black/20 text-white placeholder:text-emerald-200/30 focus-visible:ring-brand-gold" required />
            </div>
            <div>
              <Label htmlFor="password" className="text-emerald-100/70">Password</Label>
              <Input id="password" type="password" data-testid="login-password-input"
                value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="mt-1.5 border-white/15 bg-black/20 text-white placeholder:text-emerald-200/30 focus-visible:ring-brand-gold" required />
            </div>
            {error && <p data-testid="login-error" className="rounded-md border border-red-500/40 bg-red-950/40 px-3 py-2 text-sm text-red-200">{error}</p>}
            <Button data-testid="login-submit-button" type="submit" disabled={loading}
              className="w-full bg-brand-gold text-brand-greenDark hover:bg-brand-goldLight">
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Authenticate
            </Button>
          </form>

          <button data-testid="demo-super-btn" onClick={() => { setEmail("superadmin@propto.com"); setPassword("Propto@123"); }}
            className="mt-6 block w-full rounded-lg border border-dashed border-white/15 bg-black/20 p-3 text-left font-mono text-[11px] text-emerald-100/60 hover:border-brand-gold/40 hover:text-emerald-100">
            <span className="text-brand-goldLight">// demo</span><br />→ superadmin@propto.com
          </button>
        </div>

        <Link to="/login" data-testid="goto-society-portal"
          className="mt-6 flex items-center justify-center gap-1.5 text-xs font-medium text-emerald-200/50 hover:text-emerald-100">
          <ArrowRight className="h-3 w-3 rotate-180" /> Society Admin? Sign in here
        </Link>
      </div>
    </div>
  );
}
