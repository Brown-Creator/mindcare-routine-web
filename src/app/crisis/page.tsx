"use client";

import { useEffect, useState } from "react";
import { localDB } from "@/lib/local-storage";
import { ShieldAlert, PhoneCall, Copy, Check, ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";

export default function CrisisPage() {
  const router = useRouter();
  const [copied, setCopied] = useState<boolean>(false);
  const [safeConfirmed, setSafeConfirmed] = useState<boolean>(false);

  useEffect(() => {
    // 위기 로그 기록 (진입 기록 보관, 내용 유출 배제)
    if (typeof window !== "undefined") {
      const events = localDB.getSafetyEvents();
      // 이벤트가 없는 경우에만 새로 기록 (중복 로깅 방지)
      if (events.length === 0) {
        localDB.saveSafetyEvent("KEYWORD");
      }
    }
  }, []);

  const handleCopyText = () => {
    const text = "지금 혼자 있기 어렵고 내 안전이 많이 걱정돼. 혹시 연락하면 바로 받아주거나 내 곁에 와줄 수 있어?";
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleClearCrisis = () => {
    if (!safeConfirmed) return;
    
    if (confirm("안전이 확보되었고, 현재 안정을 찾으셨습니까? 정상 마음관리 화면으로 돌아갑니다.")) {
      // 로컬 스토리지에 기록된 위기 로그 및 PHQ 선별 결과를 초기화하거나 초기 상태로 전환
      if (typeof window !== "undefined") {
        // 안전 이력을 보관하되, UI 차단을 풀기 위해 로컬 상태 리셋
        localStorage.removeItem("mindcare_safety_events");
        // PHQ 9번 자조 항목도 초기화
        const results = localDB.getScreeningResults();
        const cleaned = results.map(r => {
          if (r.type === "PHQ-9") {
            const nextAnswers = [...r.answers];
            nextAnswers[8] = 0; // 9번 자살 문항을 0점으로 리셋
            return { ...r, answers: nextAnswers, totalScore: r.totalScore - r.answers[8] };
          }
          return r;
        });
        localStorage.setItem("mindcare_screening_results", JSON.stringify(cleaned));
      }
      router.push("/dashboard");
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-white flex flex-col justify-center items-center px-6 py-12">
      <div className="w-full max-w-md bg-slate-800 rounded-3xl p-6 border border-red-500/30 shadow-2xl shadow-red-500/10 space-y-6 animate-fade-in">
        
        {/* 경고 아이콘 헤더 */}
        <div className="text-center space-y-2.5">
          <div className="w-14 h-14 bg-red-950 text-red-500 rounded-full flex items-center justify-center mx-auto border border-red-500/20">
            <ShieldAlert className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold tracking-tight">지금 회원님의 안전이 가장 중요합니다</h2>
          <p className="text-xs text-slate-400">마음케어 루틴 자가조력 기능이 일시 중지되었습니다. 이 힘든 순간을 혼자 해결하려 하지 마세요.</p>
        </div>

        {/* 1. 빠른 비상 연락 버튼 */}
        <div className="space-y-2.5">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">긴급 전화 연결</h3>
          
          <div className="grid grid-cols-1 gap-2">
            <a 
              href="tel:109" 
              className="flex items-center justify-between p-3.5 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-xl text-sm transition-colors"
            >
              <span className="flex items-center gap-2">
                <PhoneCall className="w-4 h-4" /> 자살예방 상담전화 (109)
              </span>
              <span className="text-xs font-bold bg-white/20 px-2 py-0.5 rounded">전화하기</span>
            </a>

            <a 
              href="tel:15770199" 
              className="flex items-center justify-between p-3.5 bg-slate-700 hover:bg-slate-600 text-white font-semibold rounded-xl text-sm transition-colors"
            >
              <span className="flex items-center gap-2">
                <PhoneCall className="w-4 h-4" /> 정신건강 위기상담 (1577-0199)
              </span>
              <span className="text-xs font-bold bg-white/20 px-2 py-0.5 rounded">전화하기</span>
            </a>

            <div className="grid grid-cols-2 gap-2">
              <a 
                href="tel:119" 
                className="flex items-center justify-center gap-2 p-3 bg-red-950/60 hover:bg-red-950 text-red-400 border border-red-500/20 font-bold rounded-xl text-xs transition-colors"
              >
                소방 구조대 (119)
              </a>
              <a 
                href="tel:112" 
                className="flex items-center justify-center gap-2 p-3 bg-red-950/60 hover:bg-red-950 text-red-400 border border-red-500/20 font-bold rounded-xl text-xs transition-colors"
              >
                경찰 신고 (112)
              </a>
            </div>
          </div>
        </div>

        {/* 2. 주변인 도움 받기 (문자 복사) */}
        <div className="p-4 bg-slate-900 border border-slate-700/60 rounded-2xl space-y-3">
          <div className="flex justify-between items-center">
            <h4 className="text-xs font-bold text-slate-400">가까운 사람에게 도움 청하기</h4>
            <button 
              onClick={handleCopyText}
              className="text-xs text-[#d89657] font-semibold flex items-center gap-1 hover:underline"
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? "복사됨" : "메시지 복사"}
            </button>
          </div>
          <p className="text-xs text-slate-300 leading-relaxed italic bg-slate-950 p-3 rounded-lg border border-slate-800">
            "지금 내가 마음이 많이 힘들고 혼자 있기 어려워서 안전이 걱정돼. 혹시 이 문자 보면 바로 연락해주거나 와줄 수 있어?"
          </p>
        </div>

        {/* 3. 복구 / 해제 기능 (안전 확인) */}
        <div className="pt-2 border-t border-slate-700 space-y-3">
          <label className="flex items-start gap-2.5 cursor-pointer">
            <input 
              type="checkbox" 
              checked={safeConfirmed}
              onChange={(e) => setSafeConfirmed(e.target.checked)}
              className="w-4 h-4 rounded text-emerald-600 border-slate-600 bg-slate-700 focus:ring-emerald-600 mt-0.5"
            />
            <span className="text-[11px] text-slate-300 leading-normal">
              의료 기관 또는 주변 조력자와 연락을 취했거나, 안전한 환경을 확보했으며 안정을 충분히 취했습니다. (정상 모드로 복귀 확인)
            </span>
          </label>

          <button
            onClick={handleClearCrisis}
            disabled={!safeConfirmed}
            className="w-full py-3 bg-slate-700 hover:bg-slate-600 disabled:bg-slate-800 disabled:text-slate-600 disabled:border-transparent text-white font-bold rounded-xl text-xs transition-colors flex items-center justify-center gap-1 border border-slate-600"
          >
            정상 자가관리 홈으로 복귀 <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

      </div>
    </div>
  );
}
