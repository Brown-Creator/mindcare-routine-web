"use client";

import { useEffect, useState } from "react";
import { localDB, ScreeningResult } from "@/lib/local-storage";
import { AlertTriangle, BookOpen, CheckCircle, ClipboardList, HelpCircle, ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";

const PHQ_9_QUESTIONS = [
  "1. 일 또는 여가 활동을 하는 데 흥미나 즐거움이 거의 없음",
  "2. 기분이 가라앉거나, 우울하거나, 희망이 없다고 느낌",
  "3. 잠들기 어렵거나 자주 깨거나, 혹은 너무 많이 잠",
  "4. 피곤하다고 느끼거나 기운이 없음",
  "5. 입맛이 없거나 과식을 함",
  "6. 자신을 부정적으로 보거나, 자신이 실패자라고 느끼거나, 자신 또는 가족을 실망시켰다고 느낌",
  "7. 신문 기사를 읽거나 TV를 보는 등 어떤 일에 집중하기가 어려움",
  "8. 다른 사람들이 알아챌 정도로 너무 느리게 걷거나 말함, 또는 평소보다 안절부절못해서 훨씬 많이 돌아다님",
  "9. 태어나지 않았더라면 더 좋았을 것이라고 생각하거나, 어떤 식으로든 자해를 하려고 생각함"
];

const GAD_7_QUESTIONS = [
  "1. 초조하거나 불안하거나 안절부절못함",
  "2. 걱정하는 것을 멈추거나 조절할 수 없음",
  "3. 여러 가지 일에 대해 너무 걱정함",
  "4. 편안하게 있기 어려움",
  "5. 너무 안절부절못해서 가만히 앉아 있기 어려움",
  "6. 쉽게 짜증이 나거나 신경질이 남",
  "7. 끔찍한 일이 일어날 것처럼 두려움을 느낌"
];

const SCALES = [
  { value: 0, label: "전혀 없음 (0)" },
  { value: 1, label: "며칠 동안 (1)" },
  { value: 2, label: "1주일 이상 (2)" },
  { value: 3, label: "거의 매일 (3)" }
];

export default function ScreeningPage() {
  const router = useRouter();
  const [selectedTool, setSelectedTool] = useState<"PHQ-9" | "GAD-7" | null>(null);
  const [answers, setAnswers] = useState<number[]>([]);
  const [currentQuestionIdx, setCurrentQuestionIdx] = useState<number>(0);
  const [showResult, setShowResult] = useState<ScreeningResult | null>(null);
  const [hasConsent, setHasConsent] = useState<boolean>(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const consents = localDB.getConsent();
      setHasConsent(!!(consents && consents.agreedSensitiveData));
    }
  }, []);

  const handleStart = (tool: "PHQ-9" | "GAD-7") => {
    setSelectedTool(tool);
    setAnswers(new Array(tool === "PHQ-9" ? PHQ_9_QUESTIONS.length : GAD_7_QUESTIONS.length).fill(0));
    setCurrentQuestionIdx(0);
    setShowResult(null);
  };

  const handleSelectAnswer = (val: number) => {
    const nextAnswers = [...answers];
    nextAnswers[currentQuestionIdx] = val;
    setAnswers(nextAnswers);

    const maxQuestions = selectedTool === "PHQ-9" ? PHQ_9_QUESTIONS.length : GAD_7_QUESTIONS.length;

    if (currentQuestionIdx < maxQuestions - 1) {
      setCurrentQuestionIdx(prev => prev + 1);
    } else {
      // 마지막 문제 완료 -> 저장 평가
      const totalScore = nextAnswers.reduce((a, b) => a + b, 0);
      
      const { result, crisisTriggered } = localDB.saveScreeningResult({
        type: selectedTool!,
        answers: nextAnswers,
        totalScore
      });

      if (crisisTriggered) {
        // 즉각 위기 지원 라우팅
        router.push("/crisis");
      } else {
        setShowResult(result);
        setSelectedTool(null);
      }
    }
  };

  const getPHQInterpretation = (score: number) => {
    if (score <= 4) return "우울 상태가 아님 (경미한 수준)";
    if (score <= 9) return "가벼운 수준의 우울";
    if (score <= 14) return "중간 수준의 우울";
    if (score <= 19) return "중증 중간 수준의 우울";
    return "심한 수준의 우울";
  };

  const getGADInterpretation = (score: number) => {
    if (score <= 4) return "불안 상태가 아님 (정상 수준)";
    if (score <= 9) return "가벼운 수준의 불안";
    if (score <= 14) return "중간 수준의 불안";
    return "심한 수준의 불안";
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-0.5">
        <h1 className="text-2xl font-bold text-[#1e291b] tracking-tight">선별 검사 (자가 진단 서브셋)</h1>
        <p className="text-xs text-gray-500">내 현재 심리 지표를 검증된 질문지로 가만히 돌아봅니다.</p>
      </div>

      {/* 비의료 진단 안내 고지 카드 */}
      <div className="bg-amber-50 border border-amber-200/50 p-4 rounded-2xl flex gap-3 text-xs text-[#805b36] leading-relaxed">
        <AlertTriangle className="w-5 h-5 text-[#d89657] shrink-0 mt-0.5" />
        <div>
          <strong className="font-bold">⚠️ 의료 진단 면책 고지</strong>
          <p className="mt-1">
            본 스크리닝 점수는 자가 점검용 설문지이며, 의사나 심리상담사의 **의학적 임상 진단을 대신할 수 없습니다.** 결과 점수와 상관없이 일상적인 피로 및 우울감이 지속되거나 고통스럽다면 가까운 정신과 병원이나 지역 건강지원센터 등의 전문가 도움을 권장합니다.
          </p>
        </div>
      </div>

      {selectedTool ? (
        /* 검사 설문지 화면 */
        <div className="bg-white rounded-2xl p-6 border border-[#e4e7e3] calm-shadow space-y-6 animate-fade-in">
          
          <div className="flex justify-between items-center border-b border-gray-100 pb-3">
            <h2 className="text-sm font-bold text-[#4a6c4c] flex items-center gap-1.5">
              <ClipboardList className="w-4 h-4" /> {selectedTool} 문항 응답 중
            </h2>
            <span className="text-xs font-semibold text-gray-400">
              {currentQuestionIdx + 1} / {selectedTool === "PHQ-9" ? PHQ_9_QUESTIONS.length : GAD_7_QUESTIONS.length}
            </span>
          </div>

          <div className="space-y-4">
            <h3 className="text-base font-bold text-[#1e291b] leading-relaxed">
              {selectedTool === "PHQ-9" ? PHQ_9_QUESTIONS[currentQuestionIdx] : GAD_7_QUESTIONS[currentQuestionIdx]}
            </h3>
            
            <p className="text-xs text-gray-400">최근 2주일 동안 이러한 곤란을 얼마나 자주 겪으셨는지 골라주세요.</p>

            <div className="grid grid-cols-1 gap-2 pt-2">
              {SCALES.map((scale) => {
                return (
                  <button
                    key={scale.value}
                    type="button"
                    onClick={() => handleSelectAnswer(scale.value)}
                    className="w-full text-left p-3.5 bg-[#f8faf7] hover:bg-[#eaf2eb]/30 border border-[#e4e7e3] hover:border-[#4a6c4c] rounded-xl text-xs font-semibold text-gray-700 transition-all flex justify-between items-center"
                  >
                    <span>{scale.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="text-center pt-2">
            <button
              onClick={() => setSelectedTool(null)}
              className="text-xs text-gray-400 hover:text-gray-600 underline font-medium"
            >
              검사 그만두고 돌아가기
            </button>
          </div>

        </div>
      ) : (
        /* 초기 선택 화면 */
        <div className="space-y-4">
          
          <div className="grid grid-cols-1 gap-3">
            {/* A. PHQ-9 우울증 자가 진단 */}
            <button
              onClick={() => handleStart("PHQ-9")}
              className="flex justify-between items-center p-5 bg-white border border-[#e4e7e3] rounded-2xl hover:bg-[#eaf2eb]/30 text-left transition-all calm-shadow"
            >
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-[#1e291b]">우울 선별 자가진단 (PHQ-9)</h3>
                <p className="text-xs text-gray-400">9가지 대표 우울 경향 자조 측정 • 3분</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-300" />
            </button>

            {/* B. GAD-7 불안 자가 진단 */}
            <button
              onClick={() => handleStart("GAD-7")}
              className="flex justify-between items-center p-5 bg-white border border-[#e4e7e3] rounded-2xl hover:bg-[#eaf2eb]/30 text-left transition-all calm-shadow"
            >
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-[#1e291b]">불안 선별 자가진단 (GAD-7)</h3>
                <p className="text-xs text-gray-400">일상을 압도하는 긴장과 불안 수치 측정 • 2분</p>
              </div>
              <ChevronRight className="w-5 h-5 text-gray-300" />
            </button>
          </div>

          {/* 저장 제한 확인 안내 */}
          {!hasConsent && (
            <p className="text-[11px] text-amber-700 bg-amber-50/40 p-3 rounded-xl border border-amber-100/30 leading-normal">
              💡 현재 개인정보 동의 양식에서 '민감 데이터 수집'을 거부하신 상태입니다. 검사는 완료하여 결과를 즉각 보실 수 있지만, 완료된 점수가 데이터베이스에 저장되지 않습니다.
            </p>
          )}

          {/* 결과 모달(창) 형식의 최근 결과 알림 */}
          {showResult && (
            <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-5 space-y-3 animate-fade-in">
              <h3 className="text-sm font-bold text-emerald-800 flex items-center gap-1.5">
                <CheckCircle className="w-4 h-4 text-emerald-600" /> {showResult.type} 검사 완료 결과
              </h3>
              <div className="space-y-1 text-xs">
                <p className="text-emerald-900">
                  총점: <strong className="text-base text-emerald-700 font-extrabold">{showResult.totalScore}점</strong>
                </p>
                <p className="text-emerald-800 leading-relaxed font-semibold">
                  해석 지표: {showResult.type === "PHQ-9" ? getPHQInterpretation(showResult.totalScore) : getGADInterpretation(showResult.totalScore)}
                </p>
              </div>
              <p className="text-[10px] text-emerald-700/80 leading-normal border-t border-emerald-100 pt-2">
                * 이 결과는 임상적 진단이 아닙니다. 일상 스트레스 조절에 활용하시고, 높은 수준의 우울/불안이 장기간 지속될 시 꼭 전문의 진단을 받으세요.
              </p>
              <button
                onClick={() => setShowResult(null)}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-semibold"
              >
                결과 닫기
              </button>
            </div>
          )}

        </div>
      )}

    </div>
  );
}
