import type { Metadata, Viewport } from "next";
import "./globals.css";
import { plexCondensed, plexSans } from "./fonts";
import { Providers } from "@/components/Providers";
import { Rail } from "@/components/Rail";
import { ServiceWorker } from "@/components/ServiceWorker";
import { brand } from "@/lib/brand";
import { token } from "@/lib/tokens.server";

export const metadata: Metadata = {
  title: brand.name,
  description: brand.tagline,
  applicationName: brand.name,
  appleWebApp: { capable: true, title: brand.short_name, statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: token("paper"),
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${plexSans.variable} ${plexCondensed.variable}`}>
      <body>
        <Providers>
          <div className="flex min-h-dvh">
            <Rail />
            <main className="min-w-0 flex-1 px-[var(--gutter)] py-6">{children}</main>
          </div>
          <ServiceWorker />
        </Providers>
      </body>
    </html>
  );
}
