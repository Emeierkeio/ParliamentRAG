import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { NextIntlClientProvider } from 'next-intl';
import { getMessages, getLocale } from 'next-intl/server';
import { getTranslations } from 'next-intl/server';
import "./globals.css";

// ─── Maintenance mode ────────────────────────────────────────────────────────
// Change to true to show the maintenance page. Restart Next.js after changing. MANUTENZIONE SETTA QUI!
const MAINTENANCE_MODE = false;

async function MaintenancePage() {
  const t = await getTranslations('Maintenance');
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-white text-gray-900 px-6">
      <div className="max-w-md text-center space-y-6">
        <div className="text-6xl">🔧</div>
        <h1 className="text-3xl font-semibold tracking-tight">{t('title')}</h1>
        <p className="text-gray-500 text-base leading-relaxed">
          {t('description')}
        </p>
        <p className="text-gray-400 text-sm">ParliamentRAG</p>
      </div>
    </div>
  );
}

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
};

export const metadata: Metadata = {
  title: {
    default: "ParliamentRAG",
    template: "%s | ParliamentRAG",
  },
  description:
    "Esplora i dibattiti della Camera dei Deputati con. Ricerca atti, confronta posizioni politiche e visualizza il posizionamento ideologico dei gruppi parlamentari su qualsiasi tema.",
  keywords: [
    "parlamento italiano",
    "camera dei deputati",
    "dibattiti parlamentari",
    "atti parlamentari",
    "analisi politica",
    "RAG",
    "retrieval augmented generation",
    "NLP",
    "posizionamento politico",
    "compasso ideologico",
    "gruppi parlamentari",
    "interventi parlamentari",
  ],
  authors: [{ name: "Mirko Tritella" }],
  openGraph: {
    title: "ParliamentRAG",
    description:
      "Esplora i dibattiti della Camera dei Deputati. Ricerca atti, confronta posizioni e visualizza il posizionamento ideologico dei gruppi parlamentari.",
    siteName: "ParliamentRAG",
    locale: "it_IT",
    type: "website",
  },
  robots: {
    index: true,
    follow: true,
  },
  icons: {
    icon: "/favicon.svg",
  },
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale} className="light" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-white text-gray-900`}
      >
        {MAINTENANCE_MODE ? (
          <MaintenancePage />
        ) : (
          <NextIntlClientProvider messages={messages} locale={locale}>
            <TooltipProvider delayDuration={0}>
              {children}
            </TooltipProvider>
          </NextIntlClientProvider>
        )}
      </body>
    </html>
  );
}
