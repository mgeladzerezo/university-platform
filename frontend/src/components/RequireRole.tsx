"use client";

import { useTranslations } from "next-intl";

import type { Role } from "@/lib/api/types";
import { hasAnyRole, useAuth } from "@/lib/auth/AuthProvider";

/**
 * Hides portal pages from users without the role. This is a convenience only:
 * the API enforces roles on every request.
 */
export function RequireRole({ allowed, children }: { allowed: Role[]; children: React.ReactNode }) {
  const t = useTranslations();
  const auth = useAuth();

  if (!auth.ready) return <p role="status">{t("common.loading")}</p>;
  if (!auth.authenticated) {
    return (
      <div className="card max-w-md">
        <p className="mb-4">{t("common.loginRequired")}</p>
        <button type="button" className="btn" onClick={auth.login}>
          {t("nav.login")}
        </button>
      </div>
    );
  }
  if (!hasAnyRole(auth.roles, allowed)) return <p role="alert">{t("common.noAccess")}</p>;
  return <>{children}</>;
}
