import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Outfit } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const outfit = Outfit({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-outfit",
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
      className={`dark ${inter.variable} ${outfit.variable}`}
    >
      <body className="bg-void text-ink min-h-screen antialiased">
        {/* removed full-screen background */}
        <div className="fixed inset-0 -z-10 bg-grid pointer-events-none" />
        <Sidebar />
        <main className="min-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}
