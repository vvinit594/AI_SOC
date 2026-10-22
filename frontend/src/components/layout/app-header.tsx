"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";

import { BackendStatus } from "@/components/layout/backend-status";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { pageTitle } from "@/components/layout/nav-config";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

export function AppHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border/80 bg-background/85 px-4 backdrop-blur-md">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger
          render={
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden"
              aria-label="Open navigation"
            />
          }
        >
          <Menu />
          <span className="sr-only">Open navigation</span>
        </SheetTrigger>
        <SheetContent side="left" className="w-72 p-0" showCloseButton>
          <SheetHeader className="sr-only">
            <SheetTitle>Navigation</SheetTitle>
          </SheetHeader>
          <AppSidebar onNavigate={() => setOpen(false)} />
        </SheetContent>
      </Sheet>
      <div className="min-w-0 flex-1">
        <h1 className="truncate font-heading text-sm font-medium">{pageTitle(pathname)}</h1>
        <p className="hidden text-xs text-muted-foreground sm:block">
          Agentic threat investigation — incident records are still mock data
        </p>
      </div>
      <Badge variant="outline" className="hidden sm:inline-flex">
        Mock data
      </Badge>
      <BackendStatus />
    </header>
  );
}
