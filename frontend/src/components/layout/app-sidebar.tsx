"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Shield } from "lucide-react";

import { isNavActive, NAV_ITEMS } from "@/components/layout/nav-config";
import { Separator } from "@/components/ui/separator";
import { APP_NAME } from "@/lib/constants";
import { cn } from "@/lib/utils";

export function AppSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex items-center gap-2 px-4 py-5">
        <span className="flex size-9 items-center justify-center rounded-lg bg-primary/15 text-primary">
          <Shield className="size-4" aria-hidden="true" />
        </span>
        <div>
          <p className="font-heading text-sm font-semibold tracking-wide">{APP_NAME}</p>
          <p className="text-[11px] text-muted-foreground">Security Operations Center</p>
        </div>
      </div>
      <Separator />
      <nav aria-label="Primary" className="flex flex-1 flex-col gap-1 p-3">
        {NAV_ITEMS.map((item) => {
          const active = isNavActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-muted-foreground hover:bg-sidebar-accent/70 hover:text-sidebar-foreground",
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 text-[11px] leading-relaxed text-muted-foreground">
        Frontend is separate from FastAPI. All secrets stay on the backend.
      </div>
    </div>
  );
}
