"use client";

import { useMutation } from "@tanstack/react-query";
import { useLocale, useTranslations } from "next-intl";
import type { FormEvent } from "react";

import { apiFetch } from "@/lib/api/client";
import type { ContactInput } from "@/lib/api/types";

export default function ContactPage() {
  const t = useTranslations("contact");
  const locale = useLocale() as ContactInput["locale"];
  const send = useMutation({
    mutationFn: (body: ContactInput) =>
      apiFetch<{ status: string }>("/public/contact", { method: "POST", body }),
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    send.mutate(
      {
        name: String(data.get("name")),
        email: String(data.get("email")),
        subject: String(data.get("subject")),
        message: String(data.get("message")),
        locale,
      },
      { onSuccess: () => form.reset() },
    );
  }

  return (
    <div className="max-w-xl space-y-6">
      <h1>{t("title")}</h1>
      <p className="text-slate-700">{t("intro")}</p>
      <form onSubmit={submit} className="card space-y-4">
        <div>
          <label htmlFor="contact-name" className="label">{t("name")}</label>
          <input id="contact-name" name="name" required maxLength={120} autoComplete="name" className="input" />
        </div>
        <div>
          <label htmlFor="contact-email" className="label">{t("email")}</label>
          <input id="contact-email" name="email" type="email" required autoComplete="email" className="input" />
        </div>
        <div>
          <label htmlFor="contact-subject" className="label">{t("subject")}</label>
          <input id="contact-subject" name="subject" required maxLength={200} className="input" />
        </div>
        <div>
          <label htmlFor="contact-message" className="label">{t("message")}</label>
          <textarea id="contact-message" name="message" required minLength={10} maxLength={5000} rows={6} className="input" />
        </div>
        <button type="submit" className="btn" disabled={send.isPending}>
          {t("send")}
        </button>
        {send.isSuccess && <p role="status" className="text-green-800">{t("sent")}</p>}
        {send.isError && <p role="alert" className="text-red-700">{t("failed")}</p>}
      </form>
    </div>
  );
}
