import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "دیپلویار",
    short_name: "دیپلویار",
    description: "همکار فنی تو روی لیارا: آنلاین کردن و سالم نگه‌داشتن اپ، با تأیید تو",
    lang: "fa",
    dir: "rtl",
    start_url: "/",
    display: "standalone",
    background_color: "#0e0d10",
    theme_color: "#0e0d10",
    icons: [{ src: "/icon.png", sizes: "512x512", type: "image/png" }],
  };
}
