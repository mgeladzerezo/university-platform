import { notFound } from "next/navigation";

import { ContentArticle } from "@/components/ContentViews";
import { fetchPublic } from "@/lib/api/server";
import type { ContentKind, PublicContent } from "@/lib/api/types";

const KINDS: Record<string, ContentKind> = { news: "news", events: "event", pages: "page" };

interface Props {
  params: Promise<{ locale: string; section: string; slug: string }>;
}

async function load({ params }: Props): Promise<{ item: PublicContent | null; locale: string }> {
  const { locale, section, slug } = await params;
  const kind = KINDS[section];
  if (!kind) return { item: null, locale };
  const item = await fetchPublic<PublicContent>(`/content/${kind}/${encodeURIComponent(slug)}`, {
    locale,
  });
  return { item, locale };
}

export async function generateMetadata(props: Props) {
  const { item } = await load(props);
  return item ? { title: item.title, description: item.summary } : {};
}

export default async function ContentPage(props: Props) {
  const { item, locale } = await load(props);
  if (!item) notFound();
  return <ContentArticle item={item} locale={locale} />;
}
