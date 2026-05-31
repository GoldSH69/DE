import os
import sys
import json
import requests
from flask import Flask, render_template, request, jsonify, Response

# 윈도우 cp949 인코딩 방지
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 프로젝트 임포트 경로 확보
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.collector import search_videos_by_keywords

app = Flask(
    __name__,
    static_url_path="",
    static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
    template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
)

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
PROJECT_XML_PATH = os.path.join(OUTPUT_DIR, "project_xml.xml")

@app.route('/')
def index():
    """웜 샌드 대시보드 뷰 로드"""
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    """유튜브 기간 필터 및 조회수 순 자동 정렬 검색 API"""
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    period = data.get('period', 'this_week')  # today, this_week, this_month, this_year
    
    if not query:
        return jsonify({"error": "검색 키워드를 입력해 주세요."}), 400
        
    print(f"[App Backend] Searching YouTube for query: '{query}', period: '{period}'")
    try:
        results = search_videos_by_keywords([query], limit_per_keyword=8, period=period)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        print(f"[App Backend] Search failed: {e}")
        return jsonify({"error": f"검색 중 오류가 발생했습니다: {str(e)}"}), 500

@app.route('/api/trigger_actions', methods=['POST'])
def api_trigger_actions():
    """GitHub API를 직접 호출하여 깃허브 액션 원격 빌드를 백그라운드 기동"""
    data = request.get_json() or {}
    video_url = data.get('video_url', '').strip()
    github_token = data.get('github_token', '').strip()
    gemini_key = data.get('gemini_api_key', '').strip()
    repo_owner = data.get('repo_owner', 'GoldSH69').strip()
    repo_name = data.get('repo_name', 'DE').strip()
    
    if not video_url:
        return jsonify({"error": "제작할 비디오 URL이 선택되지 않았습니다."}), 400
    if not github_token:
        return jsonify({"error": "GitHub Personal Access Token(PAT)이 입력되지 않았습니다. 우측 상단 설정을 완료해 주세요."}), 400
        
    print(f"[App Backend] Triggering GitHub Actions for repo: {repo_owner}/{repo_name}...")
    
    trigger_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/workflows/remote_shorts_generator.yml/dispatches"
    
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    payload = {
        "ref": "main",
        "inputs": {
            "video_url": video_url,
            "gemini_api_key": gemini_key
        }
    }
    
    try:
        response = requests.post(trigger_url, json=payload, headers=headers)
        if response.status_code == 204:
            return jsonify({
                "success": True, 
                "message": "GitHub Actions 원격 가상 컴퓨터 기동 성공! 작업을 시작합니다."
            })
        else:
            error_msg = response.json().get('message', '알 수 없는 API 에러')
            return jsonify({"error": f"GitHub API 호출 실패 ({response.status_code}): {error_msg}"}), response.status_code
    except Exception as e:
        return jsonify({"error": f"네트워크 통신 오류가 발생했습니다: {str(e)}"}), 500

