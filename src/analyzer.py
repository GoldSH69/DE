import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List

# Pydantic 구조 정의 (Gemini JSON Schema 강제용)
class Scene(BaseModel):
    start_time: str = Field(description="원본 영상에서 잘라낼 시작 지점 (포맷: MM:SS 또는 HH:MM:SS)")
    end_time: str = Field(description="원본 영상에서 잘라낼 종료 지점 (포맷: MM:SS 또는 HH:MM:SS)")
    tts_text: str = Field(description="이 장면에서 Edge-TTS로 합성할 네이티브 일본어 쇼츠 나레이션 텍스트 (단순 명료하고 귀에 꽂히는 예능 톤)")
    caption_ko: str = Field(description="화면에 노출할 맛깔스럽고 자극적인 예능 톤의 한국어(Korean) 화면 자막")
    caption_ja: str = Field(description="이 장면의 대사나 분위기를 현지인 감성으로 살린 일본어(Japanese) 화면 자막")
    caption_en: str = Field(description="글로벌 시청자를 위한 자연스러운 영어(English) 화면 자막")
    caption_zh: str = Field(description="중국어 시청자를 위한 간결한 중국어 간체(Chinese) 화면 자막")

class VideoAnalysisResult(BaseModel):
    selected_scenes: List[Scene] = Field(description="쇼츠(60초 이내)로 사용하기에 가장 자극적이고 재미있는 하이라이트 구간 리스트")
    total_duration_seconds: int = Field(description="선정된 총 구간의 누적 초(sec) 시간 (반드시 60초 미만이어야 함)")
    rationale: str = Field(description="이 구간들을 하이라이트로 선정한 이유와 예능 편집 연출 방향에 대한 간단한 설명")

def analyze_video_transcript(transcript_text, video_title="알 수 없는 동영상"):
    """Gemini API를 사용하여 비디오의 자막을 분석하고 60초 하이라이트 기획안을 생성합니다."""
    print(f"[Analyzer] Analyzing transcript for video: '{video_title}'...")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[Analyzer] WARNING: GEMINI_API_KEY not found in environment. Falling back to Mock Analysis Result.")
        return get_mock_analysis_result()

    try:
        # google-genai 최신 클라이언트 생성
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
당신은 전 세계 인기 예능 콘텐츠를 발굴하고 100만 조회수를 기록할 쇼츠(Shorts)를 기획하는 전문 크리에이터이자 PD입니다.
아래 제공되는 유튜브 롱폼 동영상의 자막 대본(과 타임라인 정보)을 분석하여, **시청자를 단 3초 만에 몰입시킬 수 있는 가장 자극적이고, 반전이 있거나, 웃음이 터지는 60초 미만의 핵심 장면들**을 엄선해 주십시오.

[동영상 제목]
{video_title}

[자막 및 대본 내용]
{transcript_text}

[요구사항 및 가이드라인]
1. **총 누적 재생 시간 제한**: 'selected_scenes'에 기재되는 구간의 총 합이 **반드시 60초 미만**(약 30초~50초 권장)이 되도록 정밀하게 시작(start_time)과 종료(end_time) 타임코드를 지정해 주십시오.
2. **일본어 나레이션 대본 ('tts_text')**: 나중에 일본어 성우 TTS(edge-tts)로 녹음될 문장입니다. 번역기 번역이 아닌, 네이티브 일본인들이 쇼츠나 틱톡에서 쓰는 자극적이고 생동감 넘치는 예능 톤으로 작성해 주십시오. (예: "とんでもない事態が発生しました！", "これは予想外すぎるw")
3. **다국어 화면 자막 구성**:
   - `caption_ko`: 한글 자막으로서 상황을 극대화해 표현하는 맛깔스러운 한국어(Korean) 예능체 자막입니다. (예: "역대급 방송 사고 발생!")
     **특히 첫 번째 장면(Scene 1)의 `caption_ko`는 이 쇼츠 비디오의 표지이자 썸네일 제목 역할(썸네일 후킹)을 하므로, 시청자가 스크롤을 멈추고 무조건 클릭하고 싶게 만드는 강력한 썸네일 카피(호기심 자극, 자극적인 사실 요약, 100만 조회수 헤드라인 등)로 작성하십시오.**
   - `caption_ja`: 일본어 자막으로서 일본 현지인 예능 감성에 맞춘 일본어(Japanese) 자막입니다. (예: "とんでもない事態発生w")
   - `caption_en`: 영어 자막으로서 직관적이고 쉬운 자연스러운 영어(English) 자막입니다. (예: "Epic broadcast fail!")
   - `caption_zh`: 중국어 자막으로서 상황에 부합하는 간결한 중국어 간체(Chinese) 자막입니다. (예: "突发史诗级播事故!")
