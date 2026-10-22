import type { Metadata, Viewport } from "next";
import "./globals.css";

// Fonts are self-hosted from /public/fonts: nothing may load from outside Iran at runtime (rule 5).
export const metadata: Metadata = {
  title: "دیپلویار",
  description: "همکار فنی تو روی لیارا: آنلاین کردن و سالم نگه‌داشتن اپ، با تأیید تو",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0e0d10" },
    { media: "(prefers-color-scheme: light)", color: "#f4f2ee" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fa" dir="rtl" className="h-full antialiased">
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
