import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import {
  LayoutDashboard, Ticket, Users, Wrench, Bot, ClipboardCheck,
  MessageSquare, BarChart3, Building2, LogOut, ChevronLeft, Vote, ScrollText,
  Package, AlertTriangle, UsersRound, Workflow, Menu, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const SUPER_NAV = [
  { to: "/super/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/super/societies", label: "Societies", icon: Building2 },
  { to: "/super/whatsapp", label: "WhatsApp", icon: MessageSquare },
  { to: "/super/reports", label: "Analytics", icon: BarChart3 },
];
const SOCIETY_NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/tickets", label: "Tickets", icon: Ticket },
  { to: "/escalated", label: "Escalated", icon: AlertTriangle },
  { to: "/vendors", label: "Vendors", icon: Wrench },
  { to: "/assets", label: "Assets", icon: Package },
  { to: "/residents", label: "Residents", icon: Users },
  { to: "/committee", label: "Committee", icon: UsersRound },
  { to: "/ai-activity", label: "AI Activity", icon: Bot },
  { to: "/review-queue", label: "Review Queue", icon: ClipboardCheck },
  { to: "/assignment-logic", label: "Assignment Logic", icon: Workflow },
  { to: "/suggestions", label: "Suggestions", icon: Vote },
  { to: "/audit", label: "Audit Log", icon: ScrollText },
  { to: "/reports", label: "Reports", icon: BarChart3 },
];

export default function Layout({ children }) {
  const { user, logout, scopeSociety, scopeInto } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const isSuper = user?.role === "super_admin";
  const scoped = isSuper && scopeSociety;
  const nav = isSuper && !scoped ? SUPER_NAV : SOCIETY_NAV;

  const exitScope = () => {
    scopeInto(null);
    navigate("/super/societies");
  };

  return (
    <div className="min-h-screen">
      {open && (
        <div data-testid="sidebar-overlay" onClick={() => setOpen(false)} className="fixed inset-0 z-30 bg-black/40 lg:hidden" />
      )}

      <aside
        className={`fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-border bg-card transition-transform duration-200 lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}
      >
        <div className="relative border-b border-border px-6 py-5">
          <img src="/propto-logo.png" alt="Propto" className="mx-auto h-20 w-auto object-contain" />
          <p className="mt-1 text-center text-[10px] uppercase tracking-[0.25em] text-brand-gold">
            {isSuper ? "Control Tower" : "Society Portal"}
          </p>
          <button data-testid="sidebar-close" onClick={() => setOpen(false)} className="absolute right-3 top-3 rounded-md p-1 text-zinc-400 hover:bg-secondary lg:hidden">
            <X className="h-5 w-5" />
          </button>
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

        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setOpen(false)}
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

      <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-border bg-card px-4 py-2.5 lg:hidden">
        <button data-testid="sidebar-toggle" onClick={() => setOpen(true)} className="rounded-md p-1.5 text-zinc-700 hover:bg-secondary">
          <Menu className="h-5 w-5" />
        </button>
        <img src="/propto-logo.png" alt="Propto" className="h-8 w-auto object-contain" />
      </div>

      <main className="bg-background lg:ml-60">{children}</main>
    </div>
  );
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4 sm:mb-8">
      <div>
        <p className="overline mb-1">{subtitle}</p>
        <h1 className="font-cabinet text-2xl font-bold tracking-tight text-brand sm:text-3xl">{title}</h1>
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}
