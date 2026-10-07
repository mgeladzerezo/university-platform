"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";

import { RequireRole } from "@/components/RequireRole";
import { StatusBadge } from "@/components/StatusBadge";
import type { Announcement, Grade, Offering, TimetableEntry } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { formatDateTime, formatTime } from "@/lib/format";

const cell = "p-3";
const table = "w-full border-collapse bg-white text-left text-sm";

function StudentPortal() {
  const t = useTranslations();
  const locale = useLocale();
  const { api } = useAuth();
  const queryClient = useQueryClient();
  const query = { locale };

  const offerings = useQuery({
    queryKey: ["offerings", locale],
    queryFn: () => api<Offering[]>("/academics/offerings", { query }),
  });
  const timetable = useQuery({
    queryKey: ["timetable", locale],
    queryFn: () => api<TimetableEntry[]>("/academics/me/timetable", { query }),
  });
  const grades = useQuery({
    queryKey: ["grades", locale],
    queryFn: () => api<Grade[]>("/academics/me/grades", { query }),
  });
  const announcements = useQuery({
    queryKey: ["announcements"],
    queryFn: () => api<Announcement[]>("/academics/me/announcements"),
  });

  const change = useMutation({
    mutationFn: ({ offeringId, enroll }: { offeringId: number; enroll: boolean }) =>
      api(`/academics/offerings/${offeringId}/enrollment`, { method: enroll ? "POST" : "DELETE" }),
    // Seats, timetable and grades all depend on enrollment, so refresh them together.
    onSettled: () => {
      for (const key of ["offerings", "timetable", "grades", "announcements"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
    },
  });

  return (
    <div className="space-y-10">
      <h1>{t("student.title")}</h1>

      <section aria-labelledby="offerings-title" className="space-y-3">
        <h2 id="offerings-title">{t("student.offerings")}</h2>
        {offerings.isPending && <p role="status">{t("common.loading")}</p>}
        {change.isError && <p role="alert" className="text-red-700">{change.error.message}</p>}
        <div className="overflow-x-auto">
          <table className={table}>
            <thead>
              <tr className="border-b border-slate-300">
                <th scope="col" className={cell}>{t("student.course")}</th>
                <th scope="col" className={cell}>{t("student.lecturer")}</th>
                <th scope="col" className={cell}>{t("student.seats")}</th>
                <th scope="col" className={cell}>{t("student.action")}</th>
              </tr>
            </thead>
            <tbody>
              {offerings.data?.map((offering) => {
                const full = offering.enrolled_count >= offering.capacity;
                return (
                  <tr key={offering.id} className="border-b border-slate-200">
                    <th scope="row" className={`${cell} font-medium`}>
                      {offering.course_code} {offering.course_title}
                    </th>
                    <td className={cell}>{offering.lecturer_name}</td>
                    <td className={cell}>
                      {offering.enrolled_count}/{offering.capacity}
                    </td>
                    <td className={`${cell} space-x-2`}>
                      {offering.my_status ? (
                        <>
                          <StatusBadge status={offering.my_status} label={t(`student.${offering.my_status}`)} />
                          <button type="button" className="btn-secondary" disabled={change.isPending} onClick={() => change.mutate({ offeringId: offering.id, enroll: false })}>
                            {t("student.drop")}
                          </button>
                        </>
                      ) : (
                        <button type="button" className="btn" disabled={change.isPending || !offering.enrollment_open} onClick={() => change.mutate({ offeringId: offering.id, enroll: true })}>
                          {full ? t("student.joinWaitlist") : t("student.enroll")}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="timetable-title" className="space-y-3">
        <h2 id="timetable-title">{t("student.timetable")}</h2>
        {timetable.data?.length === 0 && <p>{t("common.empty")}</p>}
        {timetable.data && timetable.data.length > 0 && (
          <table className={table}>
            <thead>
              <tr className="border-b border-slate-300">
                <th scope="col" className={cell}>{t("student.day")}</th>
                <th scope="col" className={cell}>{t("student.time")}</th>
                <th scope="col" className={cell}>{t("student.course")}</th>
                <th scope="col" className={cell}>{t("student.room")}</th>
              </tr>
            </thead>
            <tbody>
              {timetable.data.map((entry, index) => (
                <tr key={index} className="border-b border-slate-200">
                  <td className={cell}>{t(`student.weekdays.${entry.weekday}`)}</td>
                  <td className={cell}>
                    {formatTime(entry.starts_at)}–{formatTime(entry.ends_at)}
                  </td>
                  <td className={cell}>{entry.course_code} {entry.course_title}</td>
                  <td className={cell}>{entry.room}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section aria-labelledby="grades-title" className="space-y-3">
        <h2 id="grades-title">{t("student.grades")}</h2>
        {grades.data?.length === 0 && <p>{t("common.empty")}</p>}
        {grades.data && grades.data.length > 0 && (
          <table className={table}>
            <thead>
              <tr className="border-b border-slate-300">
                <th scope="col" className={cell}>{t("student.course")}</th>
                <th scope="col" className={cell}>ECTS</th>
                <th scope="col" className={cell}>{t("student.grade")}</th>
              </tr>
            </thead>
            <tbody>
              {grades.data.map((grade) => (
                <tr key={grade.offering_id} className="border-b border-slate-200">
                  <th scope="row" className={`${cell} font-medium`}>
                    {grade.course_code} {grade.course_title}
                  </th>
                  <td className={cell}>{grade.ects}</td>
                  <td className={cell}>{grade.grade?.toFixed(1) ?? t("student.noGrade")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section aria-labelledby="announcements-title" className="space-y-3">
        <h2 id="announcements-title">{t("student.announcements")}</h2>
        {announcements.data?.length === 0 && <p>{t("common.empty")}</p>}
        <ul className="space-y-3">
          {announcements.data?.map((announcement) => (
            <li key={announcement.id} className="card">
              <p className="text-sm text-slate-600">
                {announcement.course_code ?? t("student.general")} ·{" "}
                {formatDateTime(announcement.created_at, locale)}
              </p>
              <h3 className="font-semibold">{announcement.title}</h3>
              <p className="whitespace-pre-wrap text-slate-800">{announcement.body}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export default function StudentPage() {
  return (
    <RequireRole allowed={["student"]}>
      <StudentPortal />
    </RequireRole>
  );
}
