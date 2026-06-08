"use client";

import { useEffect, useState } from "react";
import { localDB, UserConsent } from "@/lib/local-storage";
import { ShieldCheck, Download, Trash2, CheckCircle2, RefreshCw, Lock, Unlock, EyeOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { isE2eeEnabled, getSessionPassword, setSessionPassword, clearSessionPassword, encryptText, decryptText } from "@/lib/crypto";

export default function PrivacySettingsPage() {
  const router = useRouter();
  const [consent, setConsent] = useState<UserConsent | null>(null);
  const [deleteConfirmed, setDeleteConfirmed] = useState<boolean>(false);
  const [syncStatus, setSyncStatus] = useState<string>("로컬 저장소 전용 (로그인 없음)");

  // E2EE 암호화 관련 상태
  const [e2eeEnabled, setE2eeEnabled] = useState<boolean>(false);
  const [masterPassword, setMasterPassword] = useState<string>("");
  const [inputPassword, setInputPassword] = useState<string>("");
  const [isUnlocked, setIsUnlocked] = useState<boolean>(false);
  const [e2eeError, setE2eeError] = useState<string>("");

  useEffect(() => {
    loadConsent();
    const enabled = isE2eeEnabled();
    setE2eeEnabled(enabled);
    if (enabled) {
      const pw = getSessionPassword();
      setIsUnlocked(!!pw);
    }
  }, []);

  const handleEnableE2ee = async (e: React.FormEvent) => {
    e.preventDefault();
    if (masterPassword.length < 4) {
      setE2eeError("마스터 비밀번호는 최소 4자 이상이어야 합니다.");
      return;
    }
    try {
      const testEnc = await encryptText("session_test", masterPassword);
      localStorage.setItem("mindcare_e2ee_enabled", "true");
      localStorage.setItem("mindcare_e2ee_test", testEnc);
      setSessionPassword(masterPassword);
      setE2eeEnabled(true);
      setIsUnlocked(true);
      setMasterPassword("");
      setE2eeError("");
      alert("종단간 암호화(E2EE)가 성공적으로 활성화되었습니다! 이제 성찰 일지와 CBT 사고 기록지가 마스터 비밀번호로 암호화되어 보관됩니다.");
    } catch (err) {
      console.error(err);
      setE2eeError("암호화 활성화 처리 중 에러가 발생했습니다.");
    }
  };

  const handleUnlockE2ee = async (e: React.FormEvent) => {
    e.preventDefault();
    const testEnc = localStorage.getItem("mindcare_e2ee_test") || "";
    if (!testEnc) {
      setE2eeError("암호화 테스트 데이터가 누락되었습니다. E2EE를 재설정해 주세요.");
      return;
    }
    const dec = await decryptText(testEnc, inputPassword);
    if (dec === "session_test") {
      setSessionPassword(inputPassword);
      setIsUnlocked(true);
      setInputPassword("");
      setE2eeError("");
      alert("종단간 암호화 잠금이 해제되었습니다.");
    } else {
      setE2eeError("잘못된 비밀번호입니다. 다시 입력해 주세요.");
    }
  };

  const handleDisableE2ee = () => {
    if (confirm("🚨 경고: E2EE를 비활성화하면 앞으로 작성할 데이터는 평문으로 저장되지만, 이미 암호화된 기존 데이터들은 복호화할 마스터 비밀번호가 유실될 경우 영구히 읽을 수 없게 됩니다. 비활성화하시겠습니까?")) {
      localStorage.removeItem("mindcare_e2ee_enabled");
      localStorage.removeItem("mindcare_e2ee_test");
      clearSessionPassword();
      setE2eeEnabled(false);
      setIsUnlocked(false);
      alert("종단간 암호화(E2EE)가 비활성화되었습니다.");
    }
  };

  const loadConsent = () => {
    if (typeof window !== "undefined") {
      const saved = localDB.getConsent();
      setConsent(saved);
    }
  };

  const handleExportJSON = () => {
    const dataStr = localDB.exportAllData();
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `mindcare_routine_data_${new Date().toISOString().slice(0, 10)}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const handleExportCSV = () => {
    // 기분 체크인 이력을 CSV로 변환
    const moodEntries = localDB.getMoodEntries();
    
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "날짜,기분점수(1-10),스트레스점수(1-10),수면질(1-10),활력점수(1-10),감정태그,메모\n";
    
    moodEntries.forEach(e => {
      const date = new Date(e.timestamp).toLocaleDateString();
      const emotions = e.emotions.join(";");
      const noteClean = e.note.replace(/,/g, " "); // 쉼표 이스케이프
      csvContent += `${date},${e.mood},${e.stress},${e.sleep},${e.energy},"${emotions}","${noteClean}"\n`;
    });

    const encodedUri = encodeURI(csvContent);
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', encodedUri);
    linkElement.setAttribute('download', `mindcare_routine_moods_${new Date().toISOString().slice(0,10)}.csv`);
    linkElement.click();
    localDB.logAudit("DATA_EXPORTED", "User downloaded mood logs as CSV.");
  };

  const handleDeleteAll = () => {
    if (!deleteConfirmed) return;
    
    if (confirm("🚨 경고: 이 작업은 되돌릴 수 없습니다. 로컬 브라우저와 데이터베이스 상의 기분 점수, 성찰 일지, CBT 기록 등을 포함한 본인에 관련된 모든 데이터를 '영구 소멸'시킵니다. 정말로 진행하시겠습니까?")) {
      localDB.deleteAllData();
      alert("모든 데이터가 영구 삭제되었습니다. 랜딩 페이지로 이동합니다.");
      router.push("/");
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="space-y-0.5">
        <h1 className="text-2xl font-bold text-[#1e291b] tracking-tight">개인정보 및 설정</h1>
        <p className="text-xs text-gray-500">본 서비스는 개인정보보호법에 의거하여 사용자의 데이터 주권을 전적으로 존중합니다.</p>
      </div>

      {/* 1. 개인정보 수집 및 보관 상태 */}
      <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-4">
        <h2 className="text-sm font-bold text-[#4a6c4c] border-b border-gray-50 pb-2">
          데이터 저장 방식 및 상태
        </h2>
        
        <div className="space-y-3 text-xs">
          <div className="flex justify-between items-center bg-[#f8faf7] p-3 rounded-xl border border-gray-100">
            <span className="font-semibold text-gray-500">현재 보관 모드</span>
            <span className="text-[#4a6c4c] font-bold">{syncStatus}</span>
          </div>

          <p className="text-gray-500 leading-relaxed">
            * 회원가입을 수행하지 않으신 상태이므로, 모든 마음점수와 일지 텍스트는 브라우저의 내부 격리소(LocalStorage)에만 안전하게 남습니다. 저희 서버로 사용자의 기분 텍스트가 전송되지 않아 안심하실 수 있습니다.
          </p>
        </div>
      </div>

      {/* 2. 동의 이력 정보 */}
      <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-3">
        <h2 className="text-sm font-bold text-[#4a6c4c] border-b border-gray-50 pb-2">
          나의 동의 이력 현황
        </h2>
        
        {consent ? (
          <div className="space-y-2 text-xs">
            <div className="flex items-center gap-2 text-emerald-700">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>만 19세 이상 성인 동의 완료</span>
            </div>
            <div className="flex items-center gap-2 text-emerald-700">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>서비스 이용약관 동의 완료</span>
            </div>
            <div className="flex items-center gap-2 text-emerald-700">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>개인정보 수집 및 처리 방침 동의 완료</span>
            </div>
            <div className="flex items-center gap-2 text-emerald-700 bg-emerald-50 p-2 rounded-lg border border-emerald-100/50">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>정신건강 민감 정보 처리 동의 완료</span>
            </div>
            <p className="text-[10px] text-gray-400 mt-1">
              동의 처리 시간: {new Date(consent.timestamp).toLocaleString("ko-KR")}
            </p>
          </div>
        ) : (
          <p className="text-xs text-gray-400">동의 이력이 저장되지 않았습니다.</p>
        )}
      </div>

      {/* Zero-Knowledge E2EE Settings */}
      <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-4">
        <h2 className="text-sm font-bold text-[#4a6c4c] border-b border-gray-50 pb-2 flex items-center gap-1.5">
          <ShieldCheck className="w-4.5 h-4.5 text-emerald-600" /> Zero-Knowledge 종단간 암호화 (E2EE)
        </h2>
        <p className="text-[11px] text-gray-500 leading-relaxed">
          마스터 비밀번호를 설정하면 브라우저 내에서 사용자의 모든 성찰 일지 및 CBT 기록지 텍스트가 암호화(AES-GCM-256)되어 기기에 쓰입니다. 저희 서버나 데이터베이스 관리자도 이를 해독할 수 없으며 본인 기기에서만 복호화할 수 있습니다.
        </p>

        {!e2eeEnabled ? (
          <form onSubmit={handleEnableE2ee} className="space-y-3 pt-1">
            <div className="space-y-1">
              <label className="block text-[10px] font-bold text-gray-500">신규 마스터 비밀번호 설정</label>
              <input 
                type="password"
                value={masterPassword}
                onChange={(e) => setMasterPassword(e.target.value)}
                placeholder="4자 이상의 마스터 비밀번호 입력"
                className="w-full text-xs p-2.5 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c]"
              />
            </div>
            {e2eeError && <p className="text-[10px] text-red-500 font-semibold">{e2eeError}</p>}
            <button
              type="submit"
              className="w-full py-2.5 bg-[#4a6c4c] hover:bg-[#3b573d] text-white font-bold rounded-xl text-xs transition-colors flex items-center justify-center gap-1.5"
            >
              <Lock className="w-3.5 h-3.5" />
              종단간 암호화(E2EE) 활성화
            </button>
          </form>
        ) : (
          <div className="space-y-3 pt-1">
            <div className="flex justify-between items-center bg-[#f8faf7] p-3 rounded-xl border border-gray-100 text-xs">
              <span className="font-semibold text-gray-500">보안 상태</span>
              {isUnlocked ? (
                <span className="text-emerald-700 font-bold flex items-center gap-1">
                  <Unlock className="w-3.5 h-3.5 text-emerald-600" /> 잠금 해제됨 (조회 및 저장 가능)
                </span>
              ) : (
                <span className="text-red-600 font-bold flex items-center gap-1">
                  <Lock className="w-3.5 h-3.5 text-red-500" /> 암호 잠김 (조회 차단됨)
                </span>
              )}
            </div>

            {!isUnlocked ? (
              <form onSubmit={handleUnlockE2ee} className="space-y-3">
                <div className="space-y-1">
                  <label className="block text-[10px] font-bold text-gray-500">E2EE 잠금 해제 암호</label>
                  <input 
                    type="password"
                    value={inputPassword}
                    onChange={(e) => setInputPassword(e.target.value)}
                    placeholder="비밀번호 입력"
                    className="w-full text-xs p-2.5 bg-[#f8faf7] border border-[#e4e7e3] rounded-xl focus:outline-none focus:ring-1 focus:ring-[#4a6c4c]"
                  />
                </div>
                {e2eeError && <p className="text-[10px] text-red-500 font-semibold">{e2eeError}</p>}
                <button
                  type="submit"
                  className="w-full py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl text-xs transition-colors flex items-center justify-center gap-1.5"
                >
                  <Unlock className="w-3.5 h-3.5" />
                  E2EE 잠금 해제
                </button>
              </form>
            ) : (
              <button
                onClick={handleDisableE2ee}
                className="w-full py-2.5 bg-white border border-red-200 hover:bg-red-50 text-red-600 font-bold rounded-xl text-xs transition-colors flex items-center justify-center gap-1.5"
              >
                <EyeOff className="w-3.5 h-3.5" />
                종단간 암호화(E2EE) 비활성화
              </button>
            )}
          </div>
        )}
      </div>

      {/* 3. 데이터 휴대성 (Export) */}
      <div className="bg-white rounded-2xl p-5 border border-[#e4e7e3] calm-shadow space-y-3">
        <h2 className="text-sm font-bold text-[#4a6c4c] border-b border-gray-50 pb-2">
          전체 개인 데이터 백업 및 내보내기
        </h2>
        <p className="text-xs text-gray-500 leading-relaxed">
          언제든지 본인의 마음 점수, CBT 기록, 일기 텍스트를 파일로 다운로드하여 소장하실 수 있습니다.
        </p>
        
        <div className="grid grid-cols-2 gap-2 pt-1.5">
          <button
            onClick={handleExportJSON}
            className="flex items-center justify-center gap-1.5 p-3 bg-white border border-[#e4e7e3] hover:bg-[#eaf2eb]/30 rounded-xl text-xs font-semibold text-gray-700 transition-all"
          >
            <Download className="w-4 h-4 text-[#4a6c4c]" />
            JSON 파일 저장
          </button>
          <button
            onClick={handleExportCSV}
            className="flex items-center justify-center gap-1.5 p-3 bg-white border border-[#e4e7e3] hover:bg-[#eaf2eb]/30 rounded-xl text-xs font-semibold text-gray-700 transition-all"
          >
            <Download className="w-4 h-4 text-[#4a6c4c]" />
            CSV (기분 점수)
          </button>
        </div>
      </div>

      {/* 4. 계정 탈퇴 및 완전 삭제 */}
      <div className="bg-red-50/50 rounded-2xl p-5 border border-red-100 calm-shadow space-y-4">
        <h2 className="text-sm font-bold text-red-800 border-b border-red-200/50 pb-2">
          회원 탈퇴 및 데이터 영구 파기
        </h2>
        <p className="text-xs text-red-900/80 leading-relaxed">
          이 작업은 로컬 장치 및 데이터베이스 상에 있는 회원님의 모든 감정 기록, 생각 기록지, 일기 텍스트를 **즉각적이고 복구 불가능하게 디스크에서 물리적 소멸**시킵니다.
        </p>

        <label className="flex items-start gap-2.5 cursor-pointer">
          <input 
            type="checkbox" 
            checked={deleteConfirmed}
            onChange={(e) => setDeleteConfirmed(e.target.checked)}
            className="w-4 h-4 rounded text-red-600 border-red-300 focus:ring-red-600 mt-0.5"
          />
          <span className="text-[11px] text-red-900 font-semibold leading-normal">
            위 경고문을 숙지했으며, 내 데이터를 즉각적이고 영구히 복구 불가능하게 삭제할 것에 확실히 동의합니다.
          </span>
        </label>

        <button
          onClick={handleDeleteAll}
          disabled={!deleteConfirmed}
          className="w-full py-3 bg-red-600 hover:bg-red-700 disabled:bg-red-100 disabled:text-red-300 text-white font-bold rounded-xl text-xs transition-colors flex items-center justify-center gap-1.5"
        >
          <Trash2 className="w-4 h-4" />
          모든 데이터 즉각 완전 영구 파기
        </button>
      </div>

    </div>
  );
}
