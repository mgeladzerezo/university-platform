import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import { fetchPublic } from "@/lib/api/server";
import type { Faculty } from "@/lib/api/types";

export async function generateMetadata() {
  const t = await getTranslations("nav");
  return { title: t("faculties") };
}

export default async function FacultiesPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations();
  const faculties = (await fetchPublic<Faculty[]>("/faculties", { locale })) ?? [];

  return (
    <div className="space-y-6">
      <h1>{t("nav.faculties")}</h1>
      {faculties.length === 0 && <p>{t("common.empty")}</p>}
      <ul className="grid gap-4 md:grid-cols-2">
        {faculties.map((faculty) => (
          <li key={faculty.id} className="card">
            <h2>{faculty.name}</h2>
            <p className="mt-2 text-slate-700">{faculty.description}</p>
            <Link
              href={{ pathname: "/programs", query: { faculty: faculty.slug } }}
              className="mt-3 inline-block text-sm text-brand underline"
            >
              {t("nav.programs")}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
