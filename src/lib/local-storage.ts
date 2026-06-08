import { classifyCrisisText } from "./safety-classifier";

// 로컬 스토리지에 사용될 테이블 키 목록
const KEYS = {
  PROFILES: "mindcare_profiles",
  CONSENTS: "mindcare_consents",
  MOOD_ENTRIES: "mindcare_mood_entries",
  THOUGHT_RECORDS: "mindcare_thought_records",
  ACTIVATION_TASKS: "mindcare_activation_tasks",
  MINDFULNESS_SESSIONS: "mindcare_mindfulness_sessions",
  JOURNAL_ENTRIES: "mindcare_journal_entries",
  SCREENING_RESULTS: "mindcare_screening_results",
  SAFETY_EVENTS: "mindcare_safety_events",
  AUDIT_LOGS: "mindcare_audit_logs"
};

// 안전한 JSON Parse 헬퍼
function getLocalItem<T>(key: string, defaultValue: T): T {
  if (typeof window === "undefined") return defaultValue;
  try {
    const data = localStorage.getItem(key);
    return data ? JSON.parse(data) : defaultValue;
  } catch (e) {
    console.error(`Error parsing localStorage key ${key}`, e);
    return defaultValue;
  }
}

function setLocalItem<T>(key: string, value: T): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch (e) {
    console.error(`Error saving to localStorage key ${key}`, e);
  }
}

// ----------------------------------------------------
// Interfaces & APIs
// ----------------------------------------------------

export interface UserConsent {
  id: string;
  agreedAge19: boolean;
  agreedTerms: boolean;
  agreedPrivacy: boolean;
  agreedSensitiveData: boolean;
  timestamp: string;
}

export interface MoodEntry {
  id: string;
  mood: number;       // 1-10
  stress: number;     // 1-10
  sleep: number;      // 1-10
  energy: number;     // 1-10
  emotions: string[];  // 감정 태그 목록
  note: string;       // 한 줄 메모 (위기 감지 대상)
  timestamp: string;
}

export interface ThoughtRecord {
  id: string;
  situation: string;
  automaticThought: string;
  emotions: string;
  evidenceFor: string;
  evidenceAgainst: string;
  alternativeThought: string;
  nextAction: string;
  timestamp: string;
}

export interface ActivationSession {
  id: string;
  taskId: string;
  taskTitle: string;
  moodBefore: number;
  moodAfter: number;
  completed: boolean;
  timestamp: string;
}

export interface MindfulnessSession {
  id: string;
  exerciseId: string;
  exerciseTitle: string;
  durationMinutes: number;
  timestamp: string;
}

export interface JournalEntry {
  id: string;
  promptId: string;
  promptText: string;
  answers: { [key: string]: string }; // 프롬프트 답변
  timestamp: string;
}

export interface ScreeningResult {
  id: string;
  type: "PHQ-9" | "GAD-7";
  answers: number[];
  totalScore: number;
  timestamp: string;
}

export interface SafetyEvent {
  id: string;
  triggerType: "KEYWORD" | "PHQ9_ITEM9";
  timestamp: string;
}

// ----------------------------------------------------
// Storage Operations
// ----------------------------------------------------

