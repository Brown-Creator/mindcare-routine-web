import type { Metadata } from "next";
import "./globals.css";
import NavWrapper from "@/components/nav-wrapper";

export const metadata: Metadata = {
  title: "MindCare Routine - 근거 기반 마음관리 루틴",
  description: "한국 성인을 위한 CBT 사고 기록, 마음챙김, 행동활성화 및 성찰 저널 셀프헬프 도구",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-[#f8faf7]">
        <NavWrapper>{children}</NavWrapper>
      </body>
    </html>
  );
}
