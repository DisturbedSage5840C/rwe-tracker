import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Providers } from "@/app/providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "RWE Perception Tracker",
  description: "Quantify trial-claim versus real-world perception gaps.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
