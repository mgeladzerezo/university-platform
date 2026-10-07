import { getTranslations } from "next-intl/server";

import { fetchPublic } from "@/lib/api/server";
import type { Program } from "@/lib/api/types";

const LEVELS = ["bachelor", "master", "doctoral"] as const;

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string; level?: string; faculty?: string }>;
}

export async function generateMetadata() {
  const t = await getTranslations("programs");
  return { title: t("title") };
}

export default async function ProgramsPage({ params, searchParams }: Props) {
  const { locale } = await params;
  const { q, level, faculty } = await searchParams;
  const t = await getTranslations();
  const programs = (await fetchPublic<Program[]>("/programs", { locale, q, level, faculty })) ?? [];

  return (
    <div className="space-y-6">
      <h1>{t("programs.title")}</h1>

      {/* A plain GET form: search works without JavaScript and the URL is shareable. */}
      <form role="search" className="card flex flex-wrap items-end gap-4">
        {faculty && <input type="hidden" name="faculty" value={faculty} />}
        <div className="min-w-56 flex-1">
          <label htmlFor="program-q" className="label">
            {t("programs.searchLabel")}
          </label>
          <input id="program-q" name="q" type="search" defaultValue={q} className="input" />
        </div>
        <div>
          <label htmlFor="program-level" className="label">
            {t("programs.level")}
          </label>
          <select id="program-level" name="level" defaultValue={level ?? ""} className="input">
            <option value="">{t("programs.allLevels")}</option>
            {LEVELS.map((value) => (
              <option key={value} value={value}>
                {t(`programs.${value}`)}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className="btn">
          {t("common.search")}
        </button>
      </form>

      <p role="status" className="text-sm text-slate-700">
        {t("programs.results", { count: programs.length })}
      </p>
      <ul className="grid gap-4 md:grid-cols-2">
        {programs.map((program) => (
          <li key={program.id} className="card">
            <h2>{program.name}</h2>
            <p className="text-sm text-slate-600">{program.faculty_name}</p>
            <p className="mt-2 text-slate-700">{program.description}</p>
            <p className="mt-3 text-sm text-slate-700">
              {t(`programs.${program.degree_level}`)} · {t(`programs.${program.mode}`)} ·{" "}
              {t("programs.semesters", { count: program.semesters })} ·{" "}
              {t("programs.taughtIn", { language: program.teaching_language.toUpperCase() })}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
