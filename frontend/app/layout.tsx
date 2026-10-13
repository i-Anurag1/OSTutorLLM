import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "OSTutor - grounded Operating Systems tutor",
  description: "An Operating Systems tutor whose answers cite your course material, with simulators, labs and assessments.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

const themeScript = "try{var t=localStorage.getItem('ostutor.theme');if(t){document.documentElement.dataset.theme=t}}catch(e){}";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      <body>{children}</body>
    </html>
  );
}
