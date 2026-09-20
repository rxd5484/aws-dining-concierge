import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dining Concierge",
  description: "Serverless restaurant recommendations powered by AWS",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
