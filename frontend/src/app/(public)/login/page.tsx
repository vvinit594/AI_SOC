"use client";

import { FormEvent, Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { loginAccount } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted-foreground">Loading…</p>}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/";
  const expired = searchParams.get("reason") === "expired";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(
    expired ? "Your session expired. Log in again." : null,
  );
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await loginAccount({ email, password });
      router.replace(nextPath.startsWith("/") ? nextPath : "/");
      router.refresh();
    } catch (caught) {
      setPending(false);
      setError(caught instanceof ApiError ? caught.message : "Unable to log in");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-heading text-2xl font-semibold">Log in</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Use the email and password for your private workspace.
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
        <div className="space-y-1.5">
          <label htmlFor="password" className="text-sm font-medium">
            Password
          </label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Button type="submit" className="w-full" disabled={pending}>
          {pending ? "Signing in…" : "Log in"}
        </Button>
      </form>
      <p className="text-sm text-muted-foreground">
        No account?{" "}
        <Link href="/register" className="text-primary hover:underline">
          Create one
        </Link>
        {" · "}
        <Link href="/forgot-password" className="text-primary hover:underline">
          Forgot password
        </Link>
      </p>
    </div>
  );
}
