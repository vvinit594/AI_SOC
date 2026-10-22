"use client";

import Link from "next/link";
import { FlaskConical } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { listScenarios } from "@/lib/data";
import { cn } from "@/lib/utils";

export function LoadDemoDialog({
  triggerLabel = "Load Demo Scenario",
}: {
  triggerLabel?: string;
}) {
  const scenarios = listScenarios();

  return (
    <Dialog>
      <DialogTrigger render={<Button variant="outline" />}>
        <FlaskConical data-icon="inline-start" />
        {triggerLabel}
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Load a built-in demo scenario</DialogTitle>
          <DialogDescription>
            Phase 2 uses mock data only. Selecting a scenario opens the matching
            incident. File upload and detection run against PostgreSQL in Phase 5.
          </DialogDescription>
        </DialogHeader>
        <ul className="grid gap-2">
          {scenarios.map((scenario) => (
            <li key={scenario.id}>
              <Link
                href={`/incidents/${scenario.incidentId}`}
                className={cn(
                  buttonVariants({ variant: "outline" }),
                  "h-auto w-full justify-start py-3 text-left whitespace-normal",
                )}
              >
                <span className="flex flex-col gap-0.5">
                  <span className="font-medium">
                    Scenario {scenario.id} — {scenario.name}
                  </span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {scenario.blurb}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
        <DialogFooter showCloseButton />
      </DialogContent>
    </Dialog>
  );
}
