import { getTranslations } from "next-intl/server";

import { ContentList } from "@/components/ContentViews";
import { Link } from "@/i18n/navigation";
import { fetchPublic } from "@/lib/api/server";
import type { PublicContent } from "@/lib/api/types";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations();
  const [news, events] = await Promise.all([
    fetchPublic<PublicContent[]>("/content", { kind: "news", locale, limit: 3 }),
    fetchPublic<PublicContent[]>("/content", { kind: "event", locale, limit: 3 }),
  ]);

  return (
    <div className="space-y-10">
      <section aria-labelledby="hero-title" className="rounded-lg bg-brand px-6 py-10 text-white">
        <h1 id="hero-title" className="text-white">
          {t("site.name")}
        </h1>
        <p className="mt-2 max-w-2xl text-lg">{t("site.tagline")}</p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/programs" className="btn-secondary">
            {t("nav.programs")}
          </Link>
          <Link href="/portal/admissions" className="btn-secondary">
            {t("home.apply")}
          </Link>
        </div>
      </section>

      <section aria-labelledby="news-title">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 id="news-title">{t("home.latestNews")}</h2>
          <Link href="/news" className="text-sm text-brand underline">
            {t("home.allNews")}
          </Link>
        </div>
        <ContentList items={news ?? []} locale={locale} emptyText={t("common.empty")} />
      </section>

      <section aria-labelledby="events-title">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 id="events-title">{t("home.upcomingEvents")}</h2>
          <Link href="/events" className="text-sm text-brand underline">
            {t("home.allEvents")}
          </Link>
        </div>
        <ContentList items={events ?? []} locale={locale} emptyText={t("common.empty")} />
      </section>
    </div>
  );
}