export const localDB = {
  // 1. Consents
  getConsent: (): UserConsent | null => {
    return getLocalItem<UserConsent | null>(KEYS.CONSENTS, null);
  },
  saveConsent: (consent: Omit<UserConsent, "id" | "timestamp">): UserConsent => {
    const newConsent: UserConsent = {
      ...consent,
      id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 9),
      timestamp: new Date().toISOString()
    };
    setLocalItem(KEYS.CONSENTS, newConsent);
    localDB.logAudit("CONSENT_GIVEN", `User gave consents for data processing.`);
    return newConsent;
  },

  // 2. Mood Entries
  getMoodEntries: (): MoodEntry[] => {
    return getLocalItem<MoodEntry[]>(KEYS.MOOD_ENTRIES, []);
  },
  saveMoodEntry: (entry: Omit<MoodEntry, "id" | "timestamp">): { entry: MoodEntry; crisisTriggered: boolean } => {
    const crisisTriggered = classifyCrisisText(entry.note);
    
    if (crisisTriggered) {
      localDB.saveSafetyEvent("KEYWORD");
    }

    const newEntry: MoodEntry = {
      ...entry,
      id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 9),
      timestamp: new Date().toISOString()
    };
    
    const entries = localDB.getMoodEntries();
    setLocalItem(KEYS.MOOD_ENTRIES, [newEntry, ...entries]);
    localDB.logAudit("MOOD_CREATED", `Saved a mood entry with score: ${entry.mood}`);
    
    return { entry: newEntry, crisisTriggered };
  },

  // 3. Thought Records
  getThoughtRecords: (): ThoughtRecord[] => {
    return getLocalItem<ThoughtRecord[]>(KEYS.THOUGHT_RECORDS, []);
  },
  saveThoughtRecord: (record: Omit<ThoughtRecord, "id" | "timestamp">): { record: ThoughtRecord; crisisTriggered: boolean } => {
    const fullText = `${record.situation} ${record.automaticThought} ${record.evidenceFor} ${record.evidenceAgainst} ${record.alternativeThought}`;
    const crisisTriggered = classifyCrisisText(fullText);

    if (crisisTriggered) {
      localDB.saveSafetyEvent("KEYWORD");
    }

    const newRecord: ThoughtRecord = {
      ...record,
      id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 9),
      timestamp: new Date().toISOString()
    };
    const records = localDB.getThoughtRecords();
    setLocalItem(KEYS.THOUGHT_RECORDS, [newRecord, ...records]);
    localDB.logAudit("CBT_CREATED", `Saved a new CBT thought record.`);

    return { record: newRecord, crisisTriggered };
  },
  deleteThoughtRecord: (id: string) => {
    const records = localDB.getThoughtRecords();
    const filtered = records.filter(r => r.id !== id);
    setLocalItem(KEYS.THOUGHT_RECORDS, filtered);
    localDB.logAudit("CBT_DELETED", `Deleted thought record id: ${id}`);
  },

  // 4. Behavioral Activation Tasks
  getActivationSessions: (): ActivationSession[] => {
    return getLocalItem<ActivationSession[]>(KEYS.ACTIVATION_TASKS, []);
  },
  saveActivationSession: (session: Omit<ActivationSession, "id" | "timestamp">): ActivationSession => {
    const newSession: ActivationSession = {
      ...session,
      id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 9),
      timestamp: new Date().toISOString()
    };
    const sessions = localDB.getActivationSessions();
    setLocalItem(KEYS.ACTIVATION_TASKS, [newSession, ...sessions]);
    localDB.logAudit("ACTIVATION_CREATED", `Completed task: ${session.taskTitle}`);
    return newSession;
  },

  // 5. Mindfulness Sessions
  getMindfulnessSessions: (): MindfulnessSession[] => {
    return getLocalItem<MindfulnessSession[]>(KEYS.MINDFULNESS_SESSIONS, []);
  },
  saveMindfulnessSession: (session: Omit<MindfulnessSession, "id" | "timestamp">): MindfulnessSession => {
    const newSession: MindfulnessSession = {
      ...session,
      id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 9),
      timestamp: new Date().toISOString()
    };
    const sessions = localDB.getMindfulnessSessions();
    setLocalItem(KEYS.MINDFULNESS_SESSIONS, [newSession, ...sessions]);
    localDB.logAudit("MINDFULNESS_CREATED", `Completed mindfulness session: ${session.exerciseTitle}`);
    return newSession;
  },

  // 6. Journal Entries
  getJournalEntries: (): JournalEntry[] => {
    return getLocalItem<JournalEntry[]>(KEYS.JOURNAL_ENTRIES, []);
  },
  saveJournalEntry: (entry: Omit<JournalEntry, "id" | "timestamp">): { entry: JournalEntry; crisisTriggered: boolean } => {
    const combinedAnswers = Object.values(entry.answers).join(" ");
    const crisisTriggered = classifyCrisisText(combinedAnswers);

    if (crisisTriggered) {
      localDB.saveSafetyEvent("KEYWORD");
    }

    const newEntry: JournalEntry = {
      ...entry,
      id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 9),
      timestamp: new Date().toISOString()
    };
    const entries = localDB.getJournalEntries();
    setLocalItem(KEYS.JOURNAL_ENTRIES, [newEntry, ...entries]);
    localDB.logAudit("JOURNAL_CREATED", `Saved a reflective journal entry.`);

    return { entry: newEntry, crisisTriggered };
  },

  // 7. Screening Results
  getScreeningResults: (): ScreeningResult[] => {
    return getLocalItem<ScreeningResult[]>(KEYS.SCREENING_RESULTS, []);
  },
  saveScreeningResult: (result: Omit<ScreeningResult, "id" | "timestamp">): { result: ScreeningResult; crisisTriggered: boolean } => {
    let crisisTriggered = false;
    
    // PHQ-9 9번 문항 가동 검증 (0-indexed 라면 index 8이 9번 문항)
    if (result.type === "PHQ-9" && result.answers[8] > 0) {
      crisisTriggered = true;
      localDB.saveSafetyEvent("PHQ9_ITEM9");
    }

    const newResult: ScreeningResult = {
      ...result,
      id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 9),
      timestamp: new Date().toISOString()
    };
    
    // 동의하지 않으면 저장하지 않음 (단, 위기 트리거는 판정함)
    const consents = localDB.getConsent();
    if (consents && consents.agreedSensitiveData) {
      const results = localDB.getScreeningResults();
      setLocalItem(KEYS.SCREENING_RESULTS, [newResult, ...results]);
      localDB.logAudit("SCREENING_CREATED", `Saved ${result.type} results with score: ${result.totalScore}`);
    }

    return { result: newResult, crisisTriggered };
  },

  // 8. Safety Events (최소 로깅 원칙)
  getSafetyEvents: (): SafetyEvent[] => {
    return getLocalItem<SafetyEvent[]>(KEYS.SAFETY_EVENTS, []);
  },
  saveSafetyEvent: (triggerType: "KEYWORD" | "PHQ9_ITEM9"): SafetyEvent => {
    const newEvent: SafetyEvent = {
      id: crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 9),
      triggerType,
      timestamp: new Date().toISOString()
    };
    const events = localDB.getSafetyEvents();
    setLocalItem(KEYS.SAFETY_EVENTS, [newEvent, ...events]);
    localDB.logAudit("SAFETY_CRISIS_TRIGGERED", `Crisis workflow activated due to: ${triggerType}`);
    return newEvent;
  },

  // 9. Audit Logs (개인정보 처리 이력)
  getAuditLogs: (): { action: string; message: string; timestamp: string }[] => {
    return getLocalItem<any[]>(KEYS.AUDIT_LOGS, []);
  },
  logAudit: (action: string, message: string) => {
    if (typeof window === "undefined") return;
    const log = {
      action,
      message,
      timestamp: new Date().toISOString()
    };
    const logs = localDB.getAuditLogs();
    setLocalItem(KEYS.AUDIT_LOGS, [log, ...logs].slice(0, 100)); // 최대 100개 감사로그 보관
  },

  // 10. Data Portability (Export & Delete)
  exportAllData: (): string => {
    const allData = {
      consent: localDB.getConsent(),
      moodEntries: localDB.getMoodEntries(),
      thoughtRecords: localDB.getThoughtRecords(),
      activationSessions: localDB.getActivationSessions(),
      mindfulnessSessions: localDB.getMindfulnessSessions(),
      journalEntries: localDB.getJournalEntries(),
      screeningResults: localDB.getScreeningResults(),
      safetyEvents: localDB.getSafetyEvents(),
      auditLogs: localDB.getAuditLogs()
    };
    localDB.logAudit("DATA_EXPORTED", "User requested and downloaded all personal data.");
    return JSON.stringify(allData, null, 2);
  },

  deleteAllData: () => {
    if (typeof window === "undefined") return;
    Object.values(KEYS).forEach(key => {
      localStorage.removeItem(key);
    });
    console.log("All personal data permanently deleted.");
  }
};
