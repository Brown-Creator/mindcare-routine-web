"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { localDB } from "@/lib/local-storage";
import { ShieldCheck, Info, FileText, CheckCircle2 } from "lucide-react";

export default function OnboardingPage() {
  const router = useRouter();
  const [ageConfirmed, setAgeConfirmed] = useState<boolean>(false);
  const [agreeTerms, setAgreeTerms] = useState<boolean>(false);
  const [agreePrivacy, setAgreePrivacy] = useState<boolean>(false);
  const [agreeSensitive, setAgreeSensitive] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string>("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!ageConfirmed) {
      setErrorMessage("서비스 이용을 위해 만 19세 이상 연령 확인이 필요합니다.");
      return;
    }
    if (!agreeTerms || !agreePrivacy) {
      setErrorMessage("이용약관 및 개인정보 수집이용 동의는 필수사항입니다.");
      return;
    }
    if (!agreeSensitive) {
      setErrorMessage("CBT 기록, 마음상태 등 민감정보 수집 이용동의가 필요합니다.");
      return;
    }

    // 로컬 스토리지에 동의 정보 저장
    localDB.saveConsent({
      agreedAge19: ageConfirmed,
      agreedTerms: agreeTerms,
      agreedPrivacy: agreePrivacy,
      agreedSensitiveData: agreeSensitive
    });

    // 온보딩 완료 시 대시보드로 이동
    router.push("/dashboard");
  };

  return (
    <div className="min-h-screen bg-[#f8faf7] flex flex-col justify-center items-center px-4 py-8">
      <div className="w-full max-w-md bg-white rounded-2xl p-6 calm-shadow border border-[#e4e7e3] space-y-6">
        
        {/* 헤더 */}
        <div className="text-center space-y-2">
          <div className="w-12 h-12 bg-[#eaf2eb] text-[#4a6c4c] rounded-full flex items-center justify-center mx-auto">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h2 className="text-xl font-bold text-[#1e291b]">동의 및 이용자 보호 안내</h2>
          <p className="text-xs text-gray-500">마음케어 루틴을 안전하고 안심하며 이용하기 위한 안내입니다.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* 연령 및 동의 카드 */}
          <div className="space-y-4 text-sm text-[#1e291b]">
            
            {/* 만 19세 이상 확인 */}
            <label className="flex items-start gap-3 p-3 bg-[#f8faf7] hover:bg-[#eaf2eb]/30 rounded-xl border border-[#e4e7e3] cursor-pointer transition-colors">
              <input 
                type="checkbox" 
                checked={ageConfirmed} 
                onChange={(e) => setAgeConfirmed(e.target.checked)}
                className="w-4 h-4 rounded text-[#4a6c4c] border-[#e4e7e3] focus:ring-[#4a6c4c] mt-0.5"
              />
              <div>
                <span className="font-semibold">만 19세 이상 성인 확인 (필수)</span>
                <p className="text-xs text-gray-500 mt-0.5">본 자가관리 도구는 만 19세 이상 성인을 대상으로 포지셔닝되었습니다.</p>
              </div>
            </label>

            {/* 수집 범위 설명 */}
            <div className="p-3 bg-gray-50 border border-gray-200/50 rounded-xl space-y-2 text-xs text-gray-500">
              <div className="flex gap-1.5 items-center font-semibold text-[#1e291b]">
                <Info className="w-3.5 h-3.5 text-[#4a6c4c]" />
                수집되는 개인/민감 데이터 범위 안내
              </div>
              <ul className="list-disc list-inside space-y-1 pl-1">
                <li>일일 마음 체크인 점수 (기분, 스트레스, 수면 질, 활력 에너지)</li>
                <li>선택 감정 칩 데이터 및 기분 메모 텍스트</li>
                <li>CBT 인지행동 사고 기록 텍스트</li>
                <li>마음챙김 완료 내역 및 행동활성화 전/후 감정 변화율</li>
                <li>대인 관계 및 감정 반복 패턴 성찰 저널 텍스트</li>
              </ul>
              <p className="mt-1 border-t border-gray-200 pt-2 text-[#4a6c4c] font-medium">
                💡 언제든지 내 정보 설정 메뉴를 통해 전체 데이터를 JSON/CSV 파일로 내보내거나, 즉각적이고 영구적으로 모든 흔적을 완전 파기(삭제)할 권리를 가집니다.
              </p>
            </div>

            {/* 약관 동의 체크박스 리스트 */}
            <div className="space-y-2.5">
              <label className="flex items-center gap-3 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={agreeTerms} 
                  onChange={(e) => setAgreeTerms(e.target.checked)}
                  className="w-4 h-4 rounded text-[#4a6c4c] border-[#e4e7e3] focus:ring-[#4a6c4c]"
                />
                <span className="text-xs">서비스 이용약관 동의 (필수)</span>
              </label>

              <label className="flex items-center gap-3 cursor-pointer">
                <input 
                  type="checkbox" 
                  checked={agreePrivacy} 
                  onChange={(e) => setAgreePrivacy(e.target.checked)}
                  className="w-4 h-4 rounded text-[#4a6c4c] border-[#e4e7e3] focus:ring-[#4a6c4c]"
                />
                <span className="text-xs">개인정보 수집 및 이용 동의 (필수)</span>
              </label>

              <label className="flex items-start gap-3 cursor-pointer p-3 bg-emerald-50/50 border border-emerald-100 rounded-xl">
                <input 
                  type="checkbox" 
                  checked={agreeSensitive} 
                  onChange={(e) => setAgreeSensitive(e.target.checked)}
                  className="w-4 h-4 rounded text-[#4a6c4c] border-[#e4e7e3] focus:ring-[#4a6c4c] mt-0.5"
                />
                <div>
                  <span className="text-xs font-semibold text-emerald-900">정신건강 민감 정보 수집 및 이용 동의 (필수)</span>
                  <p className="text-[11px] text-emerald-700/80 mt-0.5 leading-relaxed">
                    작성하시는 저널 본문, 감정 점수 등은 극도로 사적인 건강/정신 민감 정보에 해당하므로, 이에 대한 별도 고지 및 동의가 필요합니다. 동의하지 않으실 경우 마음케어 분석 서비스를 온전히 이용하기 어려울 수 있습니다.
                  </p>
                </div>
              </label>
            </div>

          </div>

          {/* 에러 메시지 */}
          {errorMessage && (
            <p className="text-xs text-red-500 bg-red-50 p-2.5 rounded-lg border border-red-100 font-medium">
              ⚠️ {errorMessage}
            </p>
          )}

          {/* 시작 버튼 */}
          <button 
            type="submit"
            className="w-full py-3.5 bg-[#4a6c4c] hover:bg-[#3b573d] text-white font-medium rounded-xl flex items-center justify-center calm-shadow transition-colors text-sm"
          >
            <CheckCircle2 className="w-4 h-4 mr-2" />
            동의 완료하고 마음케어 루틴 시작하기
          </button>
        </form>

      </div>
    </div>
  );
}
