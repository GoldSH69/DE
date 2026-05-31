import os
import sys
import json
import re
import yt_dlp

# 윈도우 콘솔 한글/이모지 출력 인코딩 오류(cp949) 방지 설정
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from src.collector import collect_trends, load_existing_trends
from src.analyzer import analyze_video_transcript
from src.processor import run_processing_pipeline
from src.bridge import create_fcp_xml, create_subtitles_srt

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
PROJECT_XML_PATH = os.path.join(OUTPUT_DIR, "project_xml.xml")

def fetch_and_clean_subtitles(video_url):
    """yt-dlp를 사용하여 비디오의 자막을 다운로드하고, 순수 텍스트와 시간 정보만 추출합니다."""
    print(f"[Main] Extracting subtitles for {video_url}...")
    
    # 자막 파일 저장을 위한 임시 경로
    subtitle_temp_tmpl = os.path.join(OUTPUT_DIR, "temp_sub")
    
    ydl_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['ko', 'ja', 'en'],  # 한국어 우선, 일본어, 영어 순
        'outtmpl': subtitle_temp_tmpl,
        'quiet': True
    }
    
    # 지능형 쿠키(Cookies) 주입 엔진 가동 (유튜브 로봇 방지 우회)
    cookies_path = os.path.join(OUTPUT_DIR, "cookies.txt")
    if os.path.exists(cookies_path):
        print(f"[Main] Detected custom cookies.txt -> Using cookie file: {cookies_path}")
        ydl_opts['cookiefile'] = cookies_path
    elif not os.environ.get("GITHUB_ACTIONS"):
        # 깃허브 액션 환경이 아닌 로컬 PC 구동 시에만 브라우저로부터 로그인 쿠키 실시간 흡수
        try:
            print("[Main] Local environment detected. Auto-loading cookies from Chrome/Edge/Firefox...")
            ydl_opts['cookiesfrombrowser'] = ('chrome', 'edge', 'firefox', 'brave', 'safari', 'opera')
        except Exception as e:
            print(f"[Main] Browser cookies load skipped: {e}")
            
    try:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
        except Exception as yde:
            # 브라우저 잠김 등의 사유로 쿠키 로드 에러 시 쿠키 옵션 제거하고 재시도하는 안전 폴백
            if 'cookiesfrombrowser' in ydl_opts:
                print(f"[Main] Browser cookies db locked ({yde}). Retrying search without browser cookies...")
                del ydl_opts['cookiesfrombrowser']
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=True)
            else:
                raise yde
            
        # 다운로드된 파일 탐색 (.vtt 또는 .srt 확장자)
        sub_file = None
        for file in os.listdir(OUTPUT_DIR):
            if file.startswith("temp_sub.") and (file.endswith(".vtt") or file.endswith(".srt")):
                sub_file = os.path.join(OUTPUT_DIR, file)
                break
                
        if not sub_file:
            print("[Main] Warning: No subtitle files (.vtt/.srt) found on YouTube. Generates a placeholder transcript.")
            return "자막 정보가 존재하지 않아 오프닝과 핵심 위주의 하이라이트를 추출합니다."

        # 자막 파싱 및 텍스트 정제
        cleaned_lines = []
        with open(sub_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # VTT/SRT 타임코드 및 태그 정제 정규식
        # 예: 00:01:23.450 --> 00:01:25.670
        time_pattern = re.compile(r'(\d{2}:\d{2}:\d{2}[\.,]\d{3}) --> (\d{2}:\d{2}:\d{2}[\.,]\d{3})')
        html_tag_pattern = re.compile(r'<[^>]+>')
        
        current_time = "00:00"
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.isdigit() or "WEBVTT" in line or "NOTE" in line:
                continue
                
            match = time_pattern.search(line)
            if match:
                # 시작 시간만 파싱하여 타임라인 참조용으로 기록 (HH:MM:SS -> MM:SS 간소화)
                full_time = match.group(1).split('.')[0].split(',')[0]
                time_parts = full_time.split(':')
                if time_parts[0] == "00":
                    current_time = f"{time_parts[1]}:{time_parts[2]}"
                else:
                    current_time = full_time
                continue
                
            # HTML 태그 제거 및 텍스트 가공
            text_line = html_tag_pattern.sub('', line)
            text_line = re.sub(r'&\w+;', '', text_line)  # &nbsp; 등 엔티티 제거
            text_line = text_line.strip()
            
            if text_line:
                # 중복 줄 및 시스템 메세지 제외
                fmt_line = f"[{current_time}] {text_line}"
                if cleaned_lines and cleaned_lines[-1] == fmt_line:
                    continue
                cleaned_lines.append(fmt_line)
                
        # 임시 자막 파일 청소
        try:
            os.remove(sub_file)
        except Exception:
            pass
            
        final_transcript = "\n".join(cleaned_lines[:500]) # 컨텍스트 토큰 절약을 위해 상위 500줄만 파싱
        print(f"[Main] Subtitle parsing complete. Extracted {len(cleaned_lines)} blocks.")
        return final_transcript
        
    except Exception as e:
        print(f"[Main] Subtitle extraction failed: {e}")
        # 자막 수집에 실패한 경우 크래시 내는 대신 자막 수집 실패 코드를 전달해 제목 기반 기획으로 자동 폴백
        print("[Main] Warning: Subtitle extraction failed. Falling back to Title-based AI planning.")
        return f"__SUBTITLE_EXTRACTION_FAILED_429__: {str(e)}"

def run_main_pipeline(specific_url=None):
    """Dopamine Explorer v2 올인원 영상 자동화 파이프라인을 기동합니다."""
    print("==================================================================")
    print("🚀 Dopamine Explorer v2 (Automation & CapCut Bridge) Pipeline Start")
    print("==================================================================")
    
    # 1단계: 트렌드 데이터 수집
    trends = load_existing_trends()
    if not trends or specific_url:
        print("[Main] Database empty or specific URL provided. Collecting fresh trend data...")
        trends = collect_trends(limit_per_source=2)
        
    if not trends and not specific_url:
        print("[Main] Critical Error: No video targets found to analyze.")
        sys.exit(1)
        
    # 타겟 비디오 확정
    if specific_url:
        target_video = {
            "title": "사용자 지정 동영상",
            "url": specific_url
        }
    else:
        target_video = trends[0]
        print(f"[Main] Target selected from Trends DB: '{target_video['title']}' (Views: {target_video.get('view_count', 0)})")
        
    # 2단계: 자막 추출
    transcript = fetch_and_clean_subtitles(target_video["url"])
    
    # 3단계: Gemini AI 분석 및 기획안 생성
    analysis_result = analyze_video_transcript(transcript, target_video["title"])
    
    print("\n------------------------------------------------------------------")
    print("💡 Gemini AI 분석 및 일본어 쇼츠 기획 결과")
    print(f"사유(Rationale): {analysis_result.get('rationale')}")
    print(f"총 시간(Duration): {analysis_result.get('total_duration_seconds')} 초")
    for idx, sc in enumerate(analysis_result.get("selected_scenes", [])):
        print(f"  씬 {idx + 1}: [{sc.get('start_time')} ~ {sc.get('end_time')}]")
        print(f"    - 나레이션(JA): {sc.get('tts_text')}")
        print(f"    - 화면자막(KO): {sc.get('caption')}")
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
    PROJECT_SRT_PATH = os.path.join(OUTPUT_DIR, "subtitles_ko.srt")
    create_subtitles_srt(analysis_result.get("selected_scenes", []), cut_files, tts_files, PROJECT_SRT_PATH)
    
    print("\n==================================================================")
    print("🎉 Pipeline Completed Successfully!")
    print(f"👉 XML File Path: {PROJECT_XML_PATH}")
    print(f"👉 SRT Subtitles Path: {PROJECT_SRT_PATH}")
    print("👉 Video clips and audio parts are located in the output folder.")
    print("👉 [1] CapCut Desktop을 실행하고 '가져오기(Import) -> XML'을 눌러 XML 파일을 불러오세요!")
    print("👉 [2] 자막은 CapCut '텍스트(Text) -> 로컬 자막(Local Captions) -> 가져오기(Import)'에서 'subtitles_ko.srt'를 불러와 타임라인에 드래그하세요!")
    print("==================================================================")

if __name__ == "__main__":
    # 실행 시 인자로 유튜브 URL을 전달하면 해당 비디오로 바로 기획 및 브릿지 수행
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_main_pipeline(url_arg)
