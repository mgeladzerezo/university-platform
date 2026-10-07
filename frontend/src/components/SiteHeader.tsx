"use client";

import { useLocale, useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import type { Role } from "@/lib/api/types";
import { hasAnyRole, useAuth } from "@/lib/auth/AuthProvider";

const PUBLIC_LINKS = [
  { href: "/faculties", label: "faculties" },
  { href: "/programs", label: "programs" },
  { href: "/news", label: "news" },
  { href: "/events", label: "events" },
  { href: "/staff", label: "staff" },
  { href: "/contact", label: "contact" },
] as const;

const PORTAL_LINKS: { href: string; label: string; roles: Role[] }[] = [
  { href: "/portal/admissions", label: "applicant", roles: ["applicant"] },
  { href: "/portal/review", label: "review", roles: ["admissions_officer"] },
  { href: "/portal/student", label: "student", roles: ["student"] },
  { href: "/portal/lecturer", label: "lecturer", roles: ["lecturer"] },
  { href: "/portal/editor", label: "editor", roles: ["editor"] },
];

export function SiteHeader() {
  const t = useTranslations();
  const locale = useLocale();
  const pathname = usePathname();
  const auth = useAuth();
  const portalLinks = PORTAL_LINKS.filter((link) => hasAnyRole(auth.roles, link.roles));

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-4">
        <Link href="/" className="text-lg font-semibold text-brand">
          {t("site.name")}
        </Link>
        <nav aria-label={t("nav.main")} className="flex-1">
          <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {[...PUBLIC_LINKS, ...portalLinks].map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  aria-current={pathname.startsWith(link.href) ? "page" : undefined}
                  className="text-slate-700 hover:text-brand aria-[current=page]:font-semibold aria-[current=page]:text-brand"
                >
                  {t(`nav.${link.label}`)}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
        <ul aria-label={t("nav.language")} className="flex gap-2 text-sm">
          {routing.locales.map((code) => (
            <li key={code}>
              <Link
                href={pathname}
                locale={code}
                lang={code}
                aria-current={code === locale ? "true" : undefined}
                className="uppercase text-slate-700 aria-[current=true]:font-semibold aria-[current=true]:text-brand"
              >
                {code}
              </Link>
            </li>
          ))}
        </ul>
        {auth.authenticated ? (
          <button type="button" className="btn-secondary" onClick={auth.logout}>
            {t("nav.logout")}
          </button>
        ) : (
          <button type="button" className="btn-secondary" onClick={auth.login} disabled={!auth.ready}>
            {t("nav.login")}
          </button>
        )}
      </div>
    </header>
  );
}
