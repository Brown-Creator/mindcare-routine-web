"use client";

import { useEffect, useState } from "react";
import { localDB, ThoughtRecord } from "@/lib/local-storage";
import { cbtPrompts } from "@/lib/seed-data";
import { BookOpen, CheckCircle, ChevronLeft, ChevronRight, HelpCircle, Plus, Trash2, ArrowLeft, Lock, Unlock } from "lucide-react";
import { classifyCrisisText } from "@/lib/safety-classifier";
import { useRouter } from "next/navigation";
import { encryptText, decryptText, isE2eeEnabled, getSessionPassword, setSessionPassword } from "@/lib/crypto";

export default function CbtPage() {
  const router = useRouter();
  const [records, setRecords] = useState<ThoughtRecord[]>([]);
  const [showForm, setShowForm] = useState<boolean>(false);
  
  // E2EE 추가 상태
  const [isLocked, setIsLocked] = useState<boolean>(false);
  const [lockPassword, setLockPassword] = useState<string>("");
  const [e2eeError, setE2eeError] = useState<string>("");

  // 폼 입력 상태
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [situation, setSituation] = useState<string>("");
  const [automaticThought, setAutomaticThought] = useState<string>("");
  const [emotions, setEmotions] = useState<string>("");
  const [evidenceFor, setEvidenceFor] = useState<string>("");
  const [evidenceAgainst, setEvidenceAgainst] = useState<string>("");
  const [alternativeThought, setAlternativeThought] = useState<string>("");
  const [nextAction, setNextAction] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

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
      loadRecords(pw);
    }
  };

  const loadRecords = async (password?: string | null) => {
    const saved = localDB.getThoughtRecords();
    const activePassword = password || getSessionPassword();
    if (activePassword) {
      const decrypted = await Promise.all(saved.map(async (r) => {
        return {
          ...r,
          situation: await decryptText(r.situation, activePassword),
          automaticThought: await decryptText(r.automaticThought, activePassword),
          evidenceFor: await decryptText(r.evidenceFor, activePassword),
          evidenceAgainst: await decryptText(r.evidenceAgainst, activePassword),
          alternativeThought: await decryptText(r.alternativeThought, activePassword),
          nextAction: await decryptText(r.nextAction, activePassword)
        };
      }));
      setRecords(decrypted);
    } else {
      setRecords(saved);
    }
  };

  const handleNext = () => {
    // 유효성 체크
    if (currentStep === 0 && !situation.trim()) {
      setErrorMsg("상황을 간략히 작성해 주세요.");
      return;
    }
    if (currentStep === 1 && !automaticThought.trim()) {
      setErrorMsg("떠오른 자동적 사고를 적어주세요.");
      return;
    }
    if (currentStep === 2 && !emotions.trim()) {
      setErrorMsg("감정 종류와 강도를 적어주세요.");
      return;
    }
    if (currentStep === 3 && !evidenceFor.trim()) {
      setErrorMsg("생각을 뒷받침하는 객관적인 사실을 적어주세요.");
      return;
    }
    if (currentStep === 4 && !evidenceAgainst.trim()) {
      setErrorMsg("생각에 반대되는 사실적 근거를 적어주세요.");
      return;
    }
    
    setErrorMsg("");
    setCurrentStep(prev => prev + 1);
  };

  const handlePrev = () => {
    setErrorMsg("");
    setCurrentStep(prev => Math.max(0, prev - 1));
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
      loadRecords(lockPassword);
    } else {
      setE2eeError("잘못된 비밀번호입니다.");
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!alternativeThought.trim() || !nextAction.trim()) {
      setErrorMsg("마지막 단계의 대안 사고와 실천 행동을 채워주세요.");
      return;
    }

    const password = getSessionPassword();
    const encSituation = password ? await encryptText(situation, password) : situation;
    const encAutomatic = password ? await encryptText(automaticThought, password) : automaticThought;
    const encEvidenceFor = password ? await encryptText(evidenceFor, password) : evidenceFor;
    const encEvidenceAgainst = password ? await encryptText(evidenceAgainst, password) : evidenceAgainst;
    const encAlternative = password ? await encryptText(alternativeThought, password) : alternativeThought;
    const encNextAction = password ? await encryptText(nextAction, password) : nextAction;

    const { crisisTriggered } = localDB.saveThoughtRecord({
      situation: encSituation,
      automaticThought: encAutomatic,
      emotions,
      evidenceFor: encEvidenceFor,
      evidenceAgainst: encEvidenceAgainst,
      alternativeThought: encAlternative,
      nextAction: encNextAction
    });

    if (crisisTriggered) {
      router.push("/crisis");
    } else {
      // 초기화 및 리프레시
      setSituation("");
      setAutomaticThought("");
      setEmotions("");
      setEvidenceFor("");
      setEvidenceAgainst("");
      setAlternativeThought("");
      setNextAction("");
      setCurrentStep(0);
      setShowForm(false);
      loadRecords(password);
    }
  };

  const handleDelete = (id: string) => {
    if (confirm("이 CBT 사고기록을 영구히 삭제하시겠습니까?")) {
      localDB.deleteThoughtRecord(id);
      loadRecords();
    }
  };

  if (isLocked) {
    return (
      <div className="max-w-md mx-auto my-12 bg-white rounded-2xl p-6 border border-[#e4e7e3] calm-shadow text-center space-y-5 animate-fade-in">
        <Lock className="w-12 h-12 text-[#d89657] mx-auto" />
        <div className="space-y-1">
          <h1 className="text-base font-bold text-[#1e291b]">E2EE CBT 보관함 잠김</h1>
          <p className="text-xs text-gray-500 leading-relaxed">
            인지행동치료(CBT) 기록지가 기기 수준에서 강력하게 종단간 암호화(E2EE) 처리되어 있습니다. 기록을 조회하거나 새로 작성하려면 설정하신 마스터 비밀번호를 입력해 잠금을 해제해 주세요.
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
      
      {/* 타이틀 및 행동 버튼 */}
      <div className="flex justify-between items-center">
        <div className="space-y-0.5">
          <h1 className="text-2xl font-bold text-[#1e291b] tracking-tight">CBT 사고 기록지</h1>
          <p className="text-xs text-gray-500">생각의 왜곡을 살피고 객관적인 시선으로 균형 찾기</p>
        </div>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="px-3 py-2 bg-[#4a6c4c] hover:bg-[#3b573d] text-white text-xs font-semibold rounded-xl flex items-center gap-1 calm-shadow transition-colors"
          >
            <Plus className="w-4 h-4" /> 기록하기
          </button>
        )}
      </div>

      {showForm ? (
        /* CBT 단계별 위자드 폼 */
        <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-6 animate-fade-in">
          
          {/* 폼 헤더 */}
          <div className="flex justify-between items-center border-b border-gray-100 pb-3">
            <h2 className="text-sm font-bold text-[#4a6c4c] flex items-center gap-1.5">
              <BookOpen className="w-4 h-4" /> CBT 기록 작성 ({currentStep + 1} / 6 단계)
            </h2>
            <button 
              onClick={() => { setShowForm(false); setCurrentStep(0); }}
              className="text-xs text-gray-400 hover:text-gray-600 font-medium"
            >
              취소
            </button>
          </div>

          {/* 소크라테스식 질문 안내 */}
          {currentStep === 3 && (
            <div className="p-3 bg-amber-50 border border-amber-100 rounded-xl text-xs text-[#805b36] flex gap-2">
              <HelpCircle className="w-4 h-4 shrink-0 text-[#d89657] mt-0.5" />
              <div>
                <strong>소크라테스 질문법:</strong> 이 생각이 객관적 실체인지 자문해 봅니다.
                <p className="mt-0.5 text-gray-500">"내가 지금 일어난 일을 과도하게 추측하여 결론짓고 있지는 않나요?"</p>
              </div>
            </div>
          )}
          {currentStep === 4 && (
            <div className="p-3 bg-amber-50 border border-amber-100 rounded-xl text-xs text-[#805b36] flex gap-2">
              <HelpCircle className="w-4 h-4 shrink-0 text-[#d89657] mt-0.5" />
              <div>
                <strong>소크라테스 질문법:</strong> 반대되는 관점을 떠올려 봅니다.
                <p className="mt-0.5 text-gray-500">"가장 친한 친구가 나와 똑같은 상황에 처해 있다면, 내가 그 친구에게 어떤 현실적인 말을 건넬까요?"</p>
              </div>
            </div>
          )}

          {/* 입력 컴포넌트 */}
          <div className="space-y-3">
            {currentStep === 0 && (
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-[#1e291b]">{cbtPrompts[0].question}</label>
                <textarea
                  value={situation}
                  onChange={(e) => setSituation(e.target.value)}
                  placeholder={cbtPrompts[0].description}
                  rows={4}
                  className="w-full text-sm p-3 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c] placeholder-gray-400"
                />
              </div>
            )}

            {currentStep === 1 && (
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-[#1e291b]">{cbtPrompts[1].question}</label>
                <textarea
                  value={automaticThought}
                  onChange={(e) => setAutomaticThought(e.target.value)}
                  placeholder={cbtPrompts[1].description}
                  rows={4}
                  className="w-full text-sm p-3 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c] placeholder-gray-400"
                />
              </div>
            )}

            {currentStep === 2 && (
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-[#1e291b]">{cbtPrompts[2].question}</label>
                <textarea
                  value={emotions}
                  onChange={(e) => setEmotions(e.target.value)}
                  placeholder={cbtPrompts[2].description}
                  rows={4}
                  className="w-full text-sm p-3 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c] placeholder-gray-400"
                />
              </div>
            )}

            {currentStep === 3 && (
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-[#1e291b]">{cbtPrompts[3].question}</label>
                <textarea
                  value={evidenceFor}
                  onChange={(e) => setEvidenceFor(e.target.value)}
                  placeholder={cbtPrompts[3].description}
                  rows={4}
                  className="w-full text-sm p-3 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c] placeholder-gray-400"
                />
              </div>
            )}

            {currentStep === 4 && (
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-[#1e291b]">{cbtPrompts[4].question}</label>
                <textarea
                  value={evidenceAgainst}
                  onChange={(e) => setEvidenceAgainst(e.target.value)}
                  placeholder={cbtPrompts[4].description}
                  rows={4}
                  className="w-full text-sm p-3 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c] placeholder-gray-400"
                />
              </div>
            )}

            {currentStep === 5 && (
              <div className="space-y-5">
                <div className="space-y-2">
                  <label className="block text-sm font-semibold text-[#1e291b]">{cbtPrompts[5].question}</label>
                  <textarea
                    value={alternativeThought}
                    onChange={(e) => setAlternativeThought(e.target.value)}
                    placeholder={cbtPrompts[5].description}
                    rows={3}
                    className="w-full text-sm p-3 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c] placeholder-gray-400"
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-sm font-semibold text-[#1e291b]">행동 처방: 다음으로 즉시 취할 수 있는 초소형 행동</label>
                  <textarea
                    value={nextAction}
                    onChange={(e) => setNextAction(e.target.value)}
                    placeholder="생각에만 갇히지 않도록, 바로 실천할 수 있는 가벼운 첫걸음을 약속합니다. (예: 부장님 대신 커피 한 잔 내려 마시고 다시 쳐다보기)"
                    rows={2}
                    className="w-full text-sm p-3 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c] placeholder-gray-400"
                  />
                </div>
              </div>
            )}
          </div>

          {/* 에러 */}
          {errorMsg && (
            <p className="text-xs text-red-500 font-semibold">{errorMsg}</p>
          )}

          {/* 하단 제어 버튼 */}
          <div className="flex justify-between items-center pt-2">
            <button
              onClick={handlePrev}
              disabled={currentStep === 0}
              className="px-3.5 py-2 bg-gray-50 border border-[#e4e7e3] hover:bg-[#eaf2eb]/20 text-gray-500 rounded-xl flex items-center text-xs font-semibold disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4 mr-1" /> 이전
            </button>

            {currentStep < 5 ? (
              <button
                onClick={handleNext}
                className="px-3.5 py-2 bg-[#4a6c4c] hover:bg-[#3b573d] text-white rounded-xl flex items-center text-xs font-semibold"
              >
                다음 <ChevronRight className="w-4 h-4 ml-1" />
              </button>
            ) : (
              <button
                onClick={handleSave}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl flex items-center text-xs font-semibold"
              >
                <CheckCircle className="w-4 h-4 mr-1" /> 저장 및 완료
              </button>
            )}
          </div>

        </div>
      ) : (
        /* 과거 기록 리스트 */
        <div className="space-y-3">
          {records.length === 0 ? (
            <div className="bg-white rounded-2xl p-8 border border-[#e4e7e3] text-center text-xs text-gray-400 space-y-2">
              <p>아직 저장된 인지적 사고 기록지가 없습니다.</p>
              <p>상단의 '기록하기' 버튼을 눌러 평온한 시선을 회복해 보세요.</p>
            </div>
          ) : (
            records.map((r) => {
              return (
                <div key={r.id} className="bg-white rounded-2xl p-4 border border-[#e4e7e3] calm-shadow space-y-3">
                  <div className="flex justify-between items-start border-b border-gray-50 pb-2">
                    <span className="text-[10px] text-gray-400 font-semibold">
                      {new Date(r.timestamp).toLocaleDateString("ko-KR", {
                        year: "numeric",
                        month: "long",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit"
                      })}
                    </span>
                    <button 
                      onClick={() => handleDelete(r.id)}
                      className="text-gray-400 hover:text-red-500 p-1 rounded-full transition-colors"
                      title="삭제"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  
                  {/* 디테일 내용들 */}
                  <div className="space-y-2 text-xs">
                    <div>
                      <span className="font-semibold text-gray-400">당시 상황:</span>
                      <p className="text-gray-700 mt-0.5">{r.situation}</p>
                    </div>
                    <div className="bg-red-50/40 p-2.5 rounded-lg border border-red-100/30">
                      <span className="font-semibold text-red-800">자동적 부정 사고:</span>
                      <p className="text-red-900 mt-0.5">{r.automaticThought}</p>
                    </div>
                    <div className="bg-emerald-50/40 p-2.5 rounded-lg border border-emerald-100/30">
                      <span className="font-semibold text-emerald-800">대안적 균형 사고:</span>
                      <p className="text-emerald-900 mt-0.5">{r.alternativeThought}</p>
                    </div>
                    <div className="bg-blue-50/30 p-2.5 rounded-lg border border-blue-100/30">
                      <span className="font-semibold text-blue-800">실천할 초소형 행동:</span>
                      <p className="text-blue-900 mt-0.5">{r.nextAction}</p>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

    </div>
  );
}
