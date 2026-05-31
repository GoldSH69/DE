import os
import sys
import json
import zipfile
import io
import asyncio
from flask import Flask, render_template, request, jsonify, Response, send_file

# 윈도우 cp949 인코딩 방지
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 프로젝트 임포트 경로 확보
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.collector import search_videos_by_keywords, load_existing_trends
from src.analyzer import analyze_video_transcript
from src.processor import run_processing_pipeline
from src.bridge import create_fcp_xml

# Flask 앱 경로 커스텀 설정 (상위 폴더의 templates 및 static 참조)
app = Flask(
    __name__,
    template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates')),
    static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
)

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
PROJECT_XML_PATH = os.path.join(OUTPUT_DIR, "project_xml.xml")

@app.route('/')
def index():
    """웜 샌드 대시보드 메인 화면 로딩"""
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    """유튜브 실시간 예능 키워드 검색 API"""
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({"error": "검색 키워드를 입력해 주세요."}), 400
        
    print(f"[App Backend] Live searching for keyword: '{query}'")
    try:
        # 키워드 기반 실시간 검색 실행 (최대 8개 수집)
        results = search_videos_by_keywords([query], limit_per_keyword=8)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        print(f"[App Backend] Search failed: {e}")
        return jsonify({"error": f"검색 중 오류가 발생했습니다: {str(e)}"}), 500

def get_subtitles_silently(video_url):
    """임시 자막 추출 (에러 시 Fallback 메세지 반환)"""
    from src.main import fetch_and_clean_subtitles
    try:
        return fetch_and_clean_subtitles(video_url)
    except Exception:
        return "자막 추출에 실패하여 기본 템플릿 기준으로 기획을 시도합니다."

@app.route('/api/stream_generate')
def api_stream_generate():
    """Server-Sent Events(SSE) 실시간 작업 로그 스트리밍 API"""
    video_url = request.args.get('video_url', '')
    title = request.args.get('title', '알 수 없는 비디오')
    
    if not video_url:
        def err_stream():
            yield f"data: {json.dumps({'status': 'error', 'message': '비디오 URL이 누락되었습니다.'})}\n\n"
        return Response(err_stream(), mimetype="text/event-stream")
        
    def log_event_generator():
        try:
            # 1. 프로세스 개시
            yield f"data: {json.dumps({'status': 'progress', 'message': '🚀 쇼츠 제작 엔진 시동 완료!'})}\n\n"
            
            # 2. 자막 추출 단계
            yield f"data: {json.dumps({'status': 'progress', 'message': '🔍 1단계: 원본 동영상 자막(SRT/VTT) 스캔 중...'})}\n\n"
            transcript = get_subtitles_silently(video_url)
            yield f"data: {json.dumps({'status': 'progress', 'message': f'✅ 자막 스캔 완료 ({len(transcript)} 바이트 확보)'})}\n\n"
            
            # 3. Gemini AI 기획 분석 단계
            yield f"data: {json.dumps({'status': 'progress', 'message': '💡 2단계: Gemini API 연동 대본 및 60초 하이라이트 구간 분석 중...'})}\n\n"
            analysis = analyze_video_transcript(transcript, title)
            total_sec = analysis.get("total_duration_seconds", 0)
            yield f"data: {json.dumps({'status': 'progress', 'message': f'✅ Gemini AI 기획 분석 완성! 총 {total_sec}초 구간 선정'})}\n\n"
            yield f"data: {json.dumps({'status': 'analysis', 'data': analysis})}\n\n"
            
            # 4. 다운로드 & 컷 편집 & edge-tts 합성 단계
            yield f"data: {json.dumps({'status': 'progress', 'message': '🎬 3단계: 유튜브 원본 다운로드 및 MoviePy 고해상도 구간별 컷팅 개시...'})}\n\n"
            # run_processing_pipeline 실행 (비디오 캐싱 자동 적용)
            cut_files, tts_files = run_processing_pipeline(
                video_url,
                analysis.get("selected_scenes", []),
                voice="ja-JP-NanamiNeural"
            )
            yield f"data: {json.dumps({'status': 'progress', 'message': f'✅ 비디오 컷팅 성공 ({len(cut_files)}개 조각) 및 edge-tts 일본어 신경망 음성 합성 완료'})}\n\n"
            
            # 5. CapCut XML 타임라인 조립 단계
            yield f"data: {json.dumps({'status': 'progress', 'message': '🔗 4단계: 캡컷(CapCut) 직접 연동용 FCP 7 XML 타임라인 뼈대 조립 중...'})}\n\n"
            create_fcp_xml(cut_files, tts_files, PROJECT_XML_PATH, fps=30)
            yield f"data: {json.dumps({'status': 'progress', 'message': '✅ FCP 7 XML 생성 및 스마트 타임라인 정렬 싱크 완료!'})}\n\n"
            
            # 6. 최종 마침표
            yield f"data: {json.dumps({'status': 'complete', 'message': '🎉 모든 가공 처리가 완벽히 성공하였습니다!', 'xml_path': PROJECT_XML_PATH})}\n\n"
            
        except Exception as e:
            print(f"[App Backend] Error during SSE pipeline execution: {e}")
            yield f"data: {json.dumps({'status': 'error', 'message': f'처리 중 오류가 발생했습니다: {str(e)}'})}\n\n"
            
    return Response(log_event_generator(), mimetype="text/event-stream")

@app.route('/api/download_project')
def api_download_project():
    """모든 가공 완료 미디어(mp4, mp3) 및 CapCut XML을 단 하나의 ZIP 압축 아카이브로 묶어 다운로드 전송"""
    print("[App Backend] Building ZIP archive for the project outputs...")
    
    # 컷 및 보이스 서브디렉토리 경로 확보
    video_cuts_dir = os.path.join(OUTPUT_DIR, "video_cuts")
    tts_voices_dir = os.path.join(OUTPUT_DIR, "tts_voices")
    
    # 메모리 내 바이너리 스트림 버퍼 생성
    memory_file = io.BytesIO()
    
    try:
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. XML 파일 압축 추가
            if os.path.exists(PROJECT_XML_PATH):
                zipf.write(PROJECT_XML_PATH, "project_xml.xml")
                
            # 2. 비디오 컷팅 조각들 추가
            if os.path.exists(video_cuts_dir):
                for file in os.listdir(video_cuts_dir):
                    if file.endswith(".mp4"):
                        zipf.write(os.path.join(video_cuts_dir, file), f"video_cuts/{file}")
                        
            # 3. TTS 음성 파일들 추가
            if os.path.exists(tts_voices_dir):
                for file in os.listdir(tts_voices_dir):
                    if file.endswith(".mp3"):
                        zipf.write(os.path.join(tts_voices_dir, file), f"tts_voices/{file}")
                        
        memory_file.seek(0)
        print("[App Backend] ZIP archive successfully compiled. Sending file streams...")
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name='dopamine_shorts_project.zip'
        )
    except Exception as e:
        print(f"[App Backend] Failed to compile ZIP archive: {e}")
        return jsonify({"error": f"ZIP 압축 파일 컴파일에 실패했습니다: {str(e)}"}), 500

if __name__ == '__main__':
    # Flask 로컬 서버 기동 (기본 포트: 5000)
    app.run(host='0.0.0.0', port=5000, debug=True)
