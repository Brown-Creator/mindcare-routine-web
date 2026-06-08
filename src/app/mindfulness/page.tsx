"use client";

import { useEffect, useState } from "react";
import { localDB, MindfulnessSession } from "@/lib/local-storage";
import { mindfulnessExercises } from "@/lib/seed-data";
import { Sparkles, ChevronRight, Play, AlertTriangle, CheckCircle, Clock } from "lucide-react";

export default function MindfulnessPage() {
  const [sessions, setSessions] = useState<MindfulnessSession[]>([]);
  const [selectedExercise, setSelectedExercise] = useState<typeof mindfulnessExercises[0] | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [showWarningAlert, setShowWarningAlert] = useState<boolean>(false);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = () => {
    const saved = localDB.getMindfulnessSessions();
    setSessions(saved);
  };

  const handleStartExercise = (ex: typeof mindfulnessExercises[0]) => {
    setSelectedExercise(ex);
    setCurrentStep(0);
    if (ex.warning) {
      setShowWarningAlert(true);
    } else {
      setShowWarningAlert(false);
    }
  };

  const handleNextStep = () => {
    if (selectedExercise && currentStep < selectedExercise.steps.length - 1) {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handlePrevStep = () => {
    setCurrentStep(prev => Math.max(0, prev - 1));
  };

  const handleComplete = () => {
    if (selectedExercise) {
      localDB.saveMindfulnessSession({
        exerciseId: selectedExercise.id,
        exerciseTitle: selectedExercise.title,
        durationMinutes: selectedExercise.durationMinutes
      });
      loadSessions();
      setSelectedExercise(null);
      setCurrentStep(0);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-0.5">
        <h1 className="text-2xl font-bold text-[#1e291b] tracking-tight">마음챙김 및 그라운딩</h1>
        <p className="text-xs text-gray-500">현재의 감각과 호흡에 머무르며 머릿속 생각을 진정시킵니다.</p>
      </div>

      {selectedExercise ? (
        /* 명상 진행 모드 */
        <div className="bg-white rounded-2xl p-6 border border-[#e4e7e3] calm-shadow space-y-6 animate-fade-in">
          
          {/* 바디스캔용 특수 주의 경고 카드 */}
          {showWarningAlert && selectedExercise.warning && (
            <div className="bg-amber-50 border border-amber-200/60 p-4 rounded-2xl flex gap-3 text-xs text-[#805b36] leading-relaxed">
              <AlertTriangle className="w-5 h-5 text-[#d89657] shrink-0" />
              <div>
                <p className="font-bold mb-1">민감성 안내 고지</p>
                {selectedExercise.warning}
                <button
                  type="button"
                  onClick={() => setShowWarningAlert(false)}
                  className="mt-2 text-[#4a6c4c] font-bold block underline"
                >
                  위 내용을 이해했으며 연습을 시작하겠습니다
                </button>
              </div>
            </div>
          )}

          {(!showWarningAlert || !selectedExercise.warning) && (
            <div className="space-y-6">
              
              {/* 상단 프로그레스 바 */}
              <div className="flex justify-between items-center border-b border-gray-100 pb-3">
                <h2 className="text-sm font-bold text-[#4a6c4c]">{selectedExercise.title}</h2>
                <span className="text-xs text-gray-400 font-semibold">
                  진행 {currentStep + 1} / {selectedExercise.steps.length}
                </span>
              </div>

              {/* 진행 가이드 텍스트 (명상 텍스트) */}
              <div className="min-h-[140px] flex items-center justify-center bg-[#f8faf7] border border-[#e4e7e3] rounded-2xl p-5 text-center">
                <p className="text-sm text-gray-700 leading-relaxed font-medium transition-all">
                  {selectedExercise.steps[currentStep]}
                </p>
              </div>

              {/* 제어 버튼 */}
              <div className="flex justify-between items-center pt-2">
                <button
                  onClick={handlePrevStep}
                  disabled={currentStep === 0}
                  className="px-3.5 py-2 bg-gray-50 border border-[#e4e7e3] hover:bg-[#eaf2eb]/20 text-gray-500 rounded-xl flex items-center text-xs font-semibold disabled:opacity-40"
                >
                  이전 단계
                </button>

                {currentStep < selectedExercise.steps.length - 1 ? (
                  <button
                    onClick={handleNextStep}
                    className="px-3.5 py-2 bg-[#4a6c4c] hover:bg-[#3b573d] text-white rounded-xl flex items-center text-xs font-semibold"
                  >
                    다음 단계
                  </button>
                ) : (
                  <button
                    onClick={handleComplete}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl flex items-center text-xs font-semibold"
                  >
                    <CheckCircle className="w-4 h-4 mr-1" />
                    연습 완료하기
                  </button>
                )}
              </div>

              <div className="text-center">
                <button
                  onClick={() => setSelectedExercise(null)}
                  className="text-xs text-gray-400 hover:text-gray-600 underline font-medium"
                >
                  명상 그만두고 돌아가기
                </button>
              </div>

            </div>
          )}

        </div>
      ) : (
        /* 명상 메뉴 선택 모드 */
        <div className="space-y-4">
          <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-2">
            <h2 className="text-sm font-bold text-[#4a6c4c] flex items-center gap-1.5">
              <Sparkles className="w-4 h-4" /> 마음챙김 연습을 고르세요
            </h2>
            <p className="text-xs text-gray-500 leading-relaxed">
              오디오나 특별한 도구 없이, 조용한 공간에서 눈을 감고 텍스트 가이드를 천천히 읽어가며 내 몸과 주위를 그라운딩합니다.
            </p>
          </div>

          <div className="space-y-2.5">
            <h3 className="text-xs font-bold text-gray-400">명상 리스트</h3>
            <div className="grid grid-cols-1 gap-2.5">
              {mindfulnessExercises.map(ex => {
                return (
                  <button
                    key={ex.id}
                    onClick={() => handleStartExercise(ex)}
                    className="flex justify-between items-center p-4 bg-white border border-[#e4e7e3] rounded-2xl hover:bg-[#eaf2eb]/30 transition-all text-left calm-shadow"
                  >
                    <div className="space-y-1">
                      <h4 className="text-sm font-semibold text-[#1e291b]">{ex.title}</h4>
                      <p className="text-xs text-gray-400 max-w-[280px] truncate">{ex.description}</p>
                    </div>
                    <div className="flex items-center gap-1 text-[11px] font-bold text-[#4a6c4c] bg-[#eaf2eb] px-2 py-1 rounded-full shrink-0">
                      <Clock className="w-3.5 h-3.5" /> {ex.durationMinutes}분
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 히스토리 */}
          {sessions.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-gray-400">최근 명상 내역</h3>
              <div className="space-y-2">
                {sessions.slice(0, 5).map(s => {
                  return (
                    <div key={s.id} className="flex justify-between items-center p-3.5 bg-white border border-gray-100 rounded-xl text-xs">
                      <div>
                        <span className="font-semibold text-[#1e291b]">{s.exerciseTitle}</span>
                        <p className="text-[10px] text-gray-400 mt-0.5">
                          {new Date(s.timestamp).toLocaleDateString()}
                        </p>
                      </div>
                      <span className="text-xs font-bold text-gray-500 bg-gray-50 px-2 py-1 rounded-full border border-gray-200">
                        {s.durationMinutes}분 연습 완료
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

        </div>
      )}

    </div>
  );
}
