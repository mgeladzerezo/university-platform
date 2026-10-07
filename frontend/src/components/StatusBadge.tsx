const TONES = {
  neutral: "bg-slate-200 text-slate-900",
  progress: "bg-amber-100 text-amber-900",
  positive: "bg-green-100 text-green-900",
  negative: "bg-red-100 text-red-900",
} as const;

const STATUS_TONES: Record<string, keyof typeof TONES> = {
  submitted: "progress",
  under_review: "progress",
  in_review: "progress",
  pending_scan: "progress",
  waitlisted: "progress",
  accepted: "positive",
  published: "positive",
  clean: "positive",
  enrolled: "positive",
  rejected: "negative",
  infected: "negative",
};

/** The label carries the meaning; colour is only a secondary cue. */
export function StatusBadge({ status, label }: { status: string; label: string }) {
  const tone = TONES[STATUS_TONES[status] ?? "neutral"];
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${tone}`}>{label}</span>
  );
}
