import {
  FileBarChart,
  LayoutDashboard,
  ListTodo,
  ShieldAlert,
  Siren,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/events", label: "Events", icon: ListTodo },
  { href: "/incidents", label: "Incidents", icon: Siren },
  { href: "/response", label: "Response", icon: ShieldAlert },
  { href: "/reports", label: "Reports", icon: FileBarChart },
];

export function isNavActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function pageTitle(pathname: string): string {
  if (pathname.startsWith("/investigations/")) {
    return "Investigation workspace";
  }
  if (pathname.startsWith("/incidents/")) {
    return "Incident detail";
  }
  const match = NAV_ITEMS.find((item) => item.href === pathname);
  if (match?.href === "/") {
    return "SOC Overview";
  }
  return match?.label ?? "AI-SOC";
}
