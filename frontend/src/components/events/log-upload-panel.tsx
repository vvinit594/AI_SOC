"use client";

import { useId, useRef, useState } from "react";
import Link from "next/link";
import { FileUp, Upload, X } from "lucide-react";

import { LoadDemoDialog } from "@/components/dashboard/load-demo-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ApiError,
  detectIncidents,
  uploadLogs,
  IngestApiError,
  type DetectIncidentsApi,
  type LogUploadApi,
} from "@/lib/api";
import { analystErrorMessage, shouldBlockInFlight } from "@/lib/analyst-errors";
import { isAbortError } from "@/lib/analyst-proxy";
import { formatFileSize, MAX_UPLOAD_BYTES, validateUploadFile } from "@/lib/ingest";
import { cn } from "@/lib/utils";

export function LogUploadPanel({ onIngested }: { onIngested: () => Promise<void> | void }) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [clientError, setClientError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [detecting, setDetecting] = useState(false);
  const [uploadResult, setUploadResult] = useState<LogUploadApi | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [recordErrors, setRecordErrors] = useState<{ index: number; detail: string }[]>([]);
  const [detectResult, setDetectResult] = useState<DetectIncidentsApi | null>(null);
  const [detectError, setDetectError] = useState<string | null>(null);

  function selectFile(next: File | null) {
    setClientError(null);
    setUploadError(null);
    setRecordErrors([]);
    setUploadResult(null);
    setDetectResult(null);
    setDetectError(null);
    if (next) {
      const invalid = validateUploadFile(next);
      if (invalid) {
        setClientError(invalid.message);
        setFile(null);
        return;
      }
    }
    setFile(next);
  }

  function clearFile() {
    selectFile(null);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  async function submitUpload() {
    if (!file || shouldBlockInFlight(uploading)) {
      return;
    }
    const invalid = validateUploadFile(file);
    if (invalid) {
      setClientError(invalid.message);
      return;
    }
    setUploading(true);
    setClientError(null);
    setUploadError(null);
    setRecordErrors([]);
    setUploadResult(null);
    setDetectResult(null);
    setDetectError(null);
    try {
      const result = await uploadLogs(file);
      setUploadResult(result);
      setRecordErrors(result.errors);
      await onIngested();
    } catch (caught: unknown) {
      if (isAbortError(caught)) {
        return;
      }
      if (caught instanceof IngestApiError) {
        setUploadError(caught.message);
        setRecordErrors(caught.errors);
      } else {
        setUploadError(analystErrorMessage(caught));
      }
    } finally {
      setUploading(false);
    }
  }

  async function runDetection() {
    if (shouldBlockInFlight(detecting)) {
      return;
    }
    setDetecting(true);
    setDetectError(null);
    setDetectResult(null);
    try {
      const result = await detectIncidents();
      setDetectResult(result);
    } catch (caught: unknown) {
      if (isAbortError(caught)) {
        return;
      }
      setDetectError(
        caught instanceof ApiError ? analystErrorMessage(caught) : analystErrorMessage(caught),
      );
    } finally {
      setDetecting(false);
    }
  }

  const canUpload = file !== null && !uploading;
  const ingested = uploadResult !== null && uploadResult.accepted > 0;
  const partial = ingested && uploadResult.rejected > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Upload className="size-4" aria-hidden="true" />
          Log ingest
        </CardTitle>
        <CardDescription>
          Upload JSON or CSV to <code className="font-mono text-xs">POST /api/logs/upload</code>.
          Detection runs only when you click Run Detection.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <div
          className={cn(
            "flex min-h-28 flex-col items-center justify-center rounded-lg border border-dashed px-4 py-6 text-center transition-colors",
            dragOver ? "border-primary bg-primary/5" : "border-border",
            uploading ? "opacity-70" : "",
          )}
          onDragOver={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragOver(false);
            const dropped = event.dataTransfer.files[0];
            if (dropped) {
              selectFile(dropped);
            }
          }}
        >
          <FileUp className="mb-2 size-5 text-muted-foreground" aria-hidden="true" />
          <p className="text-sm">Drag and drop a JSON or CSV file here</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Maximum {formatFileSize(MAX_UPLOAD_BYTES)} · backend MAX_UPLOAD_SIZE_MB
          </p>
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept=".json,.csv,application/json,text/csv"
            className="sr-only"
            disabled={uploading}
            onChange={(event) => {
              selectFile(event.target.files?.[0] ?? null);
            }}
          />
          <Button
            type="button"
            variant="outline"
            className="mt-3"
            disabled={uploading}
            onClick={() => inputRef.current?.click()}
          >
            Browse files
          </Button>
        </div>

        {file ? (
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{file.name}</p>
              <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={uploading}
              onClick={clearFile}
              aria-label="Remove selected file"
            >
              <X className="size-4" />
              Remove
            </Button>
          </div>
        ) : null}

        {clientError ? (
          <p className="text-sm text-destructive" role="alert">
            {clientError}
          </p>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" disabled={!canUpload} onClick={() => void submitUpload()}>
            {uploading ? "Uploading…" : "Upload"}
          </Button>
          {uploadError || clientError ? (
            <Button
              type="button"
              variant="outline"
              disabled={!file || uploading}
              onClick={() => void submitUpload()}
            >
              Retry upload
            </Button>
          ) : null}
          <LoadDemoDialog triggerLabel="Load built-in scenario" onLoaded={() => void onIngested()} />
        </div>

        {uploading ? (
          <p className="text-sm text-muted-foreground" aria-busy="true">
            Uploading {file?.name}. Waiting for the backend to confirm…
          </p>
        ) : null}

        {uploadError ? (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2" role="alert">
            <p className="text-sm text-destructive">{uploadError}</p>
          </div>
        ) : null}

        {uploadResult ? (
          <div
            className="rounded-lg border border-border bg-muted/30 px-3 py-2"
            role="status"
          >
            <p className="text-sm">
              Backend accepted {uploadResult.accepted} event
              {uploadResult.accepted === 1 ? "" : "s"}
              {uploadResult.rejected > 0
                ? ` and rejected ${uploadResult.rejected}.`
                : "."}
            </p>
            {partial ? (
              <p className="mt-1 text-xs text-muted-foreground">
                Partial ingestion: valid rows were persisted. Invalid rows were not.
              </p>
            ) : null}
          </div>
        ) : null}

        {recordErrors.length > 0 ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2">
            <p className="mb-2 text-sm font-medium">Rejected records</p>
            <ul className="grid gap-1 text-sm">
              {recordErrors.map((error) => (
                <li key={`${error.index}-${error.detail}`}>
                  Index {error.index}: {error.detail}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
          <Button
            type="button"
            variant="outline"
            disabled={detecting}
            onClick={() => void runDetection()}
          >
            {detecting ? "Running detection…" : "Run Detection"}
          </Button>
          {detectError ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={detecting}
              onClick={() => void runDetection()}
            >
              Retry detection
            </Button>
          ) : null}
          <p className="text-xs text-muted-foreground">
            Calls <code className="font-mono">POST /api/incidents/detect</code>. Not run on upload.
          </p>
        </div>

        {detectError ? (
          <p className="text-sm text-destructive" role="alert">
            {detectError}
          </p>
        ) : null}

        {detectResult ? (
          <div className="grid gap-2 rounded-lg border border-border px-3 py-2" role="status">
            <p className="text-sm">
              Detection created {detectResult.created}, updated {detectResult.updated}, skipped{" "}
              {detectResult.skipped}.
            </p>
            {detectResult.incidents.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No incidents were returned. Rules did not create or update a row.
              </p>
            ) : (
              <ul className="grid gap-1 text-sm">
                {detectResult.incidents.map((incident) => (
                  <li key={incident.id} className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{incident.severity}</Badge>
                    <Link
                      href={`/incidents/${incident.id}`}
                      className="font-medium text-primary hover:underline"
                    >
                      {incident.title}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
            {detectResult.matches.length > 0 ? (
              <ul className="mt-1 grid gap-1 text-xs text-muted-foreground">
                {detectResult.matches.map((match) => (
                  <li key={`${match.incident_id}-${match.rule_id}-${match.timestamp}`}>
                    {match.rule_id}: {match.reason}
                  </li>
                ))}
              </ul>
            ) : null}
            {detectResult.incidents.length > 0 ? (
              <Link href="/incidents" className="text-sm text-primary hover:underline">
                Open incidents
              </Link>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
