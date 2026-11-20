"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

type Status = "checking" | "connected" | "disconnected";

export function BackendStatus() {
  const [status, setStatus] = useState<Status>("checking");
  const [label, setLabel] = useState("Checking backend…");

  useEffect(() => {
    let cancelled = false;

    const check = () => {
      getHealth()
        .then((health) => {
          if (cancelled) {
            return;
          }
          setStatus("connected");
          setLabel(`Backend connected · ${health.service} v${health.version}`);
        })
        .catch((error: unknown) => {
          if (cancelled) {
            return;
          }
          if (error instanceof DOMException && error.name === "AbortError") {
            return;
          }
          setStatus("disconnected");
          setLabel("Backend not connected");
        });
    };

    check();
    const timer = window.setInterval(check, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <div
      className="hidden items-center gap-2 rounded-lg border border-border/80 px-2.5 py-1 text-xs sm:flex"
      aria-live="polite"
    >
      <span
        className={cn(
          "size-1.5 rounded-full",
          status === "connected" && "bg-emerald-400",
          status === "disconnected" && "bg-amber-400",
          status === "checking" && "bg-muted-foreground",
        )}
        aria-hidden="true"
      />
      <span className="max-w-[16rem] truncate">{label}</span>
    </div>
  );
}
