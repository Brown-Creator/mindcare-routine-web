import { supabase, isSupabaseConfigured } from "./supabase";
import { localDB } from "./local-storage";

export async function syncLocalDataToSupabase() {
  if (!isSupabaseConfigured()) {
    console.log("Supabase is not configured. Skipping auto sync.");
    return;
  }

  try {
    console.log("Online detected: Starting automatic background sync with Supabase...");

    // 1. Mood Entries 동기화
    const moods = localDB.getMoodEntries();
    if (moods.length > 0) {
      const { error } = await supabase
        .from("mood_entries")
        .upsert(moods.map(m => ({
          id: m.id,
          mood: m.mood,
          stress: m.stress,
          sleep: m.sleep,
          energy: m.energy,
          emotions: m.emotions,
          note: m.note,
          created_at: m.timestamp
        })));
      if (error) console.error("Sync mood entries error:", error);
    }

    // 2. CBT Thought Records 동기화
    const cbts = localDB.getThoughtRecords();
    if (cbts.length > 0) {
      const { error } = await supabase
        .from("thought_records")
        .upsert(cbts.map(c => ({
          id: c.id,
          situation: c.situation,
          automatic_thought: c.automaticThought,
          emotions: c.emotions,
          evidence_for: c.evidenceFor,
          evidence_against: c.evidenceAgainst,
          alternative_thought: c.alternativeThought,
          next_action: c.nextAction,
          created_at: c.timestamp
        })));
      if (error) console.error("Sync thought records error:", error);
    }

    // 3. Reflective Journal Entries 동기화
    const journals = localDB.getJournalEntries();
    if (journals.length > 0) {
      const { error } = await supabase
        .from("journal_entries")
        .upsert(journals.map(j => ({
          id: j.id,
          prompt_id: j.promptId,
          prompt_text: j.promptText,
          answers: j.answers,
          created_at: j.timestamp
        })));
      if (error) console.error("Sync journal entries error:", error);
    }

    // 4. Mindfulness Sessions 동기화
    const mindfulness = localDB.getMindfulnessSessions();
    if (mindfulness.length > 0) {
      const { error } = await supabase
        .from("mindfulness_sessions")
        .upsert(mindfulness.map(m => ({
          id: m.id,
          exercise_id: m.exerciseId,
          exercise_title: m.exerciseTitle,
          duration_minutes: m.durationMinutes,
          created_at: m.timestamp
        })));
      if (error) console.error("Sync mindfulness sessions error:", error);
    }

    // 5. Activation Sessions 동기화
    const activations = localDB.getActivationSessions();
    if (activations.length > 0) {
      const { error } = await supabase
        .from("activation_sessions")
        .upsert(activations.map(a => ({
          id: a.id,
          task_id: a.taskId,
          task_title: a.taskTitle,
          mood_before: a.moodBefore,
          mood_after: a.moodAfter,
          completed: a.completed,
          created_at: a.timestamp
        })));
      if (error) console.error("Sync activation sessions error:", error);
    }

    localDB.logAudit("DATA_SYNCED", "Successfully auto-synced offline data to Supabase database.");
    console.log("Automatic background sync complete.");
  } catch (err) {
    console.error("Auto sync failed:", err);
  }
}

export function initAutoSync() {
  if (typeof window === "undefined") return;

  // 온라인 상태 전환 이벤트 리스너 바인딩
  window.addEventListener("online", syncLocalDataToSupabase);

  // 현재 이미 온라인 상태라면 백그라운드 즉시 동기화 시도
  if (navigator.onLine) {
    syncLocalDataToSupabase();
  }
}
