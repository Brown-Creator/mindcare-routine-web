"use client";

import { useEffect, useState } from "react";
import { localDB, MindfulnessSession } from "@/lib/local-storage";
import { mindfulnessExercises } from "@/lib/seed-data";
import { Sparkles, ChevronRight, Play, AlertTriangle, CheckCircle, Clock, Volume2, VolumeX, Music, Heart } from "lucide-react";
import { soundscape } from "@/lib/soundscape";

export default function MindfulnessPage() {
  const [sessions, setSessions] = useState<MindfulnessSession[]>([]);
  const [selectedExercise, setSelectedExercise] = useState<typeof mindfulnessExercises[0] | null>(null);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [showWarningAlert, setShowWarningAlert] = useState<boolean>(false);

  // 호흡 페이서 상태
  const [breathPhase, setBreathPhase] = useState<"IN" | "HOLD" | "OUT">("IN");
  const [breathSeconds, setBreathSeconds] = useState<number>(4);
  const [isBreathingActive, setIsBreathingActive] = useState<boolean>(false);
  
  // 사운드스케이프 오디오 재생 상태
  const [rainActive, setRainActive] = useState<boolean>(false);
  const [bowlActive, setBowlActive] = useState<boolean>(false);
  const [rainVolume, setRainVolume] = useState<number>(0.3);

  // 호흡 페이서 타이머 루프
  useEffect(() => {
    let timer: any = null;
    if (isBreathingActive && selectedExercise) {
      timer = setInterval(() => {
        setBreathSeconds(prev => {
          if (prev <= 1) {
            if (breathPhase === "IN") {
              setBreathPhase("HOLD");
              return 7; // 멈춤 7초
            } else if (breathPhase === "HOLD") {
              setBreathPhase("OUT");
              return 8; // 날숨 8초
            } else {
              setBreathPhase("IN");
              return 4; // 들숨 4초
            }
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isBreathingActive, breathPhase, selectedExercise]);

  // 사운드스케이프 제어 감지 및 정리
  useEffect(() => {
    if (rainActive) {
      soundscape.startRain(rainVolume);
    } else {
      soundscape.stopRain();
    }
  }, [rainActive]);

  useEffect(() => {
    if (bowlActive) {
      soundscape.startBowlLoop(0.4, 18);
    } else {
      soundscape.stopBowlLoop();
    }
  }, [bowlActive]);

  // 언마운트 시 사운드 완전 종료
  useEffect(() => {
    return () => {
      soundscape.stopAll();
    };
  }, []);

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

              {/* 호흡 가이드 및 사운드 제어 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-gray-100 pt-4">
                
                {/* 1. 시각적 호흡 페이서 */}
                <div className="bg-[#f8faf7] border border-[#e4e7e3] p-4 rounded-2xl flex flex-col items-center justify-center text-center space-y-4 min-h-[200px]">
                  <h3 className="text-xs font-bold text-[#4a6c4c] flex items-center gap-1.5">
                    <Heart className="w-3.5 h-3.5 fill-[#4a6c4c]" /> 호흡 페이서 (4-7-8 템포)
                  </h3>
                  
                  {isBreathingActive ? (
                    <div className="space-y-3 flex flex-col items-center">
                      {/* 맥동하는 서클 애니메이션 */}
                      <div className="relative w-24 h-24 flex items-center justify-center">
                        <div 
                          className="absolute bg-[#4a6c4c]/10 rounded-full border border-[#4a6c4c]/30 transition-all duration-1000 ease-in-out"
                          style={{
                            width: breathPhase === "IN" ? "96px" : breathPhase === "HOLD" ? "96px" : "40px",
                            height: breathPhase === "IN" ? "96px" : breathPhase === "HOLD" ? "96px" : "40px",
                          }}
                        />
                        <div 
                          className="absolute bg-[#4a6c4c] text-white rounded-full flex flex-col items-center justify-center font-bold text-xs calm-shadow transition-all duration-1000 ease-in-out"
                          style={{
                            width: breathPhase === "IN" ? "80px" : breathPhase === "HOLD" ? "80px" : "48px",
                            height: breathPhase === "IN" ? "80px" : breathPhase === "HOLD" ? "80px" : "48px",
                          }}
                        >
                          <span className="text-[10px] opacity-80">
                            {breathPhase === "IN" ? "들이마시기" : breathPhase === "HOLD" ? "멈추기" : "내쉬기"}
                          </span>
                          <span className="text-xs mt-0.5">{breathSeconds}초</span>
                        </div>
                      </div>
                      <button
                        onClick={() => setIsBreathingActive(false)}
                        className="text-[10px] text-gray-400 hover:text-gray-600 underline font-semibold"
                      >
                        호흡 페이서 일시정지
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-[11px] text-gray-400 leading-normal">
                        호흡 리듬을 시각 애니메이션에 맞춰 정돈해 줍니다.
                      </p>
                      <button
                        onClick={() => {
                          setBreathPhase("IN");
                          setBreathSeconds(4);
                          setIsBreathingActive(true);
                        }}
                        className="px-3 py-1.5 bg-[#4a6c4c] text-white text-[11px] font-bold rounded-lg hover:bg-[#3b573d] transition-all"
                      >
                        호흡 리듬 가이드 시작
                      </button>
                    </div>
                  )}
                </div>

                {/* 2. 사운드스케이프 (빗소리 및 싱잉볼) */}
                <div className="bg-[#f8faf7] border border-[#e4e7e3] p-4 rounded-2xl flex flex-col justify-center space-y-4">
                  <h3 className="text-xs font-bold text-[#4a6c4c] flex items-center gap-1.5">
                    <Music className="w-3.5 h-3.5 text-[#d89657] fill-[#d89657]" /> 명상 백그라운드 자연음 합성
                  </h3>
                  <p className="text-[10px] text-gray-400 leading-normal">
                    Web Audio 기술로 외부 서버 연결 없이도 자연 주파수 오디오를 실시간 합성합니다.
                  </p>
                  
                  <div className="space-y-3 text-xs">
                    {/* 빗소리 토글 */}
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <label className="font-semibold text-gray-600 flex items-center gap-1.5 cursor-pointer">
                          <input 
                            type="checkbox" 
                            checked={rainActive}
                            onChange={(e) => setRainActive(e.target.checked)}
                            className="rounded text-[#4a6c4c] focus:ring-[#4a6c4c] w-3.5 h-3.5"
                          />
                          잔잔한 빗소리 재생
                        </label>
                        <span className="text-[10px] text-gray-400 font-bold">{Math.round(rainVolume * 100)}%</span>
                      </div>
                      {rainActive && (
                        <input 
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={rainVolume}
                          onChange={(e) => {
                            const vol = parseFloat(e.target.value);
                            setRainVolume(vol);
                            soundscape.setRainVolume(vol);
                          }}
                          className="w-full accent-[#4a6c4c] h-1 bg-gray-200 rounded-lg cursor-pointer"
                        />
                      )}
                    </div>

                    {/* 싱잉볼 토글 */}
                    <div className="flex justify-between items-center pt-1 border-t border-gray-100/60">
                      <label className="font-semibold text-gray-600 flex items-center gap-1.5 cursor-pointer">
                        <input 
                          type="checkbox" 
                          checked={bowlActive}
                          onChange={(e) => setBowlActive(e.target.checked)}
                          className="rounded text-[#4a6c4c] focus:ring-[#4a6c4c] w-3.5 h-3.5"
                        />
                        티베트 싱잉볼 공명 벨 (18초 간격)
                      </label>
                      <button
                        onClick={() => soundscape.playBowlOnce(0.5)}
                        className="px-2 py-1 bg-white border border-gray-200 rounded text-[10px] font-bold text-gray-500 hover:bg-gray-50 transition-all shrink-0"
                      >
                        1회 강제 연주
                      </button>
                    </div>
                  </div>
                </div>

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
