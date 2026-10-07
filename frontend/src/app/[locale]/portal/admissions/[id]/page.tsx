"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { DocumentsStep } from "@/components/admissions/DocumentsStep";
import { EducationForm, PersonalForm, StatementForm } from "@/components/admissions/StepForms";
import { RequireRole } from "@/components/RequireRole";
import { StatusBadge } from "@/components/StatusBadge";
import type { Application } from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { formatDateTime } from "@/lib/format";

const STEPS = ["personal", "education", "statement", "documents", "review"] as const;
type Step = (typeof STEPS)[number];

function isComplete(application: Application, step: Step): boolean {
  if (step === "documents") return application.missing_documents.length === 0;
  if (step === "review") return application.status !== "draft";
  return Boolean(application[step]);
}

function ApplicationEditor({ id }: { id: string }) {
  const t = useTranslations();
  const locale = useLocale();
  const { api } = useAuth();
  const queryClient = useQueryClient();
  const [step, setStep] = useState<Step>("personal");
  const path = `/admissions/applications/${id}`;

  const query = useQuery({
    queryKey: ["application", id],
    queryFn: () => api<Application>(path),
    // Virus scans finish in the background; poll while any document is pending.
    refetchInterval: (current) =>
      current.state.data?.documents.some((d) => d.scan_status === "pending_scan") ? 3000 : false,
  });
  const update = (application: Application) =>
    queryClient.setQueryData(["application", id], application);

  const save = useMutation({
    mutationFn: ({ part, body }: { part: string; body: unknown }) =>
      api<Application>(`${path}/${part}`, { method: "PUT", body }),
    onSuccess: update,
  });
  const action = useMutation({
    mutationFn: (name: "submit" | "withdraw") =>
      api<Application>(`${path}/${name}`, { method: "POST" }),
    onSuccess: update,
  });

  if (query.isPending) return <p role="status">{t("common.loading")}</p>;
  if (query.isError) return <p role="alert">{t("common.error")}</p>;
  const application = query.data;
  const editable = application.status === "draft";
  const canWithdraw = ["draft", "submitted", "under_review"].includes(application.status);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1>{t("admissions.applicationFor", { program: application.program_name })}</h1>
        <StatusBadge status={application.status} label={t(`admissions.status.${application.status}`)} />
      </div>
      {!editable && <p className="text-slate-700">{t("admissions.readOnly")}</p>}

      <nav aria-label={t("admissions.statusLabel")}>
        <ol className="flex flex-wrap gap-2">
          {STEPS.map((name, index) => (
            <li key={name}>
              <button
                type="button"
                aria-current={name === step ? "step" : undefined}
                onClick={() => setStep(name)}
                className="rounded-md border border-slate-400 bg-white px-3 py-1.5 text-sm aria-[current=step]:border-brand aria-[current=step]:bg-brand aria-[current=step]:text-white"
              >
                {index + 1}. {t(`admissions.steps.${name}`)}
                {isComplete(application, name) && <span aria-hidden="true"> ✓</span>}
              </button>
            </li>
          ))}
        </ol>
      </nav>

      <section aria-labelledby="step-title" className="card space-y-4">
        <h2 id="step-title">{t(`admissions.steps.${step}`)}</h2>
        {step === "personal" && (
          <PersonalForm application={application} disabled={!editable} onSave={(body) => save.mutate({ part: "personal", body })} />
        )}
        {step === "education" && (
          <EducationForm application={application} disabled={!editable} onSave={(body) => save.mutate({ part: "education", body })} />
        )}
        {step === "statement" && (
          <StatementForm application={application} disabled={!editable} onSave={(statement) => save.mutate({ part: "statement", body: { statement } })} />
        )}
        {step === "documents" && (
          <DocumentsStep application={application} editable={editable} onChanged={() => query.refetch()} />
        )}
        {step === "review" && (
          <div className="space-y-4">
            <h3 className="font-medium">{t("admissions.history")}</h3>
            <ol className="list-decimal pl-6 text-sm">
              {application.history.map((event, index) => (
                <li key={index}>
                  {t(`admissions.status.${event.to_status}`)} · {formatDateTime(event.created_at, locale)}
                </li>
              ))}
            </ol>
            {application.decision_note && (
              <p>
                <span className="font-medium">{t("admissions.decisionNote")}: </span>
                {application.decision_note}
              </p>
            )}
            <div className="flex gap-3">
              {editable && (
                <button type="button" className="btn" disabled={action.isPending} onClick={() => action.mutate("submit")}>
                  {t("admissions.submit")}
                </button>
              )}
              {canWithdraw && (
                <button type="button" className="btn-secondary" disabled={action.isPending} onClick={() => action.mutate("withdraw")}>
                  {t("admissions.withdraw")}
                </button>
              )}
            </div>
          </div>
        )}
        {save.isSuccess && step !== "documents" && step !== "review" && (
          <p role="status" className="text-green-800">{t("common.saved")}</p>
        )}
        {(save.isError || action.isError) && (
          <p role="alert" className="text-red-700">{(save.error ?? action.error)?.message}</p>
        )}
      </section>
    </div>
  );
}

export default function ApplicationPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RequireRole allowed={["applicant"]}>
      <ApplicationEditor id={id} />
    </RequireRole>
  );
}
