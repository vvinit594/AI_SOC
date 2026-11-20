"use client";

import { useEffect, useState } from "react";

import { UserMenu } from "@/components/auth/user-menu";
import { getCurrentUser, type CurrentUser } from "@/lib/auth";

export function SessionUser() {
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getCurrentUser(controller.signal)
      .then(setUser)
      .catch(() => setUser(null));
    return () => controller.abort();
  }, []);

  if (user === null) {
    return null;
  }

  return <UserMenu name={user.full_name} email={user.email} />;
}
