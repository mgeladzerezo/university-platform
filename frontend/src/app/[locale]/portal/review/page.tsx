"use client";

import { useQuery } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { RequireRole } from "@/components/RequireRole";
import { StatusBadge } from "@/components/StatusBadge";
import { Link } from "@/i18n/navigation";
import type { ApplicationStatus, QueueItem } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { formatDateTime } from "@/lib/format";

const FILTERS: ApplicationStatus[] = ["submitted", "under_review", "accepted", "rejected"];

function Queue() {
  const t = useTranslations();
  const locale = useLocale();
  const { api } = useAuth();
  const [status, setStatus] = useState<ApplicationStatus>("submitted");
  const queue = useQuery({
    queryKey: ["review-queue", status],
    queryFn: () => api<QueueItem[]>("/admissions/review/applications", { query: { status } }),
  });

  return (
    <div className="space-y-6">
      <h1>{t("review.title")}</h1>
      <div className="max-w-xs">
        <label htmlFor="status-filter" className="label">{t("review.filter")}</label>
        <select
          id="status-filter"
          className="input"
          value={status}
          onChange={(event) => setStatus(event.target.value as ApplicationStatus)}
        >
          {FILTERS.map((value) => (
            <option key={value} value={value}>{t(`admissions.status.${value}`)}</option>
          ))}
        </select>
      </div>
      {queue.isPending && <p role="status">{t("common.loading")}</p>}
      {queue.isError && <p role="alert">{t("common.error")}</p>}
      {queue.data?.length === 0 && <p>{t("common.empty")}</p>}
      {queue.data && queue.data.length > 0 && (
        <table className="w-full border-collapse bg-white text-left text-sm">
          <caption className="sr-only">{t("review.title")}</caption>
          <thead>
            <tr className="border-b border-slate-300">
              <th scope="col" className="p-3">{t("review.applicant")}</th>
              <th scope="col" className="p-3">{t("review.program")}</th>
              <th scope="col" className="p-3">{t("review.submitted")}</th>
              <th scope="col" className="p-3">{t("admissions.statusLabel")}</th>
            </tr>
          </thead>
          <tbody>
            {queue.data.map((item) => (
              <tr key={item.id} className="border-b border-slate-200">
                <th scope="row" className="p-3 font-medium">
                  <Link href={`/portal/review/${item.id}`} className="text-brand underline">
                    {item.applicant_name || item.id}
                  </Link>
                </th>
                <td className="p-3">{item.program_name}</td>
                <td className="p-3">{formatDateTime(item.submitted_at, locale)}</td>
                <td className="p-3">
                  <StatusBadge status={item.status} label={t(`admissions.status.${item.status}`)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function ReviewQueuePage() {
  return (
    <RequireRole allowed={["admissions_officer"]}>
      <Queue />
    </RequireRole>
  );
}
