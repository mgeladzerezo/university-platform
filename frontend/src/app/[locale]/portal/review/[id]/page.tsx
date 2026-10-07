"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { RequireRole } from "@/components/RequireRole";
import { StatusBadge } from "@/components/StatusBadge";
import type {
  Application,
  ApplicationDocument,
  ApplicationSummary,
  DownloadLink,
} from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";

function ReviewDetail({ id }: { id: string }) {
  const t = useTranslations();
  const { api } = useAuth();
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const path = `/admissions/applications/${id}`;
  const reviewPath = `/admissions/review/applications/${id}`;

  const query = useQuery({ queryKey: ["review", id], queryFn: () => api<Application>(path) });
  const update = (application: Application) => {
    queryClient.setQueryData(["review", id], application);
    queryClient.invalidateQueries({ queryKey: ["review-queue"] });
  };
  const start = useMutation({
    mutationFn: () => api<Application>(`${reviewPath}/start`, { method: "POST" }),
    onSuccess: update,
  });
  const decide = useMutation({
    mutationFn: (decision: "accepted" | "rejected") =>
      api<Application>(`${reviewPath}/decision`, { method: "POST", body: { decision, note } }),
    onSuccess: update,
  });
  const summary = useMutation({
    mutationFn: () =>
      api<ApplicationSummary>(`/assistant/applications/${id}/summary`, { method: "POST" }),
  });

  async function download(document: ApplicationDocument) {
    const link = await api<DownloadLink>(`${path}/documents/${document.id}/download`);
    window.location.assign(link.url);
  }

  if (query.isPending) return <p role="status">{t("common.loading")}</p>;
  if (query.isError) return <p role="alert">{t("common.error")}</p>;
  const application = query.data;
  const personal = application.personal;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1>
          {personal ? `${personal.first_name} ${personal.last_name}` : application.id}
        </h1>
        <StatusBadge status={application.status} label={t(`admissions.status.${application.status}`)} />
      </div>
      <p className="text-slate-700">{application.program_name}</p>

      <section aria-labelledby="education-title" className="card space-y-2">
        <h2 id="education-title">{t("review.education")}</h2>
        {application.education && (
          <>
            <p>
              {application.education.school_name} ({application.education.graduation_year})
            </p>
            <ul className="list-disc pl-6 text-sm">
              {application.education.exam_results.map((result) => (
                <li key={result.subject}>
                  {result.subject}: {result.score_percent}%
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section aria-labelledby="statement-title" className="card space-y-2">
        <h2 id="statement-title">{t("review.statement")}</h2>
        <p className="whitespace-pre-wrap">{application.statement}</p>
      </section>

      <section aria-labelledby="documents-title" className="card space-y-2">
        <h2 id="documents-title">{t("review.documents")}</h2>
        <ul className="space-y-2 text-sm">
          {application.documents.map((document) => (
            <li key={document.id} className="flex flex-wrap items-center gap-3">
              <span className="font-medium">{t(`admissions.docTypes.${document.doc_type}`)}</span>
              <span>{document.filename}</span>
              <StatusBadge status={document.scan_status} label={t(`admissions.scan.${document.scan_status}`)} />
              {document.scan_status === "clean" && (
                <button type="button" className="btn-secondary" onClick={() => download(document)}>
                  {t("admissions.download")}
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="summary-title" className="card space-y-3">
        <h2 id="summary-title">{t("review.summaryTitle")}</h2>
        <p className="text-sm text-slate-700">{t("review.summaryHint")}</p>
        <button type="button" className="btn-secondary" disabled={summary.isPending} onClick={() => summary.mutate()}>
          {t("review.generate")}
        </button>
        <div aria-live="polite">
          {summary.isPending && <p>{t("common.loading")}</p>}
          {summary.isError && <p className="text-red-700">{t("chat.error")}</p>}
          {summary.data && (
            <div className="space-y-3">
              <p className="whitespace-pre-wrap">{summary.data.summary}</p>
              <h3 className="font-medium">{t("review.missingDocs")}</h3>
              {summary.data.missing_documents.length === 0 ? (
                <p>{t("review.noneMissing")}</p>
              ) : (
                <ul className="list-disc pl-6 text-sm">
                  {summary.data.missing_documents.map((type) => (
                    <li key={type}>{t(`admissions.docTypes.${type}`)}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </section>

      {application.status === "submitted" && (
        <button type="button" className="btn" disabled={start.isPending} onClick={() => start.mutate()}>
          {t("review.start")}
        </button>
      )}
      {application.status === "under_review" && (
        <section className="card space-y-3">
          <div>
            <label htmlFor="decision-note" className="label">{t("review.note")}</label>
            <textarea id="decision-note" rows={3} maxLength={2000} className="input" value={note} onChange={(event) => setNote(event.target.value)} />
          </div>
          <div className="flex gap-3">
            <button type="button" className="btn" disabled={decide.isPending} onClick={() => decide.mutate("accepted")}>
              {t("review.accept")}
            </button>
            <button type="button" className="btn-secondary" disabled={decide.isPending} onClick={() => decide.mutate("rejected")}>
              {t("review.reject")}
            </button>
          </div>
        </section>
      )}
      {(start.isError || decide.isError) && (
        <p role="alert" className="text-red-700">{(start.error ?? decide.error)?.message}</p>
      )}
    </div>
  );
}

export default function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RequireRole allowed={["admissions_officer"]}>
      <ReviewDetail id={id} />
    </RequireRole>
  );
}
