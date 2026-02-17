import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

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
    default: "ParliamentRAG — Analisi AI dei Dibattiti Parlamentari Italiani",
    template: "%s | ParliamentRAG",
  },
  description:
    "Esplora i dibattiti della Camera dei Deputati con l'intelligenza artificiale. Ricerca atti, confronta posizioni politiche e visualizza il posizionamento ideologico dei gruppi parlamentari su qualsiasi tema.",
  keywords: [
    "parlamento italiano",
    "camera dei deputati",
    "dibattiti parlamentari",
    "atti parlamentari",
    "analisi politica",
    "RAG",
    "retrieval augmented generation",
    "intelligenza artificiale",
    "NLP",
    "posizionamento politico",
    "compasso ideologico",
    "gruppi parlamentari",
    "interventi parlamentari",
  ],
  authors: [{ name: "Mirko Tritella" }],
  openGraph: {
    title: "ParliamentRAG — Analisi AI dei Dibattiti Parlamentari Italiani",
    description:
      "Esplora i dibattiti della Camera dei Deputati con l'intelligenza artificiale. Ricerca atti, confronta posizioni e visualizza il posizionamento ideologico dei gruppi parlamentari.",
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="it" className="light" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-white text-gray-900`}
      >
        <TooltipProvider delayDuration={0}>
          {children}
        </TooltipProvider>
      </body>
    </html>
  );
}
