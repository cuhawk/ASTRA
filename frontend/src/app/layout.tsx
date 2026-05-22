import type { Metadata } from "next";
import "./globals.css";
import { TopNav } from "@/components/TopNav";

export const metadata: Metadata = {
  title: "ASTRA",
  description: "BloodHound for JavaScript web apps.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-zinc-950 text-zinc-100 min-h-screen font-sans">
        <TopNav />
        <main className="max-w-[960px] mx-auto p-6">{children}</main>
      </body>
    </html>
  );
}
