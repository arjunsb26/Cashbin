import localFont from "next/font/local";

// Local woff2 files, committed next to this module, so the build and the venue
// never need the network. OFL.txt in the same folder carries the licence.
export const plexSans = localFont({
  src: [
    { path: "./fonts/ibm-plex-sans-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "./fonts/ibm-plex-sans-latin-500-normal.woff2", weight: "500", style: "normal" },
    { path: "./fonts/ibm-plex-sans-latin-600-normal.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-plex-sans",
  display: "swap",
});

export const plexCondensed = localFont({
  src: [
    {
      path: "./fonts/ibm-plex-sans-condensed-latin-400-normal.woff2",
      weight: "400",
      style: "normal",
    },
    {
      path: "./fonts/ibm-plex-sans-condensed-latin-600-normal.woff2",
      weight: "600",
      style: "normal",
    },
  ],
  variable: "--font-plex-condensed",
  display: "swap",
});
