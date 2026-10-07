export function formatDate(iso: string | null | undefined, locale: string): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: "Europe/Warsaw" }).format(
    new Date(iso),
  );
}

export function formatDateTime(iso: string | null | undefined, locale: string): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "long",
    timeStyle: "short",
    timeZone: "Europe/Warsaw",
  }).format(new Date(iso));
}

/** "08:15:00" -> "08:15" */
export function formatTime(time: string): string {
  return time.slice(0, 5);
}
