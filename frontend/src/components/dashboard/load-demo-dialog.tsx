"use client";

import { useState } from "react";
import { FlaskConical } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { loadDemoScenario } from "@/lib/api";
import { analystErrorMessage } from "@/lib/analyst-errors";
import { listScenarios } from "@/lib/data";
import type { DemoScenario } from "@/lib/types";

export function LoadDemoDialog({
  triggerLabel = "Load Demo Scenario",
  onLoaded,
}: {
  triggerLabel?: string;
  onLoaded?: () => void;
}) {
  const scenarios = listScenarios();
  const [pending, setPending] = useState<DemoScenario | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);

  async function load(id: DemoScenario) {
    if (pending) {
      return;
    }
    setPending(id);
    setError(null);
    try {
      await loadDemoScenario(id);
      onLoaded?.();
      setOpen(false);
      setPending(null);
    } catch (caught: unknown) {
      setError(analystErrorMessage(caught));
      setPending(null);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" />}>
        <FlaskConical data-icon="inline-start" />
        {triggerLabel}
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Load a built-in demo scenario</DialogTitle>
          <DialogDescription>
            Events are written to PostgreSQL. Detection is not run automatically — use
            Run Detection after ingest if you want incidents created from these events.
          </DialogDescription>
        </DialogHeader>
        {error ? (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        ) : null}
        <ul className="grid gap-2">
          {scenarios.map((scenario) => (
            <li key={scenario.id}>
              <Button
                type="button"
                variant="outline"
                className="h-auto w-full justify-start py-3 text-left whitespace-normal"
                disabled={pending !== null}
                onClick={() => void load(scenario.id)}
              >
                <span className="flex flex-col gap-0.5">
                  <span className="font-medium">
                    Scenario {scenario.id} — {scenario.name}
                  </span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {pending === scenario.id ? "Loading events…" : scenario.blurb}
                  </span>
                </span>
              </Button>
            </li>
          ))}
        </ul>
        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  );
}
