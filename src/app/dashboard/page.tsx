"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { localDB, MoodEntry } from "@/lib/local-storage";
import { 
  Heart, 
  Smile, 
  Calendar, 
  BookOpen, 
  Sparkles, 
  Activity, 
  Flame, 
  ChevronRight, 
  CheckCircle,
  FileSpreadsheet
} from "lucide-react";

export default function Dashboard() {
  const [moodEntries, setMoodEntries] = useState<MoodEntry[]>([]);
  const [streak, setStreak] = useState<number>(0);
  const [routineStatus, setRoutineStatus] = useState({
    checkIn: false,
    cbt: false,
    activation: false,
    mindfulness: false,
    journal: false
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      const entries = localDB.getMoodEntries();
      setMoodEntries(entries);

      // 연속 기록일(Streak) 계산 (오늘 포함 연속 기록된 날들 계산, 죄책감 유도 방지)
      if (entries.length > 0) {
        let currentStreak = 0;
        let lastDate: Date | null = null;
        
        // 간단한 연속 일수 추산 (하루에 한 번 이상 기록했는가)
        const datesOnly = entries.map(e => new Date(e.timestamp).toDateString());
        const uniqueDates = Array.from(new Set(datesOnly));
        
        let today = new Date().toDateString();
        let yesterday = new Date(Date.now() - 86400000).toDateString();
        
        if (uniqueDates.includes(today) || uniqueDates.includes(yesterday)) {
          // 연속 카운트
          currentStreak = uniqueDates.length;
        }
        setStreak(currentStreak);
      }

      // 오늘 완료한 루틴 상태 업데이트
      const todayString = new Date().toDateString();
      const checkInDone = entries.some(e => new Date(e.timestamp).toDateString() === todayString);
      
      const cbtRecords = localDB.getThoughtRecords();
      const cbtDone = cbtRecords.some(e => new Date(e.timestamp).toDateString() === todayString);

      const actSessions = localDB.getActivationSessions();
      const actDone = actSessions.some(e => new Date(e.timestamp).toDateString() === todayString);

      const mindSessions = localDB.getMindfulnessSessions();
      const mindDone = mindSessions.some(e => new Date(e.timestamp).toDateString() === todayString);

      const journalEntries = localDB.getJournalEntries();
      const journalDone = journalEntries.some(e => new Date(e.timestamp).toDateString() === todayString);

      setRoutineStatus({
        checkIn: checkInDone,
        cbt: cbtDone,
        activation: actDone,
        mindfulness: mindDone,
        journal: journalDone
      });
    }
  }, []);

  // 차트 렌더링용 데이터 정렬 (오래된 순)
  const chartData = [...moodEntries].slice(0, 7).reverse();

  // 커스텀 SVG 차트 그리기
  const renderTrendChart = () => {
    if (chartData.length === 0) {
      return (
        <div className="h-40 flex items-center justify-center border border-dashed border-[#e4e7e3] rounded-xl text-xs text-gray-400 p-4 text-center">
          아직 기분 상태 기록이 없습니다.<br />오늘 마음 체크인을 시작해 흐름을 기록해 보세요.
        </div>
      );
    }

    const width = 350;
    const height = 150;
    const padding = 20;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    const getCoordinates = (index: number, val: number) => {
      const x = padding + (index / (chartData.length - 1 || 1)) * chartWidth;
      const y = height - padding - ((val - 1) / 9) * chartHeight; // 1-10 점수를 높이 매핑
      return { x, y };
    };

    // 점들을 이어주는 SVG 패스 생성 함수
    const generatePath = (key: keyof Pick<MoodEntry, "mood" | "stress" | "sleep" | "energy">) => {
      return chartData.map((d, i) => {
        const { x, y } = getCoordinates(i, d[key] as number);
        return `${i === 0 ? "M" : "L"} ${x} ${y}`;
      }).join(" ");
    };

    return (
      <div className="space-y-4">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full bg-[#f8faf7] border border-gray-100 rounded-xl">
          {/* 가로 보조선 (눈금) */}
          {[1, 5, 10].map((val) => {
            const y = height - padding - ((val - 1) / 9) * chartHeight;
            return (
              <g key={val}>
                <line x1={padding} y1={y} x2={width - padding} y2={y} stroke="#e4e7e3" strokeDasharray="3" />
                <text x={padding - 5} y={y + 3} textAnchor="end" className="text-[9px] fill-gray-400 font-semibold">{val}</text>
              </g>
            );
          })}

          {/* 선 그리기 */}
          <path d={generatePath("mood")} fill="none" stroke="#4a6c4c" strokeWidth="2.5" strokeLinecap="round" />
          <path d={generatePath("stress")} fill="none" stroke="#d89657" strokeWidth="1.5" strokeDasharray="2" strokeLinecap="round" />
          <path d={generatePath("sleep")} fill="none" stroke="#5c7f8c" strokeWidth="1.5" strokeLinecap="round" />

          {/* 데이터 마커(점) */}
          {chartData.map((d, i) => {
            const { x, y } = getCoordinates(i, d.mood);
            return (
              <circle key={d.id} cx={x} cy={y} r="4" className="fill-[#4a6c4c] stroke-white stroke-2" />
            );
          })}
        </svg>

        {/* 법례 */}
        <div className="flex justify-center gap-4 text-[10px] text-gray-500 font-medium">
          <div className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 bg-[#4a6c4c] rounded-full"></span>
            기분 (Mood)
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 bg-[#d89657] rounded-full"></span>
            스트레스 (Stress)
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 bg-[#5c7f8c] rounded-full"></span>
            수면 질 (Sleep)
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6 animate-fade-in">
      
      {/* 웰컴 섹션 및 응원 메시지 */}
      <div className="flex justify-between items-start">
        <div className="space-y-0.5">
          <h1 className="text-2xl font-bold text-[#1e291b] tracking-tight">오늘 하루도 고생 많으셨어요</h1>
          <p className="text-xs text-gray-500">내 상태를 친절하게 돌아보고 오늘 루틴을 이어보세요.</p>
        </div>
        
        {/* 온화한 스트릭 시각화 */}
        <div className="bg-[#eaf2eb] text-[#4a6c4c] px-3 py-1.5 rounded-2xl flex items-center gap-1.5 border border-[#cbe1cd]/40">
          <Flame className="w-4 h-4 fill-[#4a6c4c]" />
          <span className="text-xs font-bold">{streak}일째 실천 중</span>
        </div>
      </div>

      {/* 1. 추천 루틴 세션 */}
      <div className="space-y-3">
        <h2 className="text-sm font-bold text-[#4a6c4c] flex items-center gap-1">
          <Sparkles className="w-4 h-4 text-[#d89657] fill-[#d89657]" /> 
          오늘의 추천 마음 루틴
        </h2>
        
        <div className="space-y-2">
          {/* A. 감정 체크인 */}
          <Link 
            href="/check-in"
            className="flex items-center justify-between p-4 bg-white border border-[#e4e7e3] rounded-2xl hover:bg-[#eaf2eb]/30 transition-all calm-shadow"
          >
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl ${routineStatus.checkIn ? "bg-[#eaf2eb] text-[#4a6c4c]" : "bg-gray-50 text-gray-400"}`}>
                {routineStatus.checkIn ? <CheckCircle className="w-5 h-5" /> : <Smile className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#1e291b]">오늘의 기분 체크인</h3>
                <p className="text-xs text-gray-400">내 감정과 스트레스 상태 마킹하기 • 2분</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-gray-300" />
          </Link>

          {/* B. CBT 인지행동 기록 */}
          <Link 
            href="/cbt"
            className="flex items-center justify-between p-4 bg-white border border-[#e4e7e3] rounded-2xl hover:bg-[#eaf2eb]/30 transition-all calm-shadow"
          >
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl ${routineStatus.cbt ? "bg-[#eaf2eb] text-[#4a6c4c]" : "bg-gray-50 text-gray-400"}`}>
                {routineStatus.cbt ? <CheckCircle className="w-5 h-5" /> : <BookOpen className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#1e291b]">CBT 인지 오류 점검</h3>
                <p className="text-xs text-gray-400">머릿속 부정적 사고 회로의 객관적 비평 • 5분</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-gray-300" />
          </Link>

          {/* C. 행동 활성화 태스크 */}
          <Link 
            href="/activation"
            className="flex items-center justify-between p-4 bg-white border border-[#e4e7e3] rounded-2xl hover:bg-[#eaf2eb]/30 transition-all calm-shadow"
          >
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl ${routineStatus.activation ? "bg-[#eaf2eb] text-[#4a6c4c]" : "bg-gray-50 text-gray-400"}`}>
                {routineStatus.activation ? <CheckCircle className="w-5 h-5" /> : <Activity className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#1e291b]">초소형 행동 실천</h3>
                <p className="text-xs text-gray-400">기분에 영향을 미치는 아주 간단한 미션 • 3분</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-gray-300" />
          </Link>

          {/* D. 마음챙김 호흡 */}
          <Link 
            href="/mindfulness"
            className="flex items-center justify-between p-4 bg-white border border-[#e4e7e3] rounded-2xl hover:bg-[#eaf2eb]/30 transition-all calm-shadow"
          >
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl ${routineStatus.mindfulness ? "bg-[#eaf2eb] text-[#4a6c4c]" : "bg-gray-50 text-gray-400"}`}>
                {routineStatus.mindfulness ? <CheckCircle className="w-5 h-5" /> : <Sparkles className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#1e291b]">3분 마음챙김 명상</h3>
                <p className="text-xs text-gray-400">가만히 앉아 숨의 감각에 마음 안착시키기 • 3분</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-gray-300" />
          </Link>

          {/* E. 성찰 일기 */}
          <Link 
            href="/journal"
            className="flex items-center justify-between p-4 bg-white border border-[#e4e7e3] rounded-2xl hover:bg-[#eaf2eb]/30 transition-all calm-shadow"
          >
            <div className="flex items-center gap-3">
              <div className={`p-2.5 rounded-xl ${routineStatus.journal ? "bg-[#eaf2eb] text-[#4a6c4c]" : "bg-gray-50 text-gray-400"}`}>
                {routineStatus.journal ? <CheckCircle className="w-5 h-5" /> : <Calendar className="w-5 h-5" />}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[#1e291b]">관계 및 감정 패턴 성찰 저널</h3>
                <p className="text-xs text-gray-400">내 반복적 감정 반응의 숨은 욕구 찾기 • 5분</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-gray-300" />
          </Link>
        </div>
      </div>

      {/* 2. 주간 기분 흐름 트렌드 (비진단 차트) */}
      <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-3">
        <div className="flex justify-between items-center flex-wrap gap-2">
          <h2 className="text-sm font-bold text-[#4a6c4c]">최근 기분 추이 (주간 트렌드)</h2>
          <div className="flex items-center gap-1.5">
            <Link href="/analytics" className="text-[11px] font-semibold text-[#4a6c4c] bg-[#eaf2eb] px-2 py-1 rounded hover:bg-[#cbe1cd]/40 transition-colors flex items-center gap-0.5">
              <Activity className="w-3.5 h-3.5" /> 상세 분석 보고서
            </Link>
            <Link href="/screening" className="text-[11px] font-semibold text-gray-500 bg-gray-50 border border-gray-200 px-2 py-1 rounded hover:bg-gray-100 transition-colors flex items-center gap-0.5">
              <FileSpreadsheet className="w-3 h-3" /> 우울 자가선별 (PHQ-9)
            </Link>
          </div>
        </div>
        
        {renderTrendChart()}
        
        <p className="text-[10px] text-gray-400 text-center leading-normal">
          기록 점수의 높낮이는 의학적 평가 지표가 아니며, 감정 추이를 가시화하여 마음을 점검하는 자기성찰 참고용입니다.
        </p>
      </div>

      {/* 죄책감 배제 멘트 */}
      <div className="bg-[#eaf2eb]/40 rounded-xl p-3 border border-[#cbe1cd]/20 text-center text-xs text-[#4a6c4c] font-medium leading-relaxed">
        🍀 하루쯤 기록을 깜빡해도 괜찮습니다. 마음관리는 속도가 아닌 내 상태에 따뜻하게 관심을 주는 방향 자체가 가장 소중합니다.
      </div>

    </div>
  );
}
