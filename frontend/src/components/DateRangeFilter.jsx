import { useState } from "react";
import { Input } from "@/components/ui/input";

const iso = (d) => {
  const off = d.getTimezoneOffset();
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10);
};

function presetRange(key) {
  const today = new Date();
  const end = iso(today);
  if (key === "week") {
    const day = (today.getDay() + 6) % 7; // Monday = 0
    const s = new Date(today);
    s.setDate(today.getDate() - day);
    return { start: iso(s), end };
  }
  if (key === "month") {
    return { start: iso(new Date(today.getFullYear(), today.getMonth(), 1)), end };
  }
  if (key === "year") {
    return { start: iso(new Date(today.getFullYear(), 0, 1)), end };
  }
  return { start: "", end: "" };
}

const PRESETS = [
  ["all", "All Time"],
  ["week", "This Week"],
  ["month", "This Month"],
  ["year", "This Year"],
  ["custom", "Custom"],
];

export function DateRangeFilter({ onChange, testidPrefix = "range" }) {
  const [preset, setPreset] = useState("all");
  const [custom, setCustom] = useState({ start: "", end: "" });

  const pick = (key) => {
    setPreset(key);
    if (key === "custom") {
      if (custom.start && custom.end) onChange(custom);
      return;
    }
    onChange(presetRange(key));
  };

  const setC = (patch) => {
    const next = { ...custom, ...patch };
    setCustom(next);
    setPreset("custom");
    if (next.start && next.end) onChange(next);
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {PRESETS.map(([k, l]) => (
        <button
          key={k}
          data-testid={`${testidPrefix}-${k}`}
          onClick={() => pick(k)}
          className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
            preset === k
              ? "border-brand bg-brand text-white"
              : "border-border bg-card text-zinc-600 hover:bg-secondary"
          }`}
        >
          {l}
        </button>
      ))}
      {preset === "custom" && (
        <div className="flex items-center gap-1.5">
          <Input type="date" data-testid={`${testidPrefix}-start`} value={custom.start}
            onChange={(e) => setC({ start: e.target.value })} className="h-8 w-[150px] text-xs" />
          <span className="text-xs text-zinc-400">to</span>
          <Input type="date" data-testid={`${testidPrefix}-end`} value={custom.end}
            onChange={(e) => setC({ end: e.target.value })} className="h-8 w-[150px] text-xs" />
        </div>
      )}
    </div>
  );
}
