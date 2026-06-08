"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { localDB } from "@/lib/local-storage";
import { Smile, AlertCircle, Save } from "lucide-react";

const EMOTIONS = [
  { id: "joy", label: "기쁨 😊" },
  { id: "calm", label: "평온 😌" },
  { id: "excited", label: "설렘 🥰" },
  { id: "grateful", label: "감사 🙏" },
  { id: "sad", label: "슬픔 😢" },
  { id: "anxious", label: "불안 😰" },
  { id: "angry", label: "화남 😡" },
  { id: "tired", label: "피로 😴" },
  { id: "frustrated", label: "답답 😤" },
  { id: "lethargic", label: "무기력 😫" },
  { id: "okay", label: "평범 😐" },
  { id: "lonely", label: "외로움 👤" }
];

export default function CheckInPage() {
  const router = useRouter();
  const [mood, setMood] = useState<number>(5);
  const [stress, setStress] = useState<number>(5);
  const [sleep, setSleep] = useState<number>(5);
  const [energy, setEnergy] = useState<number>(5);
  const [selectedEmotions, setSelectedEmotions] = useState<string[]>([]);
  const [note, setNote] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const toggleEmotion = (label: string) => {
    if (selectedEmotions.includes(label)) {
      setSelectedEmotions(selectedEmotions.filter(e => e !== label));
    } else {
      setSelectedEmotions([...selectedEmotions, label]);
    }
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    // 저장 및 위기 감지
    const { crisisTriggered } = localDB.saveMoodEntry({
      mood,
      stress,
      sleep,
      energy,
      emotions: selectedEmotions,
      note
    });

    if (crisisTriggered) {
      // 위기 감지 시 즉각 위기 지원 페이지로 강제 리다이렉트
      router.push("/crisis");
    } else {
      // 일반 완료 시 대시보드로 이동
      router.push("/dashboard");
    }
  };

  const renderSlider = (
    label: string, 
    value: number, 
    setValue: (val: number) => void, 
    leftLabel: string, 
    rightLabel: string
  ) => {
    return (
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm font-semibold text-[#1e291b]">{label}</span>
          <span className="text-sm font-bold text-[#4a6c4c]">{value} / 10</span>
        </div>
        <input 
          type="range" 
          min="1" 
          max="10" 
          value={value} 
          onChange={(e) => setValue(parseInt(e.target.value))}
          className="w-full h-2 bg-[#e4e7e3] rounded-lg appearance-none cursor-pointer accent-[#4a6c4c]"
        />
        <div className="flex justify-between text-[11px] text-gray-400">
          <span>{leftLabel}</span>
          <span>{rightLabel}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold text-[#1e291b] tracking-tight">오늘의 마음 체크인</h1>
        <p className="text-xs text-gray-500">현재 느껴지는 몸과 마음의 상태를 있는 그대로 평정해 주세요.</p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        
        {/* 네 가지 핵심 마음 상태 척도 */}
        <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-5">
          <h2 className="text-sm font-bold text-[#4a6c4c] border-b border-gray-100 pb-2 flex items-center gap-1.5">
            <Smile className="w-4 h-4" /> 마음 지표 평정
          </h2>
          {renderSlider("기분 점수 (Mood)", mood, setMood, "매우 우울/불안", "매우 기쁘고 만족함")}
          {renderSlider("스트레스 정도 (Stress)", stress, setStress, "아주 편안함", "숨이 막힐 정도의 압박")}
          {renderSlider("수면 질 (Sleep Quality)", sleep, setSleep, "한 잠도 못 잠 / 개운치 않음", "깊고 개운하게 숙면")}
          {renderSlider("활력 에너지 (Energy)", energy, setEnergy, "완전한 방전", "활기가 가득 참")}
        </div>

        {/* 감정 칩 다중 선택 */}
        <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-3">
          <h2 className="text-sm font-bold text-[#4a6c4c] border-b border-gray-100 pb-2">
            오늘을 채운 구체적 감정 (복수 선택 가능)
          </h2>
          <div className="flex flex-wrap gap-2 pt-1">
            {EMOTIONS.map(em => {
              const selected = selectedEmotions.includes(em.label);
              return (
                <button
                  key={em.id}
                  type="button"
                  onClick={() => toggleEmotion(em.label)}
                  className={`px-3 py-1.5 rounded-full text-xs transition-all border ${
                    selected 
                      ? "bg-[#eaf2eb] border-[#4a6c4c] text-[#4a6c4c] font-medium" 
                      : "bg-[#f8faf7] border-[#e4e7e3] text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  {em.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* 한 줄 자유 메모 (위기 스크리닝 연동) */}
        <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-3">
          <div className="flex justify-between items-center border-b border-gray-100 pb-2">
            <h2 className="text-sm font-bold text-[#4a6c4c]">한 줄 노트 (선택 사항)</h2>
            <span className="text-[10px] text-emerald-600 font-semibold bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-100 flex items-center gap-0.5">
              <AlertCircle className="w-3 h-3" /> 안전 장치 작동 중
            </span>
          </div>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="지금 이 순간 떠오르는 생각이나 상황이 있다면 가볍게 기록해 보세요. (예: 오늘 발표가 긴장되었지만 잘 끝났다.)"
            rows={3}
            className="w-full text-sm p-3 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c] placeholder-gray-400"
          />
          <p className="text-[11px] text-gray-400 leading-normal">
            💡 입력하신 내용은 비식별화 처리되어 안전하게 저장되며, 위기 단어가 감지되면 안전 가이드가 자동으로 연결됩니다.
          </p>
        </div>

        {/* 저장 제출 */}
        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full py-3.5 bg-[#4a6c4c] hover:bg-[#3b573d] text-white font-medium rounded-xl flex items-center justify-center calm-shadow transition-colors text-sm"
        >
          <Save className="w-4 h-4 mr-2" />
          마음 체크인 완료 및 대시보드 저장
        </button>

      </form>
    </div>
  );
}
