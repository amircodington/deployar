import type { Metadata } from "next";
import "./globals.css";

// No next/font/google: nothing may load from outside Iran at runtime (CLAUDE.md rule 5). Brand fonts land in B-07.
export const metadata: Metadata = {
  title: "دیپلویار",
  description: "دستیار استقرار و پایش برنامه روی لیارا",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fa" dir="rtl" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
