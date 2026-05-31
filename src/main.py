import os
import sys
import json
import re
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

# 윈도우 콘솔 한글/이모지 출력 인코딩 오류(cp949) 방지 설정
try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
# 프로젝트 임포트 경로 확보
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.collector import collect_trends, load_existing_trends
from src.analyzer import analyze_video_transcript
from src.processor import run_processing_pipeline
from src.bridge import create_fcp_xml, create_subtitles_srt

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
PROJECT_XML_PATH = os.path.join(OUTPUT_DIR, "project_xml.xml")

def extract_youtube_video_id(url):
    """유튜브 비디오 URL에서 11자리 비디오 ID를 추출합니다."""
    pattern = r'(?:v=|\/shorts\/|\/embed\/|\/v\/|youtu\.be\/|\/u\/\w\/)([^#\&\?]{11})'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    
    # query string fallback
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    if parsed.netloc in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        q = parse_qs(parsed.query)
        if 'v' in q and len(q['v']) > 0:
            return q['v'][0]
            
    if len(url.strip()) == 11:
        return url.strip()
        
    return None

def format_seconds_to_time_str(seconds):
    """초를 MM:SS 또는 HH:MM:SS 타임코드로 변환합니다."""
    seconds = int(round(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def fetch_and_clean_subtitles(video_url, languages_list=None):
    """youtube-transcript-api를 사용하여 비디오의 자막을 100% 익명으로 다운로드하고 정제합니다."""
    from youtube_transcript_api import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
    
    if languages_list is None:
        languages_list = ['ko', 'ja', 'en']
        
    if "mock" in video_url.lower() or "0010" in video_url:
        print("[Main] Mock video URL/ID detected. Returning mock transcript...")
        return """
[00:01] 안녕하십니까 오늘은 특별한 일본 예능 클립을 소개하겠습니다.
[00:10] 어? 지금 무대 뒤에서 무슨 소리가 들리는데요? 진짜 예상치 못한 일이 벌어집니다!
[00:15] 와! 대단합니다! 출연자가 갑자기 넘어졌어요!
[00:22] 큰일 날 뻔 했지만 웃음으로 극복합니다.
[00:30] 이번 코너는 진지한 토론 코너입니다.
[00:45] 그런데 갑자기 패널이 벌떡 일어나며 춤을 추기 시작합니다!
[00:50] 이게 무슨 일이죠? 다들 너무 웃겨서 뒤집어집니다!
[00:58] 결국 오늘의 우승은 댄스맨에게 돌아갑니다. 감사합니다.
"""
        
    print(f"[Main] Extracting subtitles for {video_url} with languages: {languages_list}...")
    
    try:
        video_id = extract_youtube_video_id(video_url)
        if not video_id:
            raise ValueError(f"유튜브 비디오 ID를 추출하지 못했습니다: {video_url}")
            
        # 중국어 간체/번체 및 지역 코드 확장 매핑 (중국어 수집 극대화)
        expanded_langs = []
        for lang in languages_list:
            lang = lang.strip().lower()
            if lang == 'zh':
                expanded_langs.extend(['zh', 'zh-Hans', 'zh-Hant', 'zh-HK', 'zh-TW', 'zh-SG', 'zh-CN'])
            else:
                expanded_langs.append(lang)
                
        # 100% 익명 API 호출 실행
        api_instance = YouTubeTranscriptApi()
        transcript_list_obj = api_instance.list(video_id)
        
        # 1단계: 선호하는 언어 매칭 시도
        transcript = None
        try:
            transcript = transcript_list_obj.find_transcript(expanded_langs)
            print(f"[Main] Found preferred language transcript: {transcript.language_code}")
        except NoTranscriptFound:
            # 2단계: 선호 언어가 없다면, 실존하는 첫 번째 자막 트랙을 가져옵니다.
            available_transcripts = list(transcript_list_obj)
            if available_transcripts:
                transcript = available_transcripts[0]
                print(f"[Main] Preferred language not found. Falling back to available transcript: {transcript.language_code}")
            else:
                raise TranscriptsDisabled(video_id)
                
        transcript_list = transcript.fetch()
        
        cleaned_lines = []
        for item in transcript_list:
            # 딕셔너리 혹은 객체 양식 모두 완벽 호환되게 방어 설계
            if isinstance(item, dict):
                text = item.get('text', '')
                start = item.get('start', 0.0)
            else:
                text = getattr(item, 'text', '')
                start = getattr(item, 'start', 0.0)
                
            text = text.strip()
            if not text:
                continue
                
            # 개행 제거
            text = text.replace('\n', ' ').replace('\r', ' ')
            time_str = format_seconds_to_time_str(start)
            fmt_line = f"[{time_str}] {text}"
            
            cleaned_lines.append(fmt_line)
            
        if not cleaned_lines:
            raise RuntimeError("추출된 자막 내용이 비어있습니다.")
            
        final_transcript = "\n".join(cleaned_lines[:500]) # 토큰 절약을 위해 상위 500줄만 파싱
        print(f"[Main] Subtitle parsing complete. Extracted {len(cleaned_lines)} blocks.")
        return final_transcript
        
    except TranscriptsDisabled:
        error_msg = "[❌ 유튜브 자막 비활성화] 이 비디오는 유튜브에서 자막 대본 기능이 완전히 비활성화되어 제공되지 않는 영상입니다. 대사나 음성 대화가 실존하고 자막이 열려 있는 다른 예능 영상을 선택해 주세요."
        print(f"[Main] Subtitle extraction failed: {error_msg}")
        raise RuntimeError(error_msg)
    except VideoUnavailable:
        error_msg = "[⚠️ 동영상 접근 불가] 유튜브 동영상 주소가 올바르지 않거나 비공개 혹은 삭제된 영상입니다."
        print(f"[Main] Subtitle extraction failed: {error_msg}")
        raise RuntimeError(error_msg)
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "Too Many Requests" in err_str:
            error_msg = f"[🚫 유튜브 트래픽 차단 (429)] 로컬 PC의 IP 주소가 유튜브로부터 일시적인 요청 과부하로 차단(429)되었습니다. 이 경우 대시보드 우측의 [GitHub Actions 원격 제작] 버튼을 구동해 주시기 바랍니다."
        else:
            error_msg = f"[⚙️ 로컬 파이썬 시스템 오류] 유튜브 자막(대본) 추출 실패 (원인: {err_str})"
        print(f"[Main] Subtitle extraction failed: {error_msg}")
        raise RuntimeError(error_msg)

def run_main_pipeline(specific_url=None, languages_str="ko,ja,en"):
    """Dopamine Explorer v2 올인원 영상 자동화 파이프라인을 기동합니다."""
    print("==================================================================")
    print("🚀 Dopamine Explorer v2 (Automation & CapCut Bridge) Pipeline Start")
    print("==================================================================")
    
    # 1단계: 트렌드 데이터 수집
    if specific_url:
        target_video = {
            "title": "사용자 지정 동영상",
            "url": specific_url
        }
    else:
        trends = load_existing_trends()
        if not trends:
            print("[Main] Database empty. Collecting fresh trend data...")
            trends = collect_trends(limit_per_source=2)
        if not trends:
            print("[Main] Critical Error: No video targets found to analyze.")
            sys.exit(1)
        target_video = trends[0]
        print(f"[Main] Target selected from Trends DB: '{target_video['title']}' (Views: {target_video.get('view_count', 0)})")
        
    # 2단계: 자막 추출
    languages_list = languages_str.split(',') if languages_str else ['ko', 'ja', 'en']
    transcript = fetch_and_clean_subtitles(target_video["url"], languages_list=languages_list)
    
    # 3단계: Gemini AI 분석 및 기획안 생성
    analysis_result = analyze_video_transcript(transcript, target_video["title"])
    
    print("\n------------------------------------------------------------------")
    print("💡 Gemini AI 분석 및 일본어 쇼츠 기획 결과")
    print(f"사유(Rationale): {analysis_result.get('rationale')}")
    print(f"총 시간(Duration): {analysis_result.get('total_duration_seconds')} 초")
    for idx, sc in enumerate(analysis_result.get("selected_scenes", [])):
        print(f"  씬 {idx + 1}: [{sc.get('start_time')} ~ {sc.get('end_time')}]")
        print(f"    - 나레이션(JA): {sc.get('tts_text')}")
        print(f"    - 화면자막(KO): {sc.get('caption_ko')}")
    print("------------------------------------------------------------------\n")
    
    # 4단계: 비디오 다운로드, 컷 편집 및 edge-tts 합성
    print("[Main] Process video files, cut clips, and synthesize neural TTS voices...")
    cut_files, tts_files = run_processing_pipeline(
        target_video["url"], 
        analysis_result.get("selected_scenes", []),
        voice="ja-JP-NanamiNeural"  # 네이티브 일본어 여성 신경망 목소리 기본값
    )
    
    # 5단계: CapCut FCP 7 XML 타임라인 브릿지 생성 및 SRT 자막 빌드
    print("[Main] Connecting clips and voices into CapCut FCP 7 XML format...")
    create_fcp_xml(cut_files, tts_files, PROJECT_XML_PATH, fps=30)
    
    # SRT 자막 파일 생성
    PROJECT_SRT_PATH = os.path.join(OUTPUT_DIR, "subtitles.srt")
    create_subtitles_srt(analysis_result.get("selected_scenes", []), cut_files, tts_files, PROJECT_SRT_PATH, languages_list=languages_list)
    
    # 6단계: 완성본 합본 MP4 비디오 믹싱 생성
    print("[Main] Merging video parts and neural voices into unified MP4 video (0.5s visual hook)...")
    PROJECT_MP4_PATH = os.path.join(OUTPUT_DIR, "shorts_merged.mp4")
    from src.processor import merge_shorts_video
    merge_shorts_video(cut_files, tts_files, analysis_result.get("selected_scenes", []), PROJECT_MP4_PATH)
    
    print("\n==================================================================")
    print("🎉 Pipeline Completed Successfully!")
    print(f"👉 Merged Video Path: {PROJECT_MP4_PATH}")
    print(f"👉 XML File Path: {PROJECT_XML_PATH}")
    print(f"👉 SRT Subtitles Path: {PROJECT_SRT_PATH}")
    print("👉 Video clips and audio parts are located in the output folder.")
    print("👉 [1] CapCut Desktop을 실행하고 '가져오기(Import) -> XML'을 눌러 XML 파일을 불러오세요!")
    print("👉 [2] 자막은 CapCut '텍스트(Text) -> 로컬 자막(Local Captions) -> 가져오기(Import)'에서 'subtitles_ko.srt'를 불러와 타임라인에 드래그하세요!")
    print("==================================================================")
 
if __name__ == "__main__":
    # 실행 시 인자로 유튜브 URL을 전달하면 해당 비디오로 바로 기획 및 브릿지 수행
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    langs_arg = sys.argv[2] if len(sys.argv) > 2 else "ko,ja,en"
    run_main_pipeline(url_arg, languages_str=langs_arg)
