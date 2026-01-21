import type { Metadata, Viewport } from "next";
import "./globals.css";
import MSWComponent from "@/components/msw-component";
import QueryProvider from "@/components/query-provider";
import { AppShell } from "@/components/layout/app-shell";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/toaster";

export const metadata: Metadata = {
  title: "SynapseAutomation - 矩阵发布控制台",
  description: "Synapse Engine · 多平台矩阵调度中心",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "SynapseAutomation",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <meta name="referrer" content="no-referrer"/>
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="format-detection" content="telephone=no" />
      </head>
      <body className="antialiased">
        <ThemeProvider attribute="class" defaultTheme="dark">
          <MSWComponent />
          <QueryProvider>
            <AppShell>{children}</AppShell>
            <Toaster />
          </QueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
