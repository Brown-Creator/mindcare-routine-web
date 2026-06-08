"use client";

import { useEffect, useState } from "react";
import { localDB, JournalEntry } from "@/lib/local-storage";
import { journalPrompts } from "@/lib/seed-data";
import { Calendar, HelpCircle, Save, BookOpen, Trash2, Sparkles, Loader2, ChevronRight, Lock, Unlock } from "lucide-react";
import { useRouter } from "next/navigation";
import { encryptText, decryptText, isE2eeEnabled, getSessionPassword, setSessionPassword } from "@/lib/crypto";

export default function JournalPage() {
  const router = useRouter();
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [selectedPrompt, setSelectedPrompt] = useState<typeof journalPrompts[0] | null>(null);
  
  // 저널 작성 폼 상태
  const [answer, setAnswer] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>("");
  
  // AI 연동 상태
  const [aiResponse, setAiResponse] = useState<string>("");
  const [isAiLoading, setIsAiLoading] = useState<boolean>(false);

  // E2EE 추가 상태
  const [isLocked, setIsLocked] = useState<boolean>(false);
  const [lockPassword, setLockPassword] = useState<string>("");
  const [e2eeError, setE2eeError] = useState<string>("");

  useEffect(() => {
    checkLockState();
  }, []);

  const checkLockState = () => {
    const enabled = isE2eeEnabled();
    const pw = getSessionPassword();
    if (enabled && !pw) {
      setIsLocked(true);
    } else {
      setIsLocked(false);
      loadEntries(pw);
    }
  };

  const loadEntries = async (password?: string | null) => {
    const saved = localDB.getJournalEntries();
    const activePassword = password || getSessionPassword();
    if (activePassword) {
      const decrypted = await Promise.all(saved.map(async (entry) => {
        const decryptedContent = await decryptText(entry.answers.content, activePassword);
        return {
          ...entry,
          answers: { ...entry.answers, content: decryptedContent }
        };
      }));
      setEntries(decrypted);
    } else {
      setEntries(saved);
    }
  };

  const handleSelectPrompt = (prompt: typeof journalPrompts[0]) => {
    setSelectedPrompt(prompt);
    setAnswer("");
    setErrorMsg("");
    setAiResponse("");
    setIsAiLoading(false);
  };

  const handleCallAi = async (actionType: "SUMMARIZE" | "CBT_SUGGEST" | "ACTIVATION_SUGGEST") => {
    if (!answer.trim()) {
      setErrorMsg("성찰 일기 내용이 비어있어 AI 분석을 진행할 수 없습니다.");
      return;
    }
    setErrorMsg("");
    setIsAiLoading(true);
    setAiResponse("");

    try {
      const res = await fetch("/api/ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          journalText: answer,
          actionType
        })
      });
      const data = await res.json();
      
      if (data.crisisTriggered) {
        // 즉시 위기지원 강제 리다이렉트
        router.push("/crisis");
      } else {
        setAiResponse(data.result);
      }
    } catch (e) {
      console.error(e);
      setErrorMsg("AI 처리 중 에러가 발생했습니다. 잠시 후 다시 시도해 주세요.");
    } finally {
      setIsAiLoading(false);
    }
  };

  const handleUnlock = async (e: React.FormEvent) => {
    e.preventDefault();
    const testEnc = localStorage.getItem("mindcare_e2ee_test") || "";
    if (!testEnc) {
      setE2eeError("암호화 테스트 데이터가 유실되었습니다. 설정에서 재설정하세요.");
      return;
    }
    const dec = await decryptText(testEnc, lockPassword);
    if (dec === "session_test") {
      setSessionPassword(lockPassword);
      setIsLocked(false);
      setLockPassword("");
      setE2eeError("");
      loadEntries(lockPassword);
    } else {
      setE2eeError("잘못된 비밀번호입니다.");
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!answer.trim()) {
      setErrorMsg("성찰 일지 내용을 작성해 주세요.");
      return;
    }

    if (selectedPrompt) {
      setIsSubmitting(true);
      const password = getSessionPassword();
      const finalAnswer = password ? await encryptText(answer, password) : answer;

      const { crisisTriggered } = localDB.saveJournalEntry({
        promptId: selectedPrompt.id,
        promptText: selectedPrompt.prompt,
        answers: {
          content: finalAnswer
        }
      });

      if (crisisTriggered) {
        router.push("/crisis");
      } else {
        setSelectedPrompt(null);
        setAnswer("");
        loadEntries(password);
      }
      setIsSubmitting(false);
    }
  };

  if (isLocked) {
    return (
      <div className="max-w-md mx-auto my-12 bg-white rounded-2xl p-6 border border-[#e4e7e3] calm-shadow text-center space-y-5 animate-fade-in">
        <Lock className="w-12 h-12 text-[#d89657] mx-auto" />
        <div className="space-y-1">
          <h1 className="text-base font-bold text-[#1e291b]">E2EE 저널 보관함 잠김</h1>
          <p className="text-xs text-gray-500 leading-relaxed">
            성찰 일지가 기기 수준에서 강력하게 종단간 암호화(E2EE) 처리되어 있습니다. 일지를 조회하고 작성하려면 설정하신 마스터 비밀번호를 입력해 잠금을 해제해 주세요.
          </p>
        </div>
        <form onSubmit={handleUnlock} className="space-y-3 text-left">
          <input 
            type="password"
            value={lockPassword}
            onChange={(e) => setLockPassword(e.target.value)}
            placeholder="마스터 비밀번호 입력"
            className="w-full text-xs p-3 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c]"
          />
          {e2eeError && <p className="text-[10px] text-red-500 font-semibold">{e2eeError}</p>}
          <button
            type="submit"
            className="w-full py-3 bg-[#4a6c4c] hover:bg-[#3b573d] text-white font-bold rounded-xl text-xs transition-colors flex items-center justify-center gap-1.5"
          >
            <Unlock className="w-4 h-4" /> 잠금 해제 및 복호화
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-0.5">
        <h1 className="text-2xl font-bold text-[#1e291b] tracking-tight">관계와 감정 패턴 돌아보기</h1>
        <p className="text-xs text-gray-500">내 대인관계 속에서 반복적으로 나타나는 마음의 고유한 습관적 패턴을 성찰합니다.</p>
      </div>

      {selectedPrompt ? (
        /* 저널 작성 화면 */
        <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-5 animate-fade-in">
          <div className="flex justify-between items-center border-b border-gray-100 pb-3">
            <h2 className="text-sm font-bold text-[#4a6c4c] flex items-center gap-1.5">
              <BookOpen className="w-4 h-4" /> 저널 작성하기
            </h2>
            <button 
              onClick={() => setSelectedPrompt(null)}
              className="text-xs text-gray-400 hover:text-gray-600 font-medium"
            >
              목록으로
            </button>
          </div>

          <form onSubmit={handleSave} className="space-y-4">
            <div className="space-y-2">
              <span className="text-xs font-bold text-amber-600 bg-amber-50 px-2 py-0.5 rounded border border-amber-100">
                성찰 질문
              </span>
              <h3 className="text-sm font-bold text-[#1e291b] leading-relaxed">
                {selectedPrompt.prompt}
              </h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                {selectedPrompt.description}
              </p>
            </div>

            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="내 생각과 기분을 자유롭고 솔직하게 기록해 보세요. (의학적 판단이나 병리를 찾으려는 평가는 내리지 않으며, 내 마음 상태에 대한 사실적 나열에 가치를 둡니다.)"
              rows={8}
              className="w-full text-sm p-4 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c] placeholder-gray-400 leading-relaxed"
            />

            {/* AI 보조 컨트롤 */}
            <div className="bg-[#f8faf7] border border-[#e4e7e3] p-4 rounded-xl space-y-3">
              <div className="flex items-center gap-1.5 text-xs font-bold text-[#4a6c4c]">
                <Sparkles className="w-4 h-4 text-[#d89657] fill-[#d89657]" />
                AI 자가성찰 피드백 (보조 도구)
              </div>
              <p className="text-[10px] text-gray-400 leading-normal">
                작성하신 성찰 글에 대한 건조한 요약 및 CBT 추가 질문을 건의받아 볼 수 있습니다.
              </p>
              
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => handleCallAi("SUMMARIZE")}
                  disabled={isAiLoading || !answer.trim()}
                  className="px-2.5 py-1.5 bg-white border border-gray-200 hover:bg-[#eaf2eb]/30 text-[#4a6c4c] rounded-lg text-[11px] font-semibold transition-all disabled:opacity-40 flex items-center gap-1"
                >
                  {isAiLoading && <Loader2 className="w-3 h-3 animate-spin" />}
                  중립 요약 받기
                </button>
                <button
                  type="button"
                  onClick={() => handleCallAi("CBT_SUGGEST")}
                  disabled={isAiLoading || !answer.trim()}
                  className="px-2.5 py-1.5 bg-white border border-gray-200 hover:bg-[#eaf2eb]/30 text-[#4a6c4c] rounded-lg text-[11px] font-semibold transition-all disabled:opacity-40 flex items-center gap-1"
                >
                  {isAiLoading && <Loader2 className="w-3 h-3 animate-spin" />}
                  CBT 사고 질문 건의
                </button>
              </div>

              {aiResponse && (
                <div className="mt-3 p-3 bg-white border border-[#e4e7e3] rounded-xl text-xs text-gray-600 space-y-1.5 leading-relaxed">
                  <p className="whitespace-pre-line text-[11px]">{aiResponse}</p>
                </div>
              )}
            </div>

            {errorMsg && (
              <p className="text-xs text-red-500 font-semibold">{errorMsg}</p>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3.5 bg-[#4a6c4c] hover:bg-[#3b573d] text-white font-medium rounded-xl flex items-center justify-center calm-shadow transition-colors text-sm"
            >
              <Save className="w-4 h-4 mr-2" />
              성찰 일기 저장하기
            </button>
          </form>
        </div>
      ) : (
        /* 성찰 질문 선택 및 과거 이력 리스트 */
        <div className="space-y-5">
          <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-2">
            <h2 className="text-sm font-bold text-[#4a6c4c] flex items-center gap-1.5">
              <HelpCircle className="w-4 h-4 text-[#d89657] fill-[#d89657]" /> 질문 가이드라인
            </h2>
            <p className="text-xs text-gray-500 leading-relaxed">
              성찰 일지는 스스로 상처나 트라우마를 해석하거나 병리적 낙인을 찍지 않는 안전한 기록입니다. 아래 질문 중 오늘 나에게 와닿는 질문 하나를 골라 시작해 보세요.
            </p>
          </div>

          {/* 질문 리스트 */}
          <div className="space-y-2">
            <h3 className="text-xs font-bold text-gray-400">성찰 유도 프롬프트</h3>
            <div className="grid grid-cols-1 gap-2">
              {journalPrompts.map(jp => {
                return (
                  <button
                    key={jp.id}
                    onClick={() => handleSelectPrompt(jp)}
                    className="flex justify-between items-center p-3.5 bg-white border border-[#e4e7e3] rounded-2xl hover:bg-[#eaf2eb]/30 transition-all text-left calm-shadow"
                  >
                    <span className="text-xs font-semibold text-[#1e291b] pr-4 leading-normal">{jp.prompt}</span>
                    <ChevronRight className="w-4 h-4 text-gray-300 shrink-0" />
                  </button>
                );
              })}
            </div>
          </div>

          {/* 과거 기록 리스트 */}
          {entries.length > 0 && (
            <div className="space-y-3 pt-2">
              <h3 className="text-xs font-bold text-gray-400">나의 성찰 일지 히스토리</h3>
              <div className="space-y-3">
                {entries.map(entry => {
                  return (
                    <div key={entry.id} className="bg-white rounded-2xl p-4 border border-[#e4e7e3] calm-shadow space-y-3">
                      <div className="flex justify-between items-start border-b border-gray-50 pb-2">
                        <span className="text-[10px] text-gray-400 font-semibold flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5" />
                          {new Date(entry.timestamp).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="space-y-1.5 text-xs">
                        <h4 className="font-bold text-[#4a6c4c] leading-relaxed">Q. {entry.promptText}</h4>
                        <p className="text-gray-700 leading-relaxed bg-[#f8faf7] p-3 rounded-xl border border-gray-100 whitespace-pre-wrap">
                          {entry.answers.content}
                        </p>
                      </div>
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
