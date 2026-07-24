import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { apiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Building2, Loader2 } from "lucide-react";

const HERO = "https://images.pexels.com/photos/18153132/pexels-photo-18153132.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";

export default function Login() {
  const { login } = useAuth();
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
      navigate(u.role === "super_admin" ? "/super/societies" : "/dashboard");
    } catch (err) {
      setError(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  const quick = (em, pw) => { setEmail(em); setPassword(pw); };

  return (
    <div className="flex min-h-screen">
      <div className="flex w-full flex-col justify-center px-8 md:w-1/2 md:px-16 lg:px-24">
        <div className="mx-auto w-full max-w-sm">
          <div className="mb-10 flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-zinc-900">
              <span className="font-cabinet text-base font-black text-white">P</span>
            </div>
            <div>
              <p className="font-cabinet text-xl font-bold leading-none tracking-tight">PROPTO</p>
              <p className="text-[10px] uppercase tracking-[0.2em] text-zinc-400">Complaint OS</p>
            </div>
          </div>

          <p className="overline mb-2">Welcome back</p>
          <h1 className="mb-8 font-cabinet text-4xl font-bold tracking-tight text-zinc-900">
            Sign in to your console
          </h1>

          <form onSubmit={submit} className="space-y-4">
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email" type="email" data-testid="login-email-input"
                value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="you@society.com" className="mt-1.5" required
              />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password" type="password" data-testid="login-password-input"
                value={password} onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••" className="mt-1.5" required
              />
            </div>
            {error && (
              <p data-testid="login-error" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
            )}
            <Button data-testid="login-submit-button" type="submit" disabled={loading} className="w-full">
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sign in
            </Button>
          </form>

          <div className="mt-8 space-y-2 rounded-lg border border-dashed border-border bg-secondary/50 p-4">
            <p className="overline">Demo accounts</p>
            <button data-testid="demo-super-btn" onClick={() => quick("superadmin@propto.com", "Propto@123")}
              className="block text-left text-xs text-zinc-600 hover:text-zinc-900">
              → Super Admin · superadmin@propto.com
            </button>
            <button data-testid="demo-society-btn" onClick={() => quick("admin@greenvalley.com", "Admin@123")}
              className="block text-left text-xs text-zinc-600 hover:text-zinc-900">
              → Society Admin · admin@greenvalley.com
            </button>
          </div>
        </div>
      </div>

      <div className="relative hidden w-1/2 md:block">
        <img src={HERO} alt="Modern residential society" className="h-full w-full object-cover" />
        <div className="absolute inset-0 bg-zinc-900/30" />
        <div className="absolute bottom-12 left-12 right-12 text-white">
          <p className="font-cabinet text-3xl font-bold leading-tight tracking-tight">
            AI-powered complaint management for modern societies.
          </p>
          <p className="mt-3 max-w-md text-sm text-white/80">
            Residents raise maintenance issues on WhatsApp. PROPTO detects, tickets, and routes them — automatically.
          </p>
        </div>
      </div>
    </div>
  );
}
