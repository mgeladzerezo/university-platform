"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import type { FormEvent } from "react";

import { RequireRole } from "@/components/RequireRole";
import { StatusBadge } from "@/components/StatusBadge";
import { Link, useRouter } from "@/i18n/navigation";
import { apiFetch } from "@/lib/api/client";
import type { Application, Program } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";

function Applications() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const { api } = useAuth();
  const queryClient = useQueryClient();

  const applications = useQuery({
    queryKey: ["applications"],
    queryFn: () => api<Application[]>("/admissions/applications"),
  });
  const programs = useQuery({
    queryKey: ["programs", locale],
    queryFn: () => apiFetch<Program[]>("/public/programs", { query: { locale } }),
  });
  const create = useMutation({
    mutationFn: (programId: number) =>
      api<Application>("/admissions/applications", {
        method: "POST",
        body: { program_id: programId, locale },
      }),
    onSuccess: (application) => {
      queryClient.invalidateQueries({ queryKey: ["applications"] });
      router.push(`/portal/admissions/${application.id}`);
    },
  });

  function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    create.mutate(Number(new FormData(event.currentTarget).get("program")));
  }

  return (
    <div className="space-y-8">
      <h1>{t("admissions.title")}</h1>
      {applications.isPending && <p role="status">{t("common.loading")}</p>}
      {applications.data?.length === 0 && <p>{t("common.empty")}</p>}
      <ul className="space-y-3">
        {applications.data?.map((application) => (
          <li key={application.id} className="card flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-medium">{application.program_name}</p>
              <StatusBadge
                status={application.status}
                label={t(`admissions.status.${application.status}`)}
              />
            </div>
            <Link href={`/portal/admissions/${application.id}`} className="btn-secondary">
              {t("admissions.open")}
            </Link>
          </li>
        ))}
      </ul>

      <section aria-labelledby="new-application" className="card max-w-xl space-y-4">
        <h2 id="new-application">{t("admissions.newTitle")}</h2>
        <form onSubmit={start} className="flex flex-wrap items-end gap-3">
          <div className="min-w-56 flex-1">
            <label htmlFor="program" className="label">{t("admissions.program")}</label>
            <select id="program" name="program" required className="input">
              {programs.data?.map((program) => (
                <option key={program.id} value={program.id}>
                  {program.name} ({t(`programs.${program.degree_level}`)})
                </option>
              ))}
            </select>
          </div>
          <button type="submit" className="btn" disabled={create.isPending}>
            {t("admissions.start")}
          </button>
        </form>
        {create.isError && <p role="alert" className="text-red-700">{create.error.message}</p>}
      </section>
    </div>
  );
}

export default function AdmissionsPage() {
  return (
    <RequireRole allowed={["applicant"]}>
      <Applications />
    </RequireRole>
  );
}
