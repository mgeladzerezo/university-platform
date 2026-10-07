import { getTranslations } from "next-intl/server";

import { fetchPublic } from "@/lib/api/server";
import type { StaffMember } from "@/lib/api/types";

interface Props {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string }>;
}

export async function generateMetadata() {
  const t = await getTranslations("staff");
  return { title: t("title") };
}

export default async function StaffPage({ params, searchParams }: Props) {
  const { locale } = await params;
  const { q } = await searchParams;
  const t = await getTranslations();
  const staff = (await fetchPublic<StaffMember[]>("/staff", { locale, q })) ?? [];

  return (
    <div className="space-y-6">
      <h1>{t("staff.title")}</h1>
      <form role="search" className="card flex flex-wrap items-end gap-4">
        <div className="min-w-56 flex-1">
          <label htmlFor="staff-q" className="label">
            {t("staff.searchLabel")}
          </label>
          <input id="staff-q" name="q" type="search" defaultValue={q} className="input" />
        </div>
        <button type="submit" className="btn">
          {t("common.search")}
        </button>
      </form>

      {staff.length === 0 ? (
        <p>{t("common.empty")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse bg-white text-left text-sm">
            <caption className="sr-only">{t("staff.title")}</caption>
            <thead>
              <tr className="border-b border-slate-300">
                <th scope="col" className="p-3">{t("staff.name")}</th>
                <th scope="col" className="p-3">{t("staff.position")}</th>
                <th scope="col" className="p-3">{t("staff.faculty")}</th>
                <th scope="col" className="p-3">{t("staff.contact")}</th>
              </tr>
            </thead>
            <tbody>
              {staff.map((person) => (
                <tr key={person.id} className="border-b border-slate-200">
                  <th scope="row" className="p-3 font-medium">
                    {person.academic_title} {person.full_name}
                  </th>
                  <td className="p-3">{person.position}</td>
                  <td className="p-3">{person.faculty_name}</td>
                  <td className="p-3">
                    <a href={`mailto:${person.email}`} className="text-brand underline">
                      {person.email}
                    </a>
                    {person.phone && <span className="block">{person.phone}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
