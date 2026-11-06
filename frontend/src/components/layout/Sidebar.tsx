import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  PlusCircle,
  Library,
  Settings,
  Info,
  GraduationCap,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { useSettings } from "@/hooks/useApi";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/new", label: "New Lecture", icon: PlusCircle },
  { to: "/lectures", label: "My Lectures", icon: Library },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/about", label: "About", icon: Info },
];

export function Sidebar({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { data: settings } = useSettings();
  const location = useLocation();
  const anyMock =
    settings?.providers?.some((p) => p.mode === "mock") ?? false;

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-zinc-950/30 lg:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-zinc-200 bg-white transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-zinc-200 px-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-white">
              <GraduationCap className="h-5 w-5" />
            </div>
            <span className="text-lg font-semibold tracking-tight text-zinc-900">
              LectureLens
            </span>
          </div>
          <button
            className="rounded p-1 text-zinc-400 hover:text-zinc-600 lg:hidden"
            onClick={onClose}
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 p-3" aria-label="Main">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive || (item.to === "/lectures" && location.pathname.startsWith("/lectures/"))
                    ? "bg-zinc-100 text-zinc-900"
                    : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900",
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-zinc-200 p-4">
          {anyMock && (
            <Badge className="mb-2 border-amber-200 bg-amber-50 text-amber-700">
              Demo mode
            </Badge>
          )}
          <p className="text-xs leading-relaxed text-zinc-500">
            {anyMock
              ? "AI providers are running in explicit mock mode — outputs are clearly flagged."
              : "Real model inference enabled (IndicConformer · Param-1 · IndicTrans2)."}
          </p>
        </div>
      </aside>
    </>
  );
}
