"use client";

import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import type { FormEvent } from "react";

import { StatusBadge } from "@/components/StatusBadge";
import type {
  Application,
  ApplicationDocument,
  DocumentType,
  DownloadLink,
  UploadTicket,
} from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";

const DOC_TYPES: DocumentType[] = ["identity", "diploma", "transcript", "photo", "other"];
const ACCEPTED = "application/pdf,image/jpeg,image/png";

interface Props {
  application: Application;
  editable: boolean;
  onChanged: () => void;
}

/** Sends the file straight to object storage using the presigned POST from the API. */
async function uploadToStorage(ticket: UploadTicket, file: File): Promise<void> {
  const form = new FormData();
  for (const [key, value] of Object.entries(ticket.upload_fields)) form.append(key, value);
  form.append("file", file);
  const response = await fetch(ticket.upload_url, { method: "POST", body: form });
  if (!response.ok) throw new Error(`Upload failed with status ${response.status}`);
}

export function DocumentsStep({ application, editable, onChanged }: Props) {
  const t = useTranslations("admissions");
  const { api } = useAuth();
  const base = `/admissions/applications/${application.id}/documents`;

  const upload = useMutation({
    mutationFn: async ({ file, docType }: { file: File; docType: DocumentType }) => {
      const ticket = await api<UploadTicket>(base, {
        method: "POST",
        body: {
          doc_type: docType,
          filename: file.name,
          content_type: file.type,
          size_bytes: file.size,
        },
      });
      await uploadToStorage(ticket, file);
      await api(`${base}/${ticket.document.id}/complete`, { method: "POST" });
    },
    onSuccess: onChanged,
  });
  const remove = useMutation({
    mutationFn: (documentId: string) => api(`${base}/${documentId}`, { method: "DELETE" }),
    onSuccess: onChanged,
  });

  async function download(document: ApplicationDocument) {
    const link = await api<DownloadLink>(`${base}/${document.id}/download`);
    window.location.assign(link.url);
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const file = data.get("file");
    if (!(file instanceof File) || file.size === 0) return;
    upload.mutate(
      { file, docType: data.get("doc_type") as DocumentType },
      { onSuccess: () => form.reset() },
    );
  }

  return (
    <div className="space-y-6">
      {application.missing_documents.length > 0 ? (
        <div>
          <h3 className="font-medium">{t("missing")}</h3>
          <ul className="list-disc pl-6 text-sm">
            {application.missing_documents.map((type) => (
              <li key={type}>{t(`docTypes.${type}`)}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-green-800">{t("complete")}</p>
      )}

      <ul className="space-y-2">
        {application.documents.map((document) => (
          <li key={document.id} className="flex flex-wrap items-center gap-3 rounded border border-slate-200 p-3 text-sm">
            <span className="font-medium">{t(`docTypes.${document.doc_type}`)}</span>
            <span className="text-slate-700">{document.filename}</span>
            <StatusBadge status={document.scan_status} label={t(`scan.${document.scan_status}`)} />
            <span className="ml-auto flex gap-2">
              {document.scan_status === "clean" && (
                <button type="button" className="btn-secondary" onClick={() => download(document)}>
                  {t("download")}
                </button>
              )}
              {editable && (
                <button type="button" className="btn-secondary" onClick={() => remove.mutate(document.id)}>
                  {t("remove")}
                </button>
              )}
            </span>
          </li>
        ))}
      </ul>

      {editable && (
        <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="doc_type" className="label">{t("docType")}</label>
            <select id="doc_type" name="doc_type" className="input">
              {DOC_TYPES.map((type) => (
                <option key={type} value={type}>{t(`docTypes.${type}`)}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="file" className="label">{t("file")}</label>
            <input id="file" name="file" type="file" accept={ACCEPTED} required className="text-sm" />
          </div>
          <button type="submit" className="btn" disabled={upload.isPending}>
            {t("upload")}
          </button>
        </form>
      )}
      {(upload.isError || remove.isError) && (
        <p role="alert" className="text-red-700">
          {(upload.error ?? remove.error)?.message}
        </p>
      )}
    </div>
  );
}
