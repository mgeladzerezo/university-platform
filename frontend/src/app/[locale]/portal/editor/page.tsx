"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";

import { RequireRole } from "@/components/RequireRole";
import { StatusBadge } from "@/components/StatusBadge";
import { Link } from "@/i18n/navigation";
import type { EditorialContent } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { formatDateTime } from "@/lib/format";

function ContentTable() {
  const t = useTranslations();
  const locale = useLocale();
  const { api } = useAuth();
  const content = useQuery({
    queryKey: ["cms-content"],
    queryFn: () => api<EditorialContent[]>("/cms/content"),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1>{t("editor.title")}</h1>
        <Link href="/portal/editor/new" className="btn">
          {t("editor.new")}
        </Link>
      </div>
      {content.isPending && <p role="status">{t("common.loading")}</p>}
      {content.isError && <p role="alert">{t("common.error")}</p>}
      {content.data?.length === 0 && <p>{t("common.empty")}</p>}
      {content.data && content.data.length > 0 && (
        <table className="w-full border-collapse bg-white text-left text-sm">
          <caption className="sr-only">{t("editor.title")}</caption>
          <thead>
            <tr className="border-b border-slate-300">
              <th scope="col" className="p-3">{t("editor.heading")}</th>
              <th scope="col" className="p-3">{t("editor.kind")}</th>
              <th scope="col" className="p-3">{t("editor.locale")}</th>
              <th scope="col" className="p-3">{t("admissions.statusLabel")}</th>
              <th scope="col" className="p-3">{t("editor.updated")}</th>
            </tr>
          </thead>
          <tbody>
            {content.data.map((item) => (
              <tr key={item.id} className="border-b border-slate-200">
                <th scope="row" className="p-3 font-medium">
                  <Link href={`/portal/editor/${item.id}`} className="text-brand underline">
                    {item.title}
                  </Link>
                </th>
                <td className="p-3">{t(`editor.kinds.${item.kind}`)}</td>
                <td className="p-3 uppercase">{item.locale}</td>
                <td className="p-3">
                  <StatusBadge status={item.status} label={t(`editor.status.${item.status}`)} />
                </td>
                <td className="p-3">{formatDateTime(item.updated_at, locale)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function EditorPage() {
  return (
    <RequireRole allowed={["editor"]}>
      <ContentTable />
    </RequireRole>
  );
}
