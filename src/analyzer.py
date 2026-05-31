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
    caption: str = Field(description="사용자가 CapCut에서 한국어 자막으로 얹을 한글 번역/요약 자막 텍스트")

class VideoAnalysisResult(BaseModel):
    selected_scenes: List[Scene] = Field(description="쇼츠(60초 이내)로 사용하기에 가장 자극적이고 재미있는 하이라이트 구간 리스트")
    total_duration_seconds: int = Field(description="선정된 총 구간의 누적 초(sec) 시간 (반드시 60초 미만이어야 함)")
    rationale: str = Field(description="이 구간들을 하이라이트로 선정한 이유와 예능 편집 연출 방향에 대한 간단한 설명")

def analyze_video_transcript(transcript_text, video_title="알 수 없는 동영상"):
    """Gemini API를 사용하여 비디오의 자막을 분석하고 60초 하이라이트 기획안을 생성합니다."""
    print(f"[Analyzer] Analyzing transcript for video: '{video_title}'...")
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다. 대시보드 우측 상단의 톱니바퀴 [연동 키 설정] 버튼을 눌러 Gemini API Key를 입력하고 저장해 주세요. (로컬 구동의 경우 실행하는 터미널 세션에 GEMINI_API_KEY 환경 변수가 제공되어야 합니다.)")

    # 자막 수집 실패 여부 확인
    is_subtitle_failed = transcript_text.startswith("__SUBTITLE_EXTRACTION_FAILED_429__")
    error_reason = transcript_text.split(":", 1)[1] if is_subtitle_failed else ""

    try:
        # google-genai 최신 클라이언트 생성
        client = genai.Client(api_key=api_key)
        
        if is_subtitle_failed:
            print(f"[Analyzer] Subtitles were blocked by YouTube ({error_reason}). Generating planning purely based on Video Title.")
            prompt = f"""
당신은 전 세계 인기 예능 콘텐츠를 발굴하고 100만 조회수를 기록할 쇼츠(Shorts)를 기획하는 전문 크리에이터이자 PD입니다.
현재 유튜브의 로봇 탐지 차단(429 블록 등)으로 인해 동영상의 자막 대본을 수집하지 못했습니다.
따라서, 제공되는 **동영상 제목** 정보만을 바탕으로 시청자를 단 3초 만에 몰입시킬 수 있는 재미있고 자극적인 60초 미만의 쇼츠 기획안을 추정하여 설계해 주십시오.

[동영상 제목]
{video_title}

[요구사항 및 가이드라인]
1. **자막이 없는 상태에서의 구간 제안**: 자막 대본이 없으므로, 영상의 인트로(예: 00:00 ~ 00:15) 및 핵심 웃음 포인트나 반전이 있을 만한 일반적인 중간/후반부 구간(예: 00:40 ~ 00:55)을 2~3개 골라 총합 **60초 미만**이 되도록 타임코드를 지정해 주십시오. (영상 길이를 알 수 없으므로 무난하게 전반부와 중반부의 10~20초대 구간을 지정해 주시면 좋습니다.)
2. **일본어 나레이션 대본 ('tts_text')**: 나중에 일본어 성우 TTS(edge-tts)로 녹음될 문장입니다. 번역기 번역이 아닌, 네이티브 일본인들이 쇼츠나 틱톡에서 쓰는 자극적이고 생동감 넘치는 예능 톤으로 작성해 주십시오. (예: "とんでもない事態が発生しました！", "これは予想外すぎるw")
3. **자막 텍스트 ('caption')**: 나중에 캡컷에서 한글 폰트로 편집할 화면 한글 자막입니다. 상황을 극대화하여 묘사하는 예능 자막 풍으로 간결하게 작성해 주십시오. (예: "역대급 방송 사고 발생!", "모두가 경악한 이유")
4. **경고문구 포함**: 기획의 'rationale'(기획 사유) 부분의 맨 앞에 반드시 아래 경고 문구를 포함시켜 출력해야 합니다:
   "[⚠️ 유튜브 자막 수집 차단(원인: {error_reason})으로 인해 영상 제목 기반으로 AI 쇼츠 기획을 임시 수행했습니다. 정밀 자막 기획을 원하시면 설정을 통해 유튜브 쿠키를 등록해 주세요.]"

반드시 JSON Schema 구조에 엄격히 맞추어 응답을 반환하십시오.
"""
        else:
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
3. **자막 텍스트 ('caption')**: 나중에 캡컷에서 한글 폰트로 편집할 화면 한글 자막입니다. 상황을 극대화하여 묘사하는 예능 자막 풍으로 간결하게 작성해 주십시오. (예: "역대급 방송 사고 발생!", "모두가 경악한 이유")
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
                "caption": "오늘의 하이라이트! 믿을 수 없는 방송 사고가 터졌습니다!"
            },
            {
                "start_time": "00:45",
                "end_time": "00:58",
                "tts_text": "まさかの展開にスタジオ大爆笑。この結末は予想できませんでした。",
                "caption": "설마했던 반전 결말에 스튜디오는 초토화되었습니다."
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
