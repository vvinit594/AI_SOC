"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

import { getCurrentUser, type CurrentUser } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getCurrentUser(controller.signal)
      .then((current) => {
        setUser(current);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") {
          return;
        }
        if (caught instanceof ApiError && (caught.status === 401 || caught.code === "unauthenticated")) {
          const next = encodeURIComponent(pathname || "/");
          router.replace(`/login?reason=expired&next=${next}`);
          return;
        }
        setError(caught instanceof Error ? caught.message : "Unable to verify the session");
      });
    return () => controller.abort();
  }, [pathname, router]);

  if (error) {
    return (
      <div className="flex min-h-svh items-center justify-center p-6 text-sm text-destructive">
        {error}
      </div>
    );
  }

  if (user === null) {
    return (
      <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">
        Checking session…
      </div>
    );
  }

  return <>{children}</>;
}
