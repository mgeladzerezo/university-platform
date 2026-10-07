"use client";

import { useTranslations } from "next-intl";
import type { FormEvent } from "react";

import type { Application, EducationStep, PersonalStep } from "@/lib/api/types";

interface StepProps<T> {
  application: Application;
  disabled: boolean;
  onSave: (value: T) => void;
}

const PERSONAL_FIELDS: { name: keyof PersonalStep; type?: string; autoComplete?: string }[] = [
  { name: "first_name", autoComplete: "given-name" },
  { name: "last_name", autoComplete: "family-name" },
  { name: "birth_date", type: "date", autoComplete: "bday" },
  { name: "citizenship", autoComplete: "country-name" },
  { name: "phone", type: "tel", autoComplete: "tel" },
  { name: "address_line", autoComplete: "address-line1" },
  { name: "city", autoComplete: "address-level2" },
  { name: "postal_code", autoComplete: "postal-code" },
];

function SaveButton({ disabled }: { disabled: boolean }) {
  const t = useTranslations("common");
  return (
    <button type="submit" className="btn" disabled={disabled}>
      {t("save")}
    </button>
  );
}

export function PersonalForm({ application, disabled, onSave }: StepProps<PersonalStep>) {
  const t = useTranslations("admissions.fields");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    onSave(Object.fromEntries(data) as unknown as PersonalStep);
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        {PERSONAL_FIELDS.map((field) => (
          <div key={field.name}>
            <label htmlFor={field.name} className="label">{t(field.name)}</label>
            <input
              id={field.name}
              name={field.name}
              type={field.type ?? "text"}
              autoComplete={field.autoComplete}
              defaultValue={application.personal?.[field.name] ?? ""}
              required
              disabled={disabled}
              className="input"
            />
          </div>
        ))}
      </div>
      <SaveButton disabled={disabled} />
    </form>
  );
}

export function EducationForm({ application, disabled, onSave }: StepProps<EducationStep>) {
  const t = useTranslations("admissions.fields");
  const education = application.education;
  // Three exam rows cover the usual case; empty rows are not sent.
  const rows = [0, 1, 2].map((index) => education?.exam_results[index]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const subjects = data.getAll("subject").map(String);
    const scores = data.getAll("score").map(String);
    onSave({
      school_name: String(data.get("school_name")),
      graduation_year: Number(data.get("graduation_year")),
      exam_results: subjects
        .map((subject, index) => ({ subject: subject.trim(), score_percent: Number(scores[index]) }))
        .filter((result) => result.subject !== ""),
    });
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <label htmlFor="school_name" className="label">{t("school_name")}</label>
          <input id="school_name" name="school_name" defaultValue={education?.school_name ?? ""} required disabled={disabled} className="input" />
        </div>
        <div>
          <label htmlFor="graduation_year" className="label">{t("graduation_year")}</label>
          <input id="graduation_year" name="graduation_year" type="number" min={1950} max={2100} defaultValue={education?.graduation_year ?? ""} required disabled={disabled} className="input" />
        </div>
      </div>
      {rows.map((row, index) => (
        <fieldset key={index} className="grid gap-4 md:grid-cols-2">
          <legend className="sr-only">{`${t("exam_subject")} ${index + 1}`}</legend>
          <div>
            <label htmlFor={`subject-${index}`} className="label">{t("exam_subject")}</label>
            <input id={`subject-${index}`} name="subject" defaultValue={row?.subject ?? ""} required={index === 0} disabled={disabled} className="input" />
          </div>
          <div>
            <label htmlFor={`score-${index}`} className="label">{t("exam_score")}</label>
            <input id={`score-${index}`} name="score" type="number" min={0} max={100} defaultValue={row?.score_percent ?? ""} required={index === 0} disabled={disabled} className="input" />
          </div>
        </fieldset>
      ))}
      <SaveButton disabled={disabled} />
    </form>
  );
}

export function StatementForm({ application, disabled, onSave }: StepProps<string>) {
  const t = useTranslations("admissions.fields");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave(String(new FormData(event.currentTarget).get("statement")));
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label htmlFor="statement" className="label">{t("statement")}</label>
        <textarea id="statement" name="statement" rows={10} minLength={50} maxLength={5000} defaultValue={application.statement ?? ""} required disabled={disabled} className="input" />
      </div>
      <SaveButton disabled={disabled} />
    </form>
  );
}
