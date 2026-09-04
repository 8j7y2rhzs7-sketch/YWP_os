import type { Metadata } from "next";
import { Bebas_Neue, Manrope } from "next/font/google";

import "./globals.css";

const display = Bebas_Neue({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-display",
});

const body = Manrope({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "YWP OS · Decision Engine",
  description:
    "Discipline. Data. Edge. Live protocol sweeps and lock-checked tickets.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${body.variable}`}>{children}</body>
    </html>
  );
}
