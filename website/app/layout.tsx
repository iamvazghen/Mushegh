import type { Metadata } from "next";
import { Bricolage_Grotesque, IBM_Plex_Mono, Instrument_Sans } from "next/font/google";
import "./globals.css";
import Sidebar from "./_nav";

const sans = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});
const displayFont = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://mushegh.vercel.app"),
  title: "Mushegh — an open-source, voice-first AI assistant you install and talk to",
  description:
    "Mushegh (Modular Universal Synthetic Hyper Engine General Hub) is an open-source, ready-to-install, voice-first AI assistant. Local-first, self-hosted, no GPU required.",
  // The opaque tile, not /logo.png: the mark is white-on-transparent, which is
  // invisible in a browser tab on light chrome.
  icons: { icon: "/icon.png", apple: "/icon.png" },
  openGraph: {
    title: "Mushegh",
    description:
      "An open-source, ready-to-install, voice-first AI assistant. Local-first, self-hosted.",
    // og.png, not banner.png: the wordmark is white-on-transparent and scrapers
    // have no reliable answer for a transparent image.
    images: ["/og.png"],
    type: "website",
  },
  twitter: { card: "summary_large_image", images: ["/og.png"] },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${displayFont.variable} ${mono.variable}`}>
      <body>
        <div className="layout">
          <Sidebar />
          <main className="content">
            <div className="inner">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
