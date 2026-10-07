import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";

export default async function NotFound() {
  const t = await getTranslations();
  return (
    <div className="space-y-4">
      <h1>404</h1>
      <p>{t("common.notFound")}</p>
      <Link href="/" className="text-brand underline">
        {t("nav.home")}
      </Link>
    </div>
  );
}
