import type { Metadata } from "next";
import "./globals.css";
import PwaEnable from "../components/PwaEnable";

export const metadata: Metadata = {
  title: "March Forecast | College Basketball Modeling",
  manifest: "/March-Madness-Forecasting/manifest.webmanifest",
  applicationName: "March Forecast",
  appleWebApp: {capable:true,title:"March Forecast",statusBarStyle:"black-translucent"},
  icons: {icon:"/March-Madness-Forecasting/icon.svg"},
  description: "Explore transparent college basketball team ratings, neutral-site matchup projections, and tournament simulations.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><PwaEnable/>{children}</body>
    </html>
  );
}
