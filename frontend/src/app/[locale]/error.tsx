"use client";

import { useTranslations } from "next-intl";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  const t = useTranslations("common");
  return (
    <div role="alert" className="space-y-4">
      <p>{t("error")}</p>
      <button type="button" className="btn" onClick={reset}>
        {t("back")}
      </button>
    </div>
  );
}
