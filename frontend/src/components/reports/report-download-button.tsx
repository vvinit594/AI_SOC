"use client";

import { useState } from "react";
import { Download } from "lucide-react";

import { Button } from "@/components/ui/button";
import { downloadIncidentReport } from "@/lib/api";
import { analystErrorMessage, shouldBlockInFlight } from "@/lib/analyst-errors";
import { saveBlob } from "@/lib/report";

export function ReportDownloadButton({
  incidentId,
  size = "sm",
}: {
  incidentId: string;
  size?: "sm" | "default";
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  async function handleDownload() {
    if (shouldBlockInFlight(pending)) {
      return;
    }
    setPending(true);
    setError(null);
    setStatus("Generating report…");
    try {
      const report = await downloadIncidentReport(incidentId);
      saveBlob(report.blob, report.filename);
      setStatus(`Downloaded ${report.filename}`);
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") {
        return;
      }
      setStatus(null);
      setError(analystErrorMessage(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid gap-1">
      <Button
        size={size}
        variant="outline"
        onClick={() => void handleDownload()}
        disabled={pending}
        aria-busy={pending}
      >
        <Download data-icon="inline-start" />
        {pending ? "Generating…" : "Download HTML report"}
      </Button>
      {status ? (
        <p className="text-xs text-muted-foreground" aria-live="polite">
          {status}
        </p>
      ) : null}
      {error ? (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
