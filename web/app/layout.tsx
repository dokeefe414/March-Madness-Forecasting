import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "March Forecast | College Basketball Modeling",
  description: "Explore transparent college basketball team ratings, neutral-site matchup projections, and tournament simulations.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
