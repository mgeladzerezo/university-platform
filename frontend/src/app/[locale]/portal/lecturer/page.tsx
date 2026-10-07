"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import { RequireRole } from "@/components/RequireRole";
import type { GradeValue, Offering, RosterEntry } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";

const GRADES: GradeValue[] = [2, 3, 3.5, 4, 4.5, 5];

function Roster({ offering }: { offering: Offering }) {
  const t = useTranslations();
  const { api } = useAuth();
  const queryClient = useQueryClient();
  const key = ["roster", offering.id];

  const roster = useQuery({
    queryKey: key,
    queryFn: () => api<RosterEntry[]>(`/academics/teaching/offerings/${offering.id}/roster`),
  });
  const grade = useMutation({
    mutationFn: ({ enrollmentId, value }: { enrollmentId: number; value: GradeValue }) =>
      api<RosterEntry>(`/academics/teaching/enrollments/${enrollmentId}/grade`, {
        method: "PUT",
        body: { value },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const announce = useMutation({
    mutationFn: (body: { title: string; body: string }) =>
      api(`/academics/teaching/offerings/${offering.id}/announcements`, { method: "POST", body }),
  });

  function submitAnnouncement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    announce.mutate(
      { title: String(data.get("title")), body: String(data.get("body")) },
      { onSuccess: () => form.reset() },
    );
  }

  return (
    <div className="space-y-6">
      <section aria-labelledby="roster-title" className="space-y-3">
        <h2 id="roster-title">
          {t("lecturer.roster")}: {offering.course_code} {offering.course_title}
        </h2>
        {roster.data?.length === 0 && <p>{t("common.empty")}</p>}
        {roster.data && roster.data.length > 0 && (
          <table className="w-full border-collapse bg-white text-left text-sm">
            <thead>
              <tr className="border-b border-slate-300">
                <th scope="col" className="p-3">{t("lecturer.student")}</th>
                <th scope="col" className="p-3">{t("lecturer.email")}</th>
                <th scope="col" className="p-3">{t("lecturer.grade")}</th>
              </tr>
            </thead>
            <tbody>
              {roster.data.map((entry) => (
                <tr key={entry.enrollment_id} className="border-b border-slate-200">
                  <th scope="row" className="p-3 font-medium">{entry.student_name}</th>
                  <td className="p-3">{entry.student_email}</td>
                  <td className="p-3">
                    <select
                      aria-label={t("lecturer.gradeFor", { name: entry.student_name })}
                      className="input w-24"
                      value={entry.grade ?? ""}
                      disabled={grade.isPending}
                      onChange={(event) =>
                        grade.mutate({
                          enrollmentId: entry.enrollment_id,
                          value: Number(event.target.value) as GradeValue,
                        })
                      }
                    >
                      <option value="" disabled>{t("lecturer.noGrade")}</option>
                      {GRADES.map((value) => (
                        <option key={value} value={value}>{value.toFixed(1)}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {grade.isError && <p role="alert" className="text-red-700">{grade.error.message}</p>}
      </section>

      <section aria-labelledby="announce-title" className="card max-w-xl space-y-3">
        <h2 id="announce-title">{t("lecturer.announce")}</h2>
        <form onSubmit={submitAnnouncement} className="space-y-3">
          <div>
            <label htmlFor="announcement-title" className="label">{t("lecturer.announcementTitle")}</label>
            <input id="announcement-title" name="title" required maxLength={200} className="input" />
          </div>
          <div>
            <label htmlFor="announcement-body" className="label">{t("lecturer.announcementBody")}</label>
            <textarea id="announcement-body" name="body" required rows={4} maxLength={5000} className="input" />
          </div>
          <button type="submit" className="btn" disabled={announce.isPending}>
            {t("lecturer.publish")}
          </button>
          {announce.isSuccess && <p role="status" className="text-green-800">{t("common.saved")}</p>}
          {announce.isError && <p role="alert" className="text-red-700">{announce.error.message}</p>}
        </form>
      </section>
    </div>
  );
}

function LecturerPortal() {
  const t = useTranslations();
  const locale = useLocale();
  const { api } = useAuth();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const offerings = useQuery({
    queryKey: ["teaching", locale],
    queryFn: () => api<Offering[]>("/academics/teaching/offerings", { query: { locale } }),
  });
  const selected = offerings.data?.find((offering) => offering.id === selectedId);

  return (
    <div className="space-y-8">
      <h1>{t("lecturer.title")}</h1>
      <section aria-labelledby="teaching-title" className="space-y-3">
        <h2 id="teaching-title">{t("lecturer.offerings")}</h2>
        {offerings.isPending && <p role="status">{t("common.loading")}</p>}
        {offerings.data?.length === 0 && <p>{t("common.empty")}</p>}
        <ul className="flex flex-wrap gap-2">
          {offerings.data?.map((offering) => (
            <li key={offering.id}>
              <button
                type="button"
                aria-pressed={offering.id === selectedId}
                onClick={() => setSelectedId(offering.id)}
                className="btn-secondary aria-pressed:border-brand aria-pressed:bg-brand aria-pressed:text-white"
              >
                {offering.course_code} {offering.course_title} ({offering.enrolled_count}/{offering.capacity})
              </button>
            </li>
          ))}
        </ul>
      </section>
      {selected ? <Roster key={selected.id} offering={selected} /> : <p>{t("lecturer.choose")}</p>}
    </div>
  );
}

export default function LecturerPage() {
  return (
    <RequireRole allowed={["lecturer"]}>
      <LecturerPortal />
    </RequireRole>
  );
}
