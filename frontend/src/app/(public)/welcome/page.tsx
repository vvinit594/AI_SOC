import Link from "next/link";
import type { Metadata } from "next";

import { buttonVariants } from "@/components/ui/button";
import { APP_NAME } from "@/lib/constants";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Welcome",
};

export default function WelcomePage() {
  return (
    <div className="space-y-6">
      <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Public access</p>
      <h1 className="font-heading text-3xl font-semibold tracking-tight">
        Investigate threats in a private SOC workspace
      </h1>
      <p className="text-sm leading-6 text-muted-foreground">
        {APP_NAME} ingests security events, detects incidents, and recommends simulated response
        actions. Create an account to get a private workspace. Historical demo data is not shared
        with new accounts.
      </p>
      <div className="flex flex-wrap gap-3">
        <Link href="/register" className={cn(buttonVariants())}>
          Create account
        </Link>
        <Link href="/login" className={cn(buttonVariants({ variant: "outline" }))}>
          Log in
        </Link>
      </div>
    </div>
  );
}
