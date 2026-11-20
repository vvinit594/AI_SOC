"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { startInvestigationApi } from "@/lib/api";
import { analystErrorMessage } from "@/lib/analyst-errors";
import { cn } from "@/lib/utils";

export function StartInvestigationButton({
  incidentId,
  label = "Investigate",
  variant = "outline",
  size = "sm",
  className,
}: {
  incidentId: string;
  label?: string;
  variant?: "outline" | "default";
  size?: "sm" | "default";
  className?: string;
}) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    if (pending) {
      return;
    }
    setPending(true);
    setError(null);
    try {
      const payload = await startInvestigationApi(incidentId);
      router.push(`/investigations/${payload.investigation.id}`);
    } catch (caught: unknown) {
      setError(analystErrorMessage(caught));
      setPending(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-end gap-1">
      <Button
        type="button"
        variant={variant}
        size={size}
        className={cn(className)}
        disabled={pending}
        onClick={() => void onClick()}
      >
        {pending ? "Starting…" : label}
      </Button>
      {error ? (
        <span className="max-w-56 text-right text-xs text-destructive" role="alert">
          {error}
        </span>
      ) : null}
    </span>
  );
}
