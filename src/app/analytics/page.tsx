"use client";

import { useEffect, useState } from "react";
import { localDB, MoodEntry, ThoughtRecord } from "@/lib/local-storage";
import { isE2eeEnabled, getSessionPassword, decryptText } from "@/lib/crypto";
import { BarChart2, TrendingUp, Compass, AlertCircle, RefreshCw, ChevronLeft } from "lucide-react";
import Link from "next/link";

interface DistortionStat {
  name: string;
  count: number;
  color: string;
}

export default function AnalyticsPage() {
  const [moodEntries, setMoodEntries] = useState<MoodEntry[]>([]);
  const [distortionStats, setDistortionStats] = useState<DistortionStat[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [e2eeLocked, setE2eeLocked] = useState<boolean>(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    
    // E2EE 잠금 검사
    const e2ee = isE2eeEnabled();
    const pw = getSessionPassword();
    if (e2ee && !pw) {
      setE2eeLocked(true);
      setLoading(false);
      return;
    }

    // 1. 기분 데이터 가져오기
    const moods = localDB.getMoodEntries();
    setMoodEntries(moods.slice(0, 15).reverse()); // 최근 15개만 차트에 표시

    // 2. CBT 데이터를 가져와 복호화 후 인지 왜곡 키워드 분석
    const savedCbt = localDB.getThoughtRecords();
    let cbtRecords: ThoughtRecord[] = [];
    
    if (pw) {
      cbtRecords = await Promise.all(savedCbt.map(async (r) => {
        return {
          ...r,
          situation: await decryptText(r.situation, pw),
          automaticThought: await decryptText(r.automaticThought, pw),
          evidenceFor: await decryptText(r.evidenceFor, pw),
          evidenceAgainst: await decryptText(r.evidenceAgainst, pw),
          alternativeThought: await decryptText(r.alternativeThought, pw)
        };
      }));
    } else {
      cbtRecords = savedCbt;
    }

    // 인지 왜곡 분석 사전 정의 및 어근 분류 매칭
    const distortions = {
      "흑백논리 / 전부 아니면 전무": { count: 0, keywords: ["항상", "절대", "다 ", "하나도", "모두", "완벽", "꼭 "], color: "#e07a5f" },
      "파국화 (과장된 재앙 추측)": { count: 0, keywords: ["망했", "최악", "끝장", "끝이", "절대 안", "절망"], color: "#3d5a80" },
      "감정적 추론 (기분이 곧 사실)": { count: 0, keywords: ["느낌", "기분이", "느껴져", "불안해서", "그냥 싫"], color: "#f4a261" },
      "임의적 추론 / 마음 읽기": { count: 0, keywords: ["분명", "생각할 거야", "미워할", "눈빛", "눈치"], color: "#2a9d8f" },
      "개인화 (부정 사건을 내 탓으로)": { count: 0, keywords: ["나 때문에", "내 탓", "내 잘못", "나만 없었"], color: "#81b29a" }
    };

    cbtRecords.forEach(r => {
      const fullText = `${r.situation} ${r.automaticThought} ${r.evidenceFor}`;
      Object.entries(distortions).forEach(([name, def]) => {
        def.keywords.forEach(kw => {
          if (fullText.includes(kw)) {
            def.count += 1;
          }
        });
      });
    });

    const statsArray = Object.entries(distortions).map(([name, def]) => ({
      name,
      count: def.count,
      color: def.color
    })).filter(s => s.count > 0);

    setDistortionStats(statsArray);
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[300px] space-y-3">
        <RefreshCw className="w-8 h-8 text-[#4a6c4c] animate-spin" />
        <p className="text-xs text-gray-400">마음 건강 리포트를 분석 중입니다...</p>
      </div>
    );
  }

  if (e2eeLocked) {
    return (
      <div className="max-w-md mx-auto my-12 bg-white rounded-2xl p-6 border border-[#e4e7e3] calm-shadow text-center space-y-5">
        <AlertCircle className="w-12 h-12 text-[#d89657] mx-auto" />
        <div className="space-y-1">
          <h1 className="text-base font-bold text-[#1e291b]">분석 리포트 조회 잠김</h1>
          <p className="text-xs text-gray-500 leading-relaxed">
            통계 분석에 사용되는 인지행동치료(CBT) 기록지가 암호화되어 있어 리포트를 산출할 수 없습니다. 
            먼저 <Link href="/cbt" className="text-[#4a6c4c] font-bold underline">CBT 페이지</Link> 또는 <Link href="/journal" className="text-[#4a6c4c] font-bold underline">저널 페이지</Link>에서 잠금을 해제해 주세요.
          </p>
        </div>
      </div>
    );
  }

  // SVG Line Chart 값 계산
  const chartHeight = 150;
  const chartWidth = 500;
  const padding = 25;
  const points = moodEntries.map((e, idx) => {
    const x = padding + (idx * (chartWidth - padding * 2)) / Math.max(1, moodEntries.length - 1);
    const y = chartHeight - padding - ((e.mood - 1) * (chartHeight - padding * 2)) / 9;
    return { x, y, score: e.mood, date: new Date(e.timestamp).toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" }) };
  });

  const linePath = points.map((p, idx) => `${idx === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");

  // 도넛 차트 누적 각도 계산용
  const totalDistortions = distortionStats.reduce((sum, s) => sum + s.count, 0);
  let accumulatedAngle = 0;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center gap-2">
        <Link href="/dashboard" className="p-1 hover:bg-[#eaf2eb] rounded-lg text-gray-500 transition-colors">
          <ChevronLeft className="w-5 h-5" />
        </Link>
        <div className="space-y-0.5">
          <h1 className="text-2xl font-bold text-[#1e291b] tracking-tight">마음 건강 분석 통계</h1>
          <p className="text-xs text-gray-500">누적된 감정과 인지 왜곡 습관을 객관적으로 추적합니다.</p>
        </div>
      </div>

      {/* 1. 기분 트렌드 SVG 선그래프 */}
      <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-4">
        <h2 className="text-sm font-bold text-[#4a6c4c] flex items-center gap-1.5">
          <TrendingUp className="w-4.5 h-4.5" /> 기분 변동 추이 (최근 15회)
        </h2>
        
        {moodEntries.length < 2 ? (
          <p className="text-xs text-gray-400 text-center py-8">
            충분한 통계를 쌓기 위해 기분 체크인을 최소 2회 이상 작성해 주세요.
          </p>
        ) : (
          <div className="overflow-x-auto pt-2">
            <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full min-w-[450px] overflow-visible">
              {[1, 5, 10].map(score => {
                const y = chartHeight - padding - ((score - 1) * (chartHeight - padding * 2)) / 9;
                return (
                  <g key={score}>
                    <line x1={padding} y1={y} x2={chartWidth - padding} y2={y} stroke="#f0f2f0" strokeDasharray="3,3" />
                    <text x={5} y={y + 4} className="text-[9px] fill-gray-400 font-bold">{score}점</text>
                  </g>
                );
              })}

              <defs>
                <linearGradient id="chart-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#4a6c4c" stopOpacity="0.2" />
                  <stop offset="100%" stopColor="#4a6c4c" stopOpacity="0.0" />
                </linearGradient>
              </defs>

              {points.length > 0 && (
                <path
                  d={`${linePath} L ${points[points.length - 1].x} ${chartHeight - padding} L ${points[0].x} ${chartHeight - padding} Z`}
                  fill="url(#chart-grad)"
                />
              )}

              <path d={linePath} fill="none" stroke="#4a6c4c" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

              {points.map((p, idx) => (
                <g key={idx} className="group cursor-pointer">
                  <circle cx={p.x} cy={p.y} r="4" fill="#4a6c4c" stroke="#ffffff" strokeWidth="1.5" />
                  <text x={p.x} y={p.y - 10} textAnchor="middle" className="text-[9px] font-bold fill-[#4a6c4c] opacity-0 group-hover:opacity-100 transition-opacity">
                    {p.score}점
                  </text>
                  <text x={p.x} y={chartHeight - 6} textAnchor="middle" className="text-[8px] fill-gray-400 font-semibold">
                    {p.date}
                  </text>
                </g>
              ))}
            </svg>
          </div>
        )}
      </div>

      {/* 2. CBT 인지왜곡 도넛 차트 */}
      <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-4">
        <h2 className="text-sm font-bold text-[#4a6c4c] flex items-center gap-1.5">
          <BarChart2 className="w-4.5 h-4.5" /> 인지 왜곡 주요 습관 패턴
        </h2>

        {totalDistortions === 0 ? (
          <div className="bg-[#f8faf7] border border-gray-100 p-6 rounded-2xl text-center space-y-1">
            <p className="text-xs text-gray-500 font-bold">탐지된 인지 왜곡 유형이 아직 없습니다.</p>
            <p className="text-[10px] text-gray-400 leading-normal">
              CBT 사고 기록지에서 부정적인 생각이 들 때 상황과 근거를 작성하면 왜곡 키워드가 여기 자동으로 분류되어 리포트로 누적됩니다.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
            
            <div className="flex justify-center">
              <svg width="180" height="180" viewBox="0 0 42 42" className="overflow-visible">
                <circle cx="21" cy="21" r="15.915" fill="transparent" stroke="#f0f2f0" strokeWidth="4.5" />
                
                {distortionStats.map((stat, idx) => {
                  const percentage = (stat.count / totalDistortions) * 100;
                  const strokeDasharray = `${percentage} ${100 - percentage}`;
                  const strokeDashoffset = 100 - accumulatedAngle + 25; // 12시 방향부터 시작하도록 +25 보정
                  accumulatedAngle += percentage;
                  
                  return (
                    <circle
                      key={idx}
                      cx="21"
                      cy="21"
                      r="15.915"
                      fill="transparent"
                      stroke={stat.color}
                      strokeWidth="5"
                      strokeDasharray={strokeDasharray}
                      strokeDashoffset={strokeDashoffset}
                    />
                  );
                })}

                <g>
                  <text x="50%" y="46%" textAnchor="middle" className="text-[4px] font-bold fill-gray-400">
                    총 탐지수
                  </text>
                  <text x="50%" y="60%" textAnchor="middle" className="text-[7px] font-extrabold fill-[#4a6c4c]">
                    {totalDistortions}회
                  </text>
                </g>
              </svg>
            </div>

            <div className="space-y-3">
              <h3 className="text-xs font-bold text-gray-400">탐지 빈도 순위</h3>
              <div className="space-y-2.5">
                {distortionStats.sort((a,b) => b.count - a.count).map((stat, idx) => {
                  const pct = Math.round((stat.count / totalDistortions) * 100);
                  return (
                    <div key={idx} className="flex justify-between items-center text-xs">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: stat.color }} />
                        <span className="font-semibold text-gray-700">{stat.name}</span>
                      </div>
                      <span className="font-bold text-gray-500 bg-gray-50 px-2 py-0.5 rounded border border-gray-100 shrink-0">
                        {stat.count}회 ({pct}%)
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

          </div>
        )}
      </div>

      {/* 3. 코핑 팁 카드 */}
      <div className="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 flex gap-3 text-xs text-[#2c4731] leading-relaxed calm-shadow">
        <Compass className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <h3 className="font-bold">심리 웰니스 분석 코칭</h3>
          <p className="text-gray-600 text-[11px] leading-relaxed">
            자주 나타나는 인지 왜곡은 나를 보호하기 위한 낡은 무의식 방어 패턴입니다. 
            왜곡이 많이 잡히더라도 나를 책망하기보다는, "내가 상황을 이렇게 해석하고 있구나" 하고 제3자의 관점에서 그저 알아차려 주는(Mindful) 태도가 마음 웰니스의 핵심 열쇠입니다.
          </p>
        </div>
      </div>
    </div>
  );
}
