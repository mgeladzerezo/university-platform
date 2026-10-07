"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import { RequireRole } from "@/components/RequireRole";
import { RichTextEditor } from "@/components/RichTextEditor";
import { StatusBadge } from "@/components/StatusBadge";
import { useRouter } from "@/i18n/navigation";
import type {
  ContentInput,
  ContentKind,
  EditorialContent,
  WorkflowAction,
} from "@/lib/api/types";
import { useAuth } from "@/lib/auth/AuthProvider";
import { availableActions } from "@/lib/workflow";

const KINDS: ContentKind[] = ["page", "news", "event"];

/** <input type="datetime-local"> works in local time without a zone suffix. */
function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function ContentForm({ item }: { item: EditorialContent | null }) {
  const t = useTranslations();
  const router = useRouter();
  const { api } = useAuth();
  const queryClient = useQueryClient();
  const [bodyHtml, setBodyHtml] = useState(item?.body_html ?? "");
  const [kind, setKind] = useState<ContentKind>(item?.kind ?? "news");
  const editable = !item || item.status === "draft";

  const refresh = (saved: EditorialContent) => {
    queryClient.setQueryData(["cms-content", String(saved.id)], saved);
    queryClient.invalidateQueries({ queryKey: ["cms-content"], exact: true });
  };
  const save = useMutation({
    mutationFn: (body: ContentInput) =>
      item
        ? api<EditorialContent>(`/cms/content/${item.id}`, { method: "PUT", body })
        : api<EditorialContent>("/cms/content", { method: "POST", body }),
    onSuccess: (saved) => {
      refresh(saved);
      if (!item) router.replace(`/portal/editor/${saved.id}`);
    },
  });
  const transition = useMutation({
    mutationFn: (action: WorkflowAction) =>
      api<EditorialContent>(`/cms/content/${item?.id}/transitions`, {
        method: "POST",
        body: { action, comment: "" },
      }),
    onSuccess: refresh,
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const startsAt = String(data.get("event_starts_at") ?? "");
    save.mutate({
      kind,
      slug: String(data.get("slug")),
      locale: data.get("locale") as ContentInput["locale"],
      title: String(data.get("title")),
      summary: String(data.get("summary")),
      body_html: bodyHtml,
      event_starts_at: kind === "event" && startsAt ? new Date(startsAt).toISOString() : null,
      event_location: kind === "event" ? String(data.get("event_location") ?? "") : null,
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1>{item ? t("editor.edit") : t("editor.new")}</h1>
        {item && <StatusBadge status={item.status} label={t(`editor.status.${item.status}`)} />}
      </div>
      {!editable && <p className="text-slate-700">{t("editor.lockedHint")}</p>}

      <form onSubmit={submit} className="card space-y-4">
        <fieldset disabled={!editable} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <label htmlFor="kind" className="label">{t("editor.kind")}</label>
              <select id="kind" className="input" value={kind} onChange={(event) => setKind(event.target.value as ContentKind)}>
                {KINDS.map((value) => (
                  <option key={value} value={value}>{t(`editor.kinds.${value}`)}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="locale" className="label">{t("editor.locale")}</label>
              <select id="locale" name="locale" className="input" defaultValue={item?.locale ?? "pl"}>
                <option value="pl">PL</option>
                <option value="en">EN</option>
              </select>
            </div>
            <div>
              <label htmlFor="slug" className="label">{t("editor.slug")}</label>
              <input id="slug" name="slug" required pattern="[a-z0-9]+(-[a-z0-9]+)*" defaultValue={item?.slug} className="input" />
            </div>
          </div>
          <div>
            <label htmlFor="title" className="label">{t("editor.heading")}</label>
            <input id="title" name="title" required maxLength={200} defaultValue={item?.title} className="input" />
          </div>
          <div>
            <label htmlFor="summary" className="label">{t("editor.summary")}</label>
            <textarea id="summary" name="summary" rows={2} maxLength={500} defaultValue={item?.summary} className="input" />
          </div>
          {kind === "event" && (
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label htmlFor="event_starts_at" className="label">{t("editor.eventStart")}</label>
                <input id="event_starts_at" name="event_starts_at" type="datetime-local" required defaultValue={toLocalInput(item?.event_starts_at)} className="input" />
              </div>
              <div>
                <label htmlFor="event_location" className="label">{t("editor.eventLocation")}</label>
                <input id="event_location" name="event_location" maxLength={200} defaultValue={item?.event_location ?? ""} className="input" />
              </div>
            </div>
          )}
        </fieldset>
        <div>
          <span id="body-label" className="label">{t("editor.body")}</span>
          <RichTextEditor initialHtml={bodyHtml} editable={editable} labelledBy="body-label" onChange={setBodyHtml} />
        </div>
        <button type="submit" className="btn" disabled={!editable || save.isPending}>
          {t("common.save")}
        </button>
        {save.isSuccess && <p role="status" className="text-green-800">{t("common.saved")}</p>}
        {save.isError && <p role="alert" className="text-red-700">{save.error.message}</p>}
      </form>

      {item && (
        <section aria-label={t("admissions.statusLabel")} className="flex flex-wrap gap-3">
          {availableActions(item.status).map((action) => (
            <button key={action} type="button" className="btn-secondary" disabled={transition.isPending} onClick={() => transition.mutate(action)}>
              {t(`editor.actions.${action}`)}
            </button>
          ))}
          {transition.isError && <p role="alert" className="w-full text-red-700">{transition.error.message}</p>}
        </section>
      )}
    </div>
  );
}

function ContentLoader({ id }: { id: string }) {
  const t = useTranslations("common");
  const { api } = useAuth();
  const isNew = id === "new";
  const query = useQuery({
    queryKey: ["cms-content", id],
    queryFn: () => api<EditorialContent>(`/cms/content/${id}`),
    enabled: !isNew,
  });

  if (isNew) return <ContentForm item={null} />;
  if (query.isPending) return <p role="status">{t("loading")}</p>;
  if (query.isError) return <p role="alert">{t("error")}</p>;
  // Remount on status change so the form and editor pick up the new editable state.
  return <ContentForm key={`${query.data.id}-${query.data.status}`} item={query.data} />;
}

export default function EditContentPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <RequireRole allowed={["editor"]}>
      <ContentLoader id={id} />
    </RequireRole>
  );
}
