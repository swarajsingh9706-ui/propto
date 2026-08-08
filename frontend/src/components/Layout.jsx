import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Ticket, Users, Wrench, Bot, ClipboardCheck,
  MessageSquare, BarChart3, Building2, LogOut, ChevronLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const SUPER_NAV = [
  { to: "/super/societies", label: "Societies", icon: Building2 },
  { to: "/super/reports", label: "Analytics", icon: BarChart3 },
];
const SOCIETY_NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/tickets", label: "Tickets", icon: Ticket },
  { to: "/vendors", label: "Vendors", icon: Wrench },
  { to: "/residents", label: "Residents", icon: Users },
  { to: "/ai-activity", label: "AI Activity", icon: Bot },
  { to: "/review-queue", label: "Review Queue", icon: ClipboardCheck },
  { to: "/whatsapp", label: "WhatsApp", icon: MessageSquare },
  { to: "/reports", label: "Reports", icon: BarChart3 },
];

export default function Layout({ children }) {
  const { user, logout, scopeSociety, scopeInto } = useAuth();
  const navigate = useNavigate();
  const isSuper = user?.role === "super_admin";
  const scoped = isSuper && scopeSociety;
  const nav = isSuper && !scoped ? SUPER_NAV : SOCIETY_NAV;

  const exitScope = () => {
    scopeInto(null);
    navigate("/super/societies");
  };

  return (
    <div className="flex min-h-screen">
      <aside className="fixed left-0 top-0 z-20 flex h-screen w-60 flex-col border-r border-border bg-card">
        <div className="border-b border-border px-6 py-5">
          <img src="/propto-logo.png" alt="Propto" className="mx-auto h-20 w-auto object-contain" />
          <p className="mt-1 text-center text-[10px] uppercase tracking-[0.25em] text-brand-gold">
            {isSuper ? "Control Tower" : "Society Portal"}
          </p>
        </div>

        {scoped && (
          <button
            data-testid="exit-scope-btn"
            onClick={exitScope}
            className="mx-4 mt-4 flex items-center gap-1.5 rounded-md border border-border bg-secondary px-3 py-2 text-xs font-medium text-brand hover:bg-accent"
          >
            <ChevronLeft className="h-3.5 w-3.5" /> All Societies
          </button>
        )}

        <nav className="flex-1 space-y-1 px-3 py-4">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              data-testid={`nav-${item.label.toLowerCase().replace(/\s/g, "-")}`}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? "bg-brand-green text-white" : "text-zinc-600 hover:bg-secondary"
                }`
              }
            >
              <item.icon className="h-4 w-4" strokeWidth={1.75} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-border p-4">
          <div className="mb-3">
            <p className="truncate text-sm font-medium text-zinc-900">{user?.name}</p>
            <p className="truncate text-xs text-zinc-400">{user?.email}</p>
            <span className="mt-1 inline-block rounded-full bg-accent px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-brand">
              {isSuper ? "Super Admin" : "Society Admin"}
            </span>
          </div>
          <Button data-testid="logout-btn" variant="outline" size="sm" className="w-full justify-start gap-2" onClick={logout}>
            <LogOut className="h-4 w-4" /> Sign out
          </Button>
        </div>
      </aside>

      <main className="ml-60 flex-1 bg-background">{children}</main>
    </div>
  );
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="overline mb-1">{subtitle}</p>
        <h1 className="font-cabinet text-3xl font-bold tracking-tight text-brand">{title}</h1>
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}
