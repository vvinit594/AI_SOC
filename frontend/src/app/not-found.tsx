import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-lg py-16 text-center">
      <p className="text-sm font-medium text-primary">404</p>
      <h2 className="mt-2 font-heading text-2xl font-semibold">Page not found</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        That route is not part of the SOC workspace. Return to the overview or open the
        incident list.
      </p>
      <div className="mt-6 flex justify-center gap-2">
        <Link href="/" className={cn(buttonVariants())}>
          Overview
        </Link>
        <Link href="/incidents" className={cn(buttonVariants({ variant: "outline" }))}>
          Incidents
        </Link>
      </div>
    </div>
  );
}
