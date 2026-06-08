import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

export const isSupabaseConfigured = (): boolean => {
  return (
    supabaseUrl !== "" &&
    supabaseUrl !== "https://placeholder-project.supabase.co" &&
    supabaseAnonKey !== "" &&
    supabaseAnonKey !== "placeholder-key"
  );
};

// Supabase 클라이언트를 안전하게 초기화합니다.
// 환경변수가 없을 경우 빌드 중 에러 방지 및 로컬 우선 모드 작동용 플레이스홀더 설정.
export const supabase = createClient(
  supabaseUrl || "https://placeholder-project.supabase.co",
  supabaseAnonKey || "placeholder-key"
);
