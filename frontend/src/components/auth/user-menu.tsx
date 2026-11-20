"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { logoutAccount } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export function UserMenu({ name, email }: { name: string; email: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onLogout() {
    setPending(true);
    setError(null);
    try {
      await logoutAccount();
      router.replace("/login");
      router.refresh();
    } catch (caught) {
      setPending(false);
      setError(caught instanceof ApiError ? caught.message : "Unable to log out");
    }
  }

  return (
    <div className="space-y-2">
      <p className="truncate text-xs font-medium text-sidebar-foreground">{name}</p>
      <p className="truncate text-[11px] text-muted-foreground">{email}</p>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="w-full"
        disabled={pending}
        onClick={() => {
          void onLogout();
        }}
      >
        {pending ? "Signing out…" : "Log out"}
      </Button>
      {error ? <p className="text-[11px] text-destructive">{error}</p> : null}
    </div>
  );
}
