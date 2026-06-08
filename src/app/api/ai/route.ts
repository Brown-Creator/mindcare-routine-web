import { NextRequest, NextResponse } from "next/server";
import { classifyCrisisText, redactSensitiveLogs } from "@/lib/safety-classifier";

// 모의 AI 응답 세트 (API 키가 없거나 대체 작동 시)
const MOCK_SUMMARIES = [
  "자신에 대해 다소 비판적인 생각이 일어났으나 객관적으로 바라보려는 노력이 보입니다.",
  "타인의 부정적인 반응에 다소 과민하게 긴장하고 있음을 가만히 수용하고 있습니다.",
  "바쁜 업무 피로로 인해 내면의 활력 에너지가 일시 감소하였음을 성찰하고 있습니다."
];

const MOCK_CBT_QUESTIONS = [
  "혹시 오늘 그 일 외에 다른 긍정적인 상황은 없었나요?",
  "나를 가장 아껴주는 사람이 내 곁에서 이 상황을 본다면 어떤 따뜻한 말을 건네줄까요?",
  "이 일이 일어난 데에 내 지분이 정말 100%인가요? 다른 외부 요인은 어떤 것이 있었을까요?"
];

const MOCK_ACTIVATIONS = [
  "따뜻한 허브차 한 잔을 받아서 향기를 30초 동안 음미하며 마시기",
  "책상의 오래된 메모지 3장 버리기",
  "스마트폰을 내려놓고 창문 밖 구름이나 간판을 30초 동안 쳐다보기"
];

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { journalText, actionType } = body;

    // 로그 마스킹 처리하여 안전하게 출력
    console.log(redactSensitiveLogs(`AI Request received. Action: ${actionType}, Content: ${journalText}`));

    // 1. AI 호출 전(Pre-generation) 위기 감지 검사
    if (classifyCrisisText(journalText)) {
      console.warn("Safety Classifier: Crisis detected in user request. Blocking generation.");
      return NextResponse.json({
        crisisTriggered: true,
        message: "위기 단어가 감지되었습니다. 즉각적인 안전 관리가 중요합니다."
      }, { status: 200 }); // 클라이언트가 위기 흐름을 탈 수 있도록 성공 코드로 넘겨 처리
    }

    let aiResult = "";
    const openAiKey = process.env.OPENAI_API_KEY;

    if (!openAiKey) {
      // API 키가 없으면 준비된 근거 기반 템플릿(Mock)으로 작동 (오작동 방지)
      const mockIndex = Math.floor(Math.random() * 3);
      if (actionType === "SUMMARIZE") {
        aiResult = `• ${MOCK_SUMMARIES[mockIndex]}`;
      } else if (actionType === "CBT_SUGGEST") {
        aiResult = `• ${MOCK_CBT_QUESTIONS[mockIndex]}`;
      } else {
        aiResult = `• 추천 소형 행동: ${MOCK_ACTIVATIONS[mockIndex]}`;
      }
    } else {
      // OpenAI API 호출 연동 (실제 배포시)
      try {
        const response = await fetch("https://api.openai.com/v1/chat/completions", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${openAiKey}`
          },
          body: JSON.stringify({
            model: "gpt-4o-mini",
            messages: [
              {
                role: "system",
                content: `당신은 마음건강 기록 보조자입니다. 다음 규칙을 엄격히 따르십시오:
                1. 의학적 진단, 질병 처방, 치료 선언을 절대로 하지 마십시오.
                2. 트라우마를 해석하거나 병리적 낙인을 찍지 마십시오.
                3. 친절하고 중립적이며 건조한 어조를 유지하십시오.
                4. 저널 내용을 제3자 시선에서 중립적으로 요약하거나, CBT 질문 한 가지를 던지거나, 초소형 행동 활성화 태스크 하나만 제안하십시오.`
              },
              {
                role: "user",
                content: `텍스트: "${journalText}". 행동 유형: ${actionType}`
              }
            ],
            temperature: 0.5,
            max_tokens: 300
          })
        });

        const data = await response.json();
        aiResult = data.choices[0].message.content || "";
      } catch (err) {
        console.error("OpenAI API call failed, falling back to Mock:", err);
        aiResult = "• 저널 감정이 다소 격해졌으나 가만히 수용하고 있습니다. 차분하게 호흡을 지속해 보세요.";
      }
    }

    // 2. AI 생성 후(Post-generation) 안전성 2차 검증
    if (classifyCrisisText(aiResult)) {
      console.warn("Safety Classifier: Crisis detected in AI generated content. Blocking response.");
      return NextResponse.json({
        crisisTriggered: true,
        message: "안전 조력 페이지로 이동합니다."
      }, { status: 200 });
    }

    // 면책 고지 문구를 필수적으로 삽입하여 리턴
    const disclaimer = "\n\n* AI가 생성한 내용은 자기성찰 보조이며 전문적 진단이나 치료가 아닙니다.";

    return NextResponse.json({
      crisisTriggered: false,
      result: aiResult + disclaimer
    });

  } catch (error) {
    console.error("AI API route error:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}
