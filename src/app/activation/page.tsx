"use client";

import { useEffect, useState } from "react";
import { localDB, ActivationSession } from "@/lib/local-storage";
import { activationTasks } from "@/lib/seed-data";
import { Activity, ArrowRight, Play, CheckCircle, Award, Smile } from "lucide-react";

export default function ActivationPage() {
  const [sessions, setSessions] = useState<ActivationSession[]>([]);
  const [step, setStep] = useState<"SELECT" | "BEFORE" | "DOING" | "AFTER">("SELECT");
  const [selectedTask, setSelectedTask] = useState<typeof activationTasks[0] | null>(null);
  
  const [moodBefore, setMoodBefore] = useState<number>(5);
  const [moodAfter, setMoodAfter] = useState<number>(5);

  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = () => {
    const saved = localDB.getActivationSessions();
    setSessions(saved);
  };

  const handleStartTask = (task: typeof activationTasks[0]) => {
    setSelectedTask(task);
    setStep("BEFORE");
  };

  const handleSaveBefore = () => {
    setStep("DOING");
  };

  const handleCompleteTask = () => {
    setStep("AFTER");
  };

  const handleSaveAfter = () => {
    if (selectedTask) {
      localDB.saveActivationSession({
        taskId: selectedTask.id,
        taskTitle: selectedTask.title,
        moodBefore,
        moodAfter,
        completed: true
      });
      loadSessions();
      // 초기화
      setSelectedTask(null);
      setMoodBefore(5);
      setMoodAfter(5);
      setStep("SELECT");
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-0.5">
        <h1 className="text-2xl font-bold text-[#1e291b] tracking-tight">초소형 행동 활성화</h1>
        <p className="text-xs text-gray-500">기분이 행동을 지배하기 전에, 작은 행동으로 기분을 먼저 움직입니다.</p>
      </div>

      {step === "SELECT" && (
        /* 행동 태스크 리스트 선택 */
        <div className="space-y-4">
          <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-2">
            <h2 className="text-sm font-bold text-[#4a6c4c] flex items-center gap-1.5">
              <Activity className="w-4 h-4" /> 행동 처방의 효과
            </h2>
            <p className="text-xs text-gray-500 leading-relaxed">
              의욕이 전혀 없을 때, 몸을 3분만 움직이는 것만으로도 뇌가 활성화되기 시작합니다. 아래의 아주 쉽고 작은 미션 중 하나를 골라 시작해 보세요.
            </p>
          </div>

          <div className="space-y-2.5">
            <h3 className="text-xs font-bold text-gray-400">행동 리스트</h3>
            <div className="grid grid-cols-1 gap-2.5">
              {activationTasks.map(task => {
                return (
                  <button
                    key={task.id}
                    onClick={() => handleStartTask(task)}
                    className="flex justify-between items-center p-4 bg-white border border-[#e4e7e3] rounded-2xl hover:bg-[#eaf2eb]/30 transition-all text-left calm-shadow"
                  >
                    <div className="space-y-1">
                      <h4 className="text-sm font-semibold text-[#1e291b]">{task.title}</h4>
                      <p className="text-xs text-gray-400 truncate max-w-[280px]">{task.description}</p>
                    </div>
                    <div className="flex items-center gap-1 text-[11px] font-bold text-[#4a6c4c] bg-[#eaf2eb] px-2 py-1 rounded-full shrink-0">
                      <Play className="w-3 h-3 fill-[#4a6c4c]" /> {task.durationMinutes}분
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 과거 완료 세션 히스토리 */}
          {sessions.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-gray-400">최근 실천 결과</h3>
              <div className="space-y-2">
                {sessions.slice(0, 5).map(s => {
                  const diff = s.moodAfter - s.moodBefore;
                  return (
                    <div key={s.id} className="flex justify-between items-center p-3.5 bg-white border border-gray-100 rounded-xl text-xs">
                      <div>
                        <span className="font-semibold text-[#1e291b]">{s.taskTitle}</span>
                        <p className="text-[10px] text-gray-400 mt-0.5">
                          {new Date(s.timestamp).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 font-semibold text-gray-600">
                        <span>기분: {s.moodBefore}</span>
                        <ArrowRight className="w-3.5 h-3.5 text-gray-300" />
                        <span className="text-[#4a6c4c]">{s.moodAfter}</span>
                        {diff > 0 && (
                          <span className="text-[10px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-100">
                            +{diff} 향상
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {step === "BEFORE" && selectedTask && (
        /* 행동 전 기분 입력 */
        <div className="bg-white rounded-2xl p-6 border border-[#e4e7e3] calm-shadow space-y-6 text-center animate-fade-in">
          <div className="space-y-2">
            <span className="text-xs font-bold text-[#4a6c4c] bg-[#eaf2eb] px-2.5 py-1 rounded-full">
              STEP 1: 기분 체크
            </span>
            <h3 className="text-lg font-bold text-[#1e291b]">실천 전 현재 기분은 어떠신가요?</h3>
            <p className="text-xs text-gray-400">행동 후 기분 변화를 살펴보기 위해, 현재의 기분을 1점(가장 나쁨)부터 10점(가장 좋음) 사이로 짚어주세요.</p>
          </div>

          <div className="space-y-4 py-4">
            <span className="text-4xl font-extrabold text-[#4a6c4c]">{moodBefore} / 10</span>
            <input 
              type="range" 
              min="1" 
              max="10" 
              value={moodBefore} 
              onChange={(e) => setMoodBefore(parseInt(e.target.value))}
              className="w-full h-2 bg-[#e4e7e3] rounded-lg appearance-none cursor-pointer accent-[#4a6c4c]"
            />
          </div>

          <button
            onClick={handleSaveBefore}
            className="w-full py-3.5 bg-[#4a6c4c] hover:bg-[#3b573d] text-white font-medium rounded-xl flex items-center justify-center calm-shadow transition-colors text-sm"
          >
            행동 시작하러 가기
          </button>
        </div>
      )}

      {step === "DOING" && selectedTask && (
        /* 행동 실천 가이드 */
        <div className="bg-white rounded-2xl p-6 border border-[#e4e7e3] calm-shadow space-y-6 text-center animate-fade-in">
          <div className="space-y-2">
            <span className="text-xs font-bold text-amber-600 bg-amber-50 px-2.5 py-1 rounded-full border border-amber-100">
              STEP 2: 미션 수행 중 ({selectedTask.durationMinutes}분)
            </span>
            <h3 className="text-xl font-bold text-[#1e291b]">{selectedTask.title}</h3>
          </div>

          <div className="p-4 bg-[#f8faf7] border border-[#e4e7e3] rounded-2xl text-sm text-gray-600 leading-relaxed text-left">
            {selectedTask.description}
          </div>

          <p className="text-xs text-gray-400">
            ⏳ 조급하게 서두를 필요 없습니다. 미션을 가만히 음미하며 다 끝마치신 후 아래 완료 버튼을 눌러주세요.
          </p>

          <button
            onClick={handleCompleteTask}
            className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-700 text-white font-medium rounded-xl flex items-center justify-center calm-shadow transition-colors text-sm"
          >
            <CheckCircle className="w-5 h-5 mr-2" />
            미션을 무사히 완료했습니다
          </button>
        </div>
      )}

      {step === "AFTER" && selectedTask && (
        /* 행동 후 기분 입력 및 비교 */
        <div className="bg-white rounded-2xl p-6 border border-[#e4e7e3] calm-shadow space-y-6 text-center animate-fade-in">
          <div className="space-y-2">
            <span className="text-xs font-bold text-[#4a6c4c] bg-[#eaf2eb] px-2.5 py-1 rounded-full">
              STEP 3: 변화 확인
            </span>
            <h3 className="text-lg font-bold text-[#1e291b]">실천한 후 기분은 어떻게 달라졌나요?</h3>
            <p className="text-xs text-gray-400">사소한 움직임이 내 감정에 어떤 영향을 미치는지 숫자로 확인해 보세요.</p>
          </div>

          <div className="space-y-4 py-4">
            <span className="text-4xl font-extrabold text-[#4a6c4c]">{moodAfter} / 10</span>
            <input 
              type="range" 
              min="1" 
              max="10" 
              value={moodAfter} 
              onChange={(e) => setMoodAfter(parseInt(e.target.value))}
              className="w-full h-2 bg-[#e4e7e3] rounded-lg appearance-none cursor-pointer accent-[#4a6c4c]"
            />
          </div>

          <div className="p-4 bg-emerald-50 border border-emerald-100 rounded-2xl text-left text-xs text-emerald-800 space-y-1.5">
            <div className="flex items-center gap-1.5 font-bold">
              <Award className="w-4 h-4 text-emerald-600" />
              스스로를 칭찬해 주세요!
            </div>
            <p className="leading-relaxed">
              수고하셨습니다. 아주 작고 단순한 행동조차 우리의 기분을 긍정적인 방향으로 흔들 수 있는 충분한 힘을 가집니다.
            </p>
          </div>

          <button
            onClick={handleSaveAfter}
            className="w-full py-3.5 bg-[#4a6c4c] hover:bg-[#3b573d] text-white font-medium rounded-xl flex items-center justify-center calm-shadow transition-colors text-sm"
          >
            기록 완료하고 저장하기
          </button>
        </div>
      )}

    </div>
  );
}
