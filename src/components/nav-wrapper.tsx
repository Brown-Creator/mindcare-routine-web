"use client";

import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";
import { localDB } from "@/lib/local-storage";
import { 
  Heart, 
  Home, 
  Calendar, 
  BookOpen, 
  Smile, 
  Sparkles, 
  ShieldAlert, 
  Settings as SettingsIcon,
  Activity
} from "lucide-react";

export default function NavWrapper({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [hasConsent, setHasConsent] = useState<boolean>(true);

  // 온보딩 및 위기 체크
  useEffect(() => {
    if (typeof window !== "undefined") {
      // 1. 위기 이벤트 발생 여부 검사 (가장 최우선 순위)
      const events = localDB.getSafetyEvents();
      const phqResults = localDB.getScreeningResults();
      const lastPhq = phqResults[0];
      const hasCrisis = events.length > 0 || (lastPhq && lastPhq.type === "PHQ-9" && lastPhq.answers[8] > 0);
      
      if (hasCrisis && pathname !== "/crisis") {
        router.push("/crisis");
        return;
      }

      // 2. 온보딩 동의 완료 여부 검사
      const consent = localDB.getConsent();
      if (!consent && pathname !== "/" && pathname !== "/onboarding" && pathname !== "/crisis") {
        setHasConsent(false);
        router.push("/onboarding");
      } else {
        setHasConsent(true);
      }
    }
  }, [pathname, router]);

  // 네비게이션 노출 예외 페이지
  const isNoNavPage = pathname === "/" || pathname === "/onboarding" || pathname === "/crisis";

  if (isNoNavPage) {
    return <main className="flex-1 w-full">{children}</main>;
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#f8faf7]">
      {/* 상단 헤더 */}
      <header className="sticky top-0 z-40 w-full border-b border-[#e4e7e3] bg-white/80 backdrop-blur-md">
        <div className="max-w-md mx-auto px-4 h-14 flex items-center justify-between">
          <Link href="/dashboard" className="flex items-center gap-2">
            <Heart className="w-5 h-5 text-[#4a6c4c] fill-[#4a6c4c]" />
            <span className="font-semibold text-lg text-[#1e291b] tracking-tight">MindCare Routine</span>
          </Link>
          <div className="flex items-center gap-2">
            <Link 
              href="/privacy" 
              className="p-2 hover:bg-[#eaf2eb] rounded-full text-[#4a6c4c] transition-colors"
              title="설정 및 개인정보"
            >
              <SettingsIcon className="w-5 h-5" />
            </Link>
            <Link 
              href="/crisis" 
              className="px-2.5 py-1 text-xs font-semibold bg-red-50 text-red-600 rounded-full border border-red-100 flex items-center gap-1 hover:bg-red-100 transition-colors"
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              위기도움
            </Link>
          </div>
        </div>
      </header>

      {/* 메인 콘텐츠 영역 (모바일 최적화 컨테이너) */}
      <main className="flex-1 w-full max-w-md mx-auto px-4 py-6 pb-24">
        {children}
      </main>

      {/* 하단 모바일 탭 바 */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white border-t border-[#e4e7e3] calm-shadow">
        <div className="max-w-md mx-auto flex items-center justify-around h-16 px-2">
          <Link 
            href="/dashboard" 
            className={`flex flex-col items-center justify-center flex-1 h-full text-xs transition-colors ${
              pathname === "/dashboard" ? "text-[#4a6c4c] font-medium" : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <Home className="w-5 h-5 mb-1" />
            홈
          </Link>

          <Link 
            href="/check-in" 
            className={`flex flex-col items-center justify-center flex-1 h-full text-xs transition-colors ${
              pathname === "/check-in" ? "text-[#4a6c4c] font-medium" : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <Smile className="w-5 h-5 mb-1" />
            체크인
          </Link>

          <Link 
            href="/cbt" 
            className={`flex flex-col items-center justify-center flex-1 h-full text-xs transition-colors ${
              pathname.startsWith("/cbt") ? "text-[#4a6c4c] font-medium" : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <BookOpen className="w-5 h-5 mb-1" />
            CBT기록
          </Link>

          <Link 
            href="/activation" 
            className={`flex flex-col items-center justify-center flex-1 h-full text-xs transition-colors ${
              pathname === "/activation" ? "text-[#4a6c4c] font-medium" : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <Activity className="w-5 h-5 mb-1" />
            행동활성
          </Link>

          <Link 
            href="/mindfulness" 
            className={`flex flex-col items-center justify-center flex-1 h-full text-xs transition-colors ${
              pathname === "/mindfulness" ? "text-[#4a6c4c] font-medium" : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <Sparkles className="w-5 h-5 mb-1" />
            명상
          </Link>

          <Link 
            href="/journal" 
            className={`flex flex-col items-center justify-center flex-1 h-full text-xs transition-colors ${
              pathname === "/journal" ? "text-[#4a6c4c] font-medium" : "text-gray-400 hover:text-gray-600"
            }`}
          >
            <Calendar className="w-5 h-5 mb-1" />
            성찰일기
          </Link>
        </div>
      </nav>
    </div>
  );
}
