"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { requestPasswordRecovery } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<string | null>(null);
  const [devToken, setDevToken] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    setDetail(null);
    setDevToken(null);
    try {
      const result = await requestPasswordRecovery(email);
      setDetail(result.detail);
      setDevToken(result.dev_recovery_token ?? null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Unable to start recovery");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-heading text-2xl font-semibold">Password recovery</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Recovery never pretends that an email was sent. Production requires a configured mail
          provider.
        </p>
      </div>
      <form className="space-y-4" onSubmit={onSubmit}>
        <div className="space-y-1.5">
          <label htmlFor="email" className="text-sm font-medium">
            Email
          </label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {detail ? <p className="text-sm text-muted-foreground">{detail}</p> : null}
        {devToken ? (
          <p className="break-all text-xs text-muted-foreground">
            Development token:{" "}
            <Link
              href={`/reset-password?token=${encodeURIComponent(devToken)}`}
              className="text-primary hover:underline"
            >
              continue to reset
            </Link>
          </p>
        ) : null}
        <Button type="submit" className="w-full" disabled={pending}>
          {pending ? "Checking…" : "Continue"}
        </Button>
      </form>
      <Link href="/login" className="text-sm text-primary hover:underline">
        Back to login
      </Link>
    </div>
  );
}
