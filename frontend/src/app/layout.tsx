import type { Metadata } from "next";
import { Geist, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

const geist = Geist({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-geist",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "ASTRA · callgraph observatory",
  description:
    "BloodHound for JavaScript web apps. Drop a URL, see the callgraph.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`dark ${geist.variable} ${jetbrains.variable}`}
    >
      <body className="bg-void text-ink min-h-screen antialiased">
        <div className="fixed inset-0 -z-10 bg-grid pointer-events-none" />
        <Sidebar />
        <main className="md:pl-60">{children}</main>
      </body>
    </html>
  );
}
