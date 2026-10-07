"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useId, useState } from "react";

import { API_URL } from "@/lib/api/client";
import { readSse } from "@/lib/sse";

interface Source {
  id: number;
  title: string;
  path: string;
}

interface Message {
  role: "user" | "assistant";
  text: string;
  sources: Source[];
}

export function ChatWidget() {
  const t = useTranslations("chat");
  const locale = useLocale();
  const inputId = useId();
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateAnswer(change: (answer: Message) => Message) {
    setMessages((current) => [...current.slice(0, -1), change(current[current.length - 1])]);
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (text.length < 3 || busy) return;
    setQuestion("");
    setError(null);
    setBusy(true);
    setMessages((current) => [
      ...current,
      { role: "user", text, sources: [] },
      { role: "assistant", text: "", sources: [] },
    ]);

    try {
      const response = await fetch(`${API_URL}/assistant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text, locale }),
      });
      if (!response.ok) {
        setError(response.status === 429 ? t("rateLimited") : t("error"));
        return;
      }
      for await (const { event: type, data } of readSse(response)) {
        if (type === "delta") {
          const delta = (data as { text: string }).text;
          updateAnswer((answer) => ({ ...answer, text: answer.text + delta }));
        } else if (type === "done") {
          const sources = (data as { sources: Source[] }).sources;
          updateAnswer((answer) => ({ ...answer, sources }));
        } else if (type === "error") {
          setError((data as { message: string }).message);
        }
      }
    } catch {
      setError(t("error"));
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        className="btn fixed bottom-4 right-4 shadow-lg"
        onClick={() => setOpen(true)}
      >
        {t("open")}
      </button>
    );
  }

  return (
    <section
      aria-label={t("title")}
      className="fixed bottom-4 right-4 flex max-h-[80vh] w-[min(24rem,calc(100vw-2rem))] flex-col rounded-lg border border-slate-300 bg-white shadow-xl"
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="text-base">{t("title")}</h2>
        <button type="button" className="text-sm text-brand underline" onClick={() => setOpen(false)}>
          {t("close")}
        </button>
      </div>
      <p className="px-4 pt-3 text-xs text-slate-600">{t("disclaimer")}</p>
      {/* The answer is rendered as plain text: model output is never treated as HTML. */}
      <ol aria-live="polite" className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm">
        {messages.map((message, index) => (
          <li key={index}>
            <p className="font-medium text-slate-900">
              {message.role === "user" ? t("you") : t("assistant")}
            </p>
            <p className="whitespace-pre-wrap text-slate-800">{message.text}</p>
            {message.sources.length > 0 && (
              <div className="mt-1">
                <p className="text-xs font-medium text-slate-700">{t("sources")}</p>
                <ul className="text-xs">
                  {message.sources.map((source) => (
                    <li key={source.id}>
                      [{source.id}]{" "}
                      <a href={source.path} className="text-brand underline">
                        {source.title}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </li>
        ))}
      </ol>
      {error && (
        <p role="alert" className="px-4 pb-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <form onSubmit={ask} className="flex gap-2 border-t border-slate-200 p-3">
        <div className="flex-1">
          <label htmlFor={inputId} className="sr-only">
            {t("label")}
          </label>
          <input
            id={inputId}
            className="input"
            value={question}
            maxLength={500}
            placeholder={t("placeholder")}
            onChange={(event) => setQuestion(event.target.value)}
          />
        </div>
        <button type="submit" className="btn" disabled={busy}>
          {t("send")}
        </button>
      </form>
    </section>
  );
}