4. **연속성 및 서사**: 구간을 여러 개 잘라낼 경우, 숏폼으로서 내용의 흐름이나 반전이 매끄럽게 연결되도록 설계하십시오.

반드시 JSON Schema 구조에 응답을 반환하십시오.
"""
        
        # gemini-2.5-flash 모델을 기본으로 구조화된 JSON 요청
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VideoAnalysisResult,
                temperature=0.3
            )
        )
        
        # 결과 파싱
        result_json = json.loads(response.text)
        print("[Analyzer] Gemini Analysis completed successfully.")
        return result_json
        
    except Exception as e:
        print(f"[Analyzer] Error during Gemini Analysis: {e}")
        raise RuntimeError(f"Gemini AI 분석 기획안 생성 실패 (원인: {str(e)})")

def get_mock_analysis_result():
    """Gemini API가 없거나 에러 발생 시 테스트용으로 사용할 Mock 데이터를 반환합니다."""
    return {
        "selected_scenes": [
            {
                "start_time": "00:10",
                "end_time": "00:20",
                "tts_text": "今日の動画はこれです！信じられないハプニングが起きました！",
                "caption_ko": "오늘의 하이라이트! 믿을 수 없는 방송 사고가 터졌습니다!",
                "caption_ja": "今日のハイライト！信じられないハプニング発生！",
                "caption_en": "Today's highlight! An unbelievable accident happened!",
                "caption_zh": "今日亮点！发生了令人难以置信的播事故！"
            },
            {
                "start_time": "00:45",
                "end_time": "00:58",
                "tts_text": "まさかの展開にスタジオ大爆笑。この結末は予想できませんでした。",
                "caption_ko": "설마했던 반전 결말에 스튜디오는 초토화되었습니다.",
                "caption_ja": "まさかの結末にスタジオ大爆笑！",
                "caption_en": "Unexpected ending! The studio broke out in laughter!",
                "caption_zh": "意想不到的结局！录音棚哄堂大笑！"
            }
        ],
        "total_duration_seconds": 23,
        "rationale": "테스트 모드용 모의 데이터입니다. 인트로의 시선을 끄는 사고 장면과 중후반부의 웃음 포인트를 결합하여 23초 분량의 쇼츠를 기획했습니다."
    }

if __name__ == "__main__":
    # 테스트 구동
    sample_transcript = """
    00:01 [음악] 안녕하십니까 오늘은 특별한 일본 예능 클립을 소개하겠습니다.
    00:10 어? 지금 무대 뒤에서 무슨 소리가 들리는데요? 진짜 예상치 못한 일이 벌어집니다!
    00:15 와! 대단합니다! 출연자가 갑자기 넘어졌어요!
    00:22 큰일 날 뻔 했지만 웃음으로 극복합니다.
    00:30 이번 코너는 진지한 토론 코너입니다.
    00:45 그런데 갑자기 패널이 벌떡 일어나며 춤을 추기 시작합니다!
    00:50 이게 무슨 일이죠? 다들 너무 웃겨서 뒤집어집니다!
    00:58 결국 오늘의 우승은 댄스맨에게 돌아갑니다. 감사합니다.
    """
    res = analyze_video_transcript(sample_transcript, "샘플 요절복통 예능쇼")
    print(json.dumps(res, ensure_ascii=False, indent=2))
