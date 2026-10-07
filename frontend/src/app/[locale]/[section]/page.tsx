import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { ContentList } from "@/components/ContentViews";
import { fetchPublic } from "@/lib/api/server";
import type { ContentKind, PublicContent } from "@/lib/api/types";

// /news and /events share this listing; other sections have their own folders.
const LISTED: Record<string, ContentKind> = { news: "news", events: "event" };

interface Props {
  params: Promise<{ locale: string; section: string }>;
}

export async function generateMetadata({ params }: Props) {
  const { section } = await params;
  if (!(section in LISTED)) return {};
  const t = await getTranslations("nav");
  return { title: t(section) };
}

export default async function ContentListPage({ params }: Props) {
  const { locale, section } = await params;
  const kind = LISTED[section];
  if (!kind) notFound();
  const t = await getTranslations();
  const items = await fetchPublic<PublicContent[]>("/content", { kind, locale, limit: 50 });

  return (
    <div className="space-y-6">
      <h1>{t(`nav.${section}`)}</h1>
      <ContentList items={items ?? []} locale={locale} emptyText={t("common.empty")} />
    </div>
  );
}
