import type { MetadataRoute } from "next";
import { brand } from "@/lib/brand";
import { token } from "@/lib/tokens.server";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: brand.name,
    short_name: brand.short_name,
    description: brand.tagline,
    start_url: "/",
    display: "standalone",
    background_color: token("paper"),
    theme_color: token("paper"),
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
