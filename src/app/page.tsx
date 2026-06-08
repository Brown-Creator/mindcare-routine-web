"use client";

import Link from "next/link";
import { Heart, ShieldCheck, Clock, BookOpen, AlertTriangle } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#eaf2eb] to-[#f8faf7] flex flex-col items-center justify-between px-6 py-12">
      {/* 로고 & 헤더 */}
      <div className="w-full max-w-md flex flex-col items-center mt-8 animate-fade-in">
        <div className="w-16 h-16 bg-white rounded-full flex items-center justify-center calm-shadow mb-4">
          <Heart className="w-9 h-9 text-[#4a6c4c] fill-[#4a6c4c]" />
        </div>
        <h1 className="text-3xl font-bold text-[#1e291b] tracking-tight">MindCare Routine</h1>
        <p className="text-sm text-[#4a6c4c] mt-1">한국 성인을 위한 근거 기반 마음관리 루틴</p>
      </div>

      {/* 메인 소개 카드 */}
      <div className="w-full max-w-md bg-white rounded-2xl p-6 calm-shadow border border-[#e4e7e3] space-y-6 my-8 animate-fade-in" style={{ animationDelay: "0.1s" }}>
        <div className="text-center space-y-2">
          <h2 className="text-xl font-bold text-[#1e291b]">오늘 하루, 내 마음은 어땠나요?</h2>
          <p className="text-sm text-gray-500 leading-relaxed">
            바쁜 일상 속 단 3분, 5분, 10분의 과학적으로 증명된 자가 돌봄 루틴(CBT 기록, 마음챙김 명상, 행동활성화)을 통해 마음의 균형을 찾으세요.
          </p>
        </div>

        {/* 핵심 기능 하이라이트 */}
        <div className="grid grid-cols-1 gap-4 text-sm">
          <div className="flex gap-3 items-start">
            <div className="p-1.5 bg-[#eaf2eb] text-[#4a6c4c] rounded-lg mt-0.5">
              <Clock className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-semibold text-[#1e291b]">시간대별 초소형 마음 루틴</h3>
              <p className="text-xs text-gray-500">직장인, 학생의 바쁜 삶에 맞춘 3분~10분 세션</p>
            </div>
          </div>

          <div className="flex gap-3 items-start">
            <div className="p-1.5 bg-[#eaf2eb] text-[#4a6c4c] rounded-lg mt-0.5">
              <BookOpen className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-semibold text-[#1e291b]">CBT 인지행동 및 감정 패턴 성찰</h3>
              <p className="text-xs text-gray-500">부정적 사고 회로를 걷어내는 체계적인 글쓰기 연습</p>
            </div>
          </div>

          <div className="flex gap-3 items-start">
            <div className="p-1.5 bg-[#eaf2eb] text-[#4a6c4c] rounded-lg mt-0.5">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-semibold text-[#1e291b]">철저한 익명성 및 보안 보장</h3>
              <p className="text-xs text-gray-500">로컬 퍼스트 저장 지원으로 내 개인 데이터 유출 걱정 없음</p>
            </div>
          </div>
        </div>

        {/* CTA 버튼 */}
        <div className="pt-2">
          <Link 
            href="/onboarding" 
            className="w-full py-3.5 bg-[#4a6c4c] hover:bg-[#3b573d] text-white font-medium rounded-xl flex items-center justify-center calm-shadow transition-colors"
          >
            오늘의 마음 체크인 시작하기
          </Link>
        </div>
      </div>

      {/* 비의료용 메디컬 가이드라인 안내 (디스클레이머) */}
      <div className="w-full max-w-md bg-amber-50/60 border border-amber-200/50 rounded-xl p-4 flex gap-3 animate-fade-in" style={{ animationDelay: "0.2s" }}>
        <AlertTriangle className="w-5 h-5 text-[#d89657] shrink-0 mt-0.5" />
        <div className="text-xs text-[#805b36] leading-relaxed">
          <p className="font-bold mb-1">안내 및 면책 고지</p>
          본 서비스는 정신건강 자가관리 향상을 목적으로 설계된 셀프헬프 자가도구로, **의학적 진단, 약물 처방, 또는 전문 심리치료를 대체할 수 없습니다.** 지속적인 고통이 있거나 비상 상황 시 전문 의료진과의 상담 또는 긴급 구조 전화를 이용해 주십시오.
        </div>
      </div>
    </div>
  );
}