@app.route('/api/check_status', methods=['POST'])
def api_check_status():
    """GitHub API 실행 목록을 스캔하여 현재 원격 쇼츠 생성 워크플로우 진행 상태 실시간 폴링"""
    data = request.get_json() or {}
    github_token = data.get('github_token', '').strip()
    repo_owner = data.get('repo_owner', 'GoldSH69').strip()
    repo_name = data.get('repo_name', 'DE').strip()
    
    if not github_token:
        return jsonify({"error": "GitHub Token이 제공되지 않았습니다."}), 400
        
    runs_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/runs"
    
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    try:
        response = requests.get(runs_url, headers=headers)
        if response.status_code != 200:
            return jsonify({"error": "실행 목록 조회 실패"}), response.status_code
            
        runs_data = response.json().get('workflow_runs', [])
        generator_runs = [r for r in runs_data if 'remote_shorts_generator' in r.get('path', '')]
        
        if not generator_runs:
            return jsonify({"status": "idle", "message": "원격 가동 내역이 없습니다."})
            
        latest_run = generator_runs[0]
        run_status = latest_run.get('status')       # queued, in_progress, completed
        conclusion = latest_run.get('conclusion')   # success, failure, cancelled
        run_id = latest_run.get('id')
        
        download_url = ""
        if run_status == "completed" and conclusion == "success":
            download_url = f"https://github.com/{repo_owner}/{repo_name}/actions/runs/{run_id}"
            
        return jsonify({
            "success": True,
            "run_id": run_id,
            "status": run_status,
            "conclusion": conclusion,
            "download_url": download_url
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================================================================
# [하이브리드 다이내믹 임포트 기술] 로컬 1번 상황 제어 API 복원
# ==================================================================
@app.route('/api/stream_generate_local')
def api_stream_generate_local():
    """로컬 1번 상황: 로컬 컴퓨터 내에서 직접 컷팅, TTS 및 FCP XML 즉시 실시간 복원"""
    video_url = request.args.get('video_url', '')
    title = request.args.get('title', '알 수 없는 비디오')
    
    if not video_url:
        def err_stream():
            yield f"data: {json.dumps({'status': 'error', 'message': '비디오 URL이 누락되었습니다.'})}\n\n"
        return Response(err_stream(), mimetype="text/event-stream")
        
    def log_event_generator_local():
        try:
            # 1. 외부 서버 배포 시 라이브러리 부재로 인한 충돌을 피하기 위해 런타임에 다이내믹 임포트(Dynamic Import) 수행!
            yield f"data: {json.dumps({'status': 'progress', 'message': '⚙️ 로컬 파이썬 엔진 라이브러리 동적 로드 중...'})}\n\n"
            
            from src.analyzer import analyze_video_transcript
            from src.processor import run_processing_pipeline
            from src.bridge import create_fcp_xml, create_subtitles_srt
            from src.main import fetch_and_clean_subtitles
            
            yield f"data: {json.dumps({'status': 'progress', 'message': '🚀 1단계: 유튜브 동영상 자막(SRT/VTT) 추출 중...'})}\n\n"
            transcript = fetch_and_clean_subtitles(video_url)
            yield f"data: {json.dumps({'status': 'progress', 'message': '✅ 자막 스캔 성공!'})}\n\n"
            
            yield f"data: {json.dumps({'status': 'progress', 'message': '💡 2단계: Gemini API 연동 60초 하이라이트 대본 기획 및 번역 추출 중...'})}\n\n"
            analysis = analyze_video_transcript(transcript, title)
            total_sec = analysis.get("total_duration_seconds", 0)
            yield f"data: {json.dumps({'status': 'progress', 'message': f'✅ Gemini AI 분석 완료! 총 {total_sec}초 구간 확정'})}\n\n"
            yield f"data: {json.dumps({'status': 'analysis', 'data': analysis})}\n\n"
            
            yield f"data: {json.dumps({'status': 'progress', 'message': '🎬 3단계: 유튜브 고화질 원본 다운로드 및 MoviePy 정밀 컷팅 시작...'})}\n\n"
            cut_files, tts_files = run_processing_pipeline(
                video_url,
                analysis.get("selected_scenes", []),
                voice="ja-JP-NanamiNeural"
            )
            yield f"data: {json.dumps({'status': 'progress', 'message': f'✅ 비디오 컷팅 ({len(cut_files)}개 조각) 및 edge-tts 나레이션 매칭 합성 완료'})}\n\n"
            
            yield f"data: {json.dumps({'status': 'progress', 'message': '🔗 4단계: 캡컷(CapCut) 직접 연동용 FCP 7 XML 뼈대 구성 및 스마트 동기화 정렬 중...'})}\n\n"
            create_fcp_xml(cut_files, tts_files, PROJECT_XML_PATH, fps=30)
            
            # SRT 자막 파일 생성
            PROJECT_SRT_PATH = os.path.join(OUTPUT_DIR, "subtitles_ko.srt")
            create_subtitles_srt(analysis.get("selected_scenes", []), cut_files, tts_files, PROJECT_SRT_PATH)
            
            yield f"data: {json.dumps({'status': 'progress', 'message': '✅ FCP 7 XML 및 SRT 자막 생성 완료!'})}\n\n"
            
            # 최종 마침표
            yield f"data: {json.dumps({'status': 'complete_local', 'message': '🎉 [로컬 직접 저장 완료] 결과 파일들이 내 컴퓨터 output/ 폴더에 직접 수립되었습니다!', 'xml_path': PROJECT_XML_PATH})}\n\n"
            
        except ImportError as ie:
            yield f"data: {json.dumps({'status': 'error', 'message': f'로컬 구동에 필요한 라이브러리(moviepy, edge-tts 등)가 서버에 미설치 상태입니다. 외부 인터넷 구동 상태이시라면 우측의 [GitHub Actions] 버튼을 사용해 주세요.'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'status': 'error', 'message': f'로컬 구동 중 예외 발생: {str(e)}'})}\n\n"
            
    return Response(log_event_generator_local(), mimetype="text/event-stream")

if __name__ == '__main__':
    # Flask 로컬 서버 기동
    app.run(host='0.0.0.0', port=5000, debug=True)
