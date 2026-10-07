import { Link } from "@/i18n/navigation";
import type { PublicContent } from "@/lib/api/types";
import { formatDate, formatDateTime } from "@/lib/format";

const PATHS = { page: "pages", news: "news", event: "events" } as const;

function contentDate(item: PublicContent, locale: string): string {
  return item.kind === "event"
    ? formatDateTime(item.event_starts_at, locale)
    : formatDate(item.published_at, locale);
}

export function ContentList({
  items,
  locale,
  emptyText,
}: {
  items: PublicContent[];
  locale: string;
  emptyText: string;
}) {
  if (items.length === 0) return <p>{emptyText}</p>;
  return (
    <ul className="space-y-4">
      {items.map((item) => (
        <li key={item.id} className="card">
          <p className="text-sm text-slate-600">
            <time dateTime={(item.event_starts_at ?? item.published_at) ?? undefined}>
              {contentDate(item, locale)}
            </time>
            {item.event_location ? ` · ${item.event_location}` : ""}
          </p>
          <h3 className="text-lg font-semibold">
            <Link href={`/${PATHS[item.kind]}/${item.slug}`} className="text-brand hover:underline">
              {item.title}
            </Link>
          </h3>
          {item.summary && <p className="mt-1 text-slate-700">{item.summary}</p>}
        </li>
      ))}
    </ul>
  );
}

export function ContentArticle({ item, locale }: { item: PublicContent; locale: string }) {
  return (
    <article className="max-w-3xl">
      <h1>{item.title}</h1>
      {item.kind !== "page" && (
        <p className="mt-2 text-sm text-slate-600">
          {contentDate(item, locale)}
          {item.event_location ? ` · ${item.event_location}` : ""}
        </p>
      )}
      {item.summary && <p className="mt-4 text-lg text-slate-700">{item.summary}</p>}
      {/* body_html is sanitised by the API (allow-list of tags) when editors save it. */}
      <div className="rich-text mt-6" dangerouslySetInnerHTML={{ __html: item.body_html }} />
    </article>
  );
}
