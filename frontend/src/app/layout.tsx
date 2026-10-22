import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { APP_NAME } from "@/lib/constants";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: `${APP_NAME} — Security Operations Center`,
    template: `%s · ${APP_NAME}`,
  },
  description:
    "Agentic AI platform for ingesting security events, investigating incidents, and recommending a human-approved response.",
};

function ShellFallback() {
  return (
    <div className="flex min-h-full">
      <div className="hidden w-64 border-r border-border bg-sidebar lg:block" />
      <div className="flex-1">
        <div className="h-14 border-b border-border" />
        <div className="p-6 text-sm text-muted-foreground">Loading workspace…</div>
      </div>
    </div>
  );
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:m-3 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
        >
          Skip to content
        </a>
        <TooltipProvider>
          <Suspense fallback={<ShellFallback />}>
            <AppShell>{children}</AppShell>
          </Suspense>
        </TooltipProvider>
      </body>
    </html>
  );
}
