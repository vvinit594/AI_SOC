import Link from "next/link";
import { Shield } from "lucide-react";
import type { ReactNode } from "react";

import { APP_NAME } from "@/lib/constants";

export default function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-svh bg-background">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <Link href="/welcome" className="flex items-center gap-2 text-sm font-medium">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <Shield className="size-4" aria-hidden="true" />
          </span>
          {APP_NAME}
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/login" className="text-muted-foreground hover:text-foreground">
            Log in
          </Link>
          <Link href="/register" className="text-primary hover:underline">
            Create account
          </Link>
        </nav>
      </header>
      <main id="main-content" className="mx-auto w-full max-w-lg px-4 py-12">
        {children}
      </main>
    </div>
  );
}
