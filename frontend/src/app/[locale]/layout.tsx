import "../globals.css";

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { ChatWidget } from "@/components/ChatWidget";
import { Providers } from "@/components/Providers";
import { SiteHeader } from "@/components/SiteHeader";
import { routing } from "@/i18n/routing";

interface Props {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const t = await getTranslations({ locale, namespace: "site" });
  return { title: { default: t("name"), template: `%s | ${t("name")}` }, description: t("tagline") };
}

export default async function LocaleLayout({ children, params }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  const t = await getTranslations("site");

  return (
    <html lang={locale}>
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <NextIntlClientProvider>
          <Providers>
            <a
              href="#main"
              className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:bg-white focus:px-3 focus:py-2"
            >
              {t("skip")}
            </a>
            <SiteHeader />
            <main id="main" className="mx-auto max-w-6xl px-4 py-8">
              {children}
            </main>
            <footer className="border-t border-slate-200 bg-white">
              <p className="mx-auto max-w-6xl px-4 py-6 text-sm text-slate-700">{t("footer")}</p>
            </footer>
            <ChatWidget />
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
