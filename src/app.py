import os
import sys
import json
import requests
from flask import Flask, render_template, request, jsonify

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
    template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates')),
    static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))
)

@app.route('/')
def index():
    """웜 샌드 빈티지 대시보드 뷰 로드"""
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def api_search():
    """유튜브 기간 필터 및 조회수 순 자동 정렬 검색 API"""
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    period = data.get('period', 'this_week')  # today, this_week, this_month
    
    if not query:
        return jsonify({"error": "검색 키워드를 입력해 주세요."}), 400
        
    print(f"[App Backend] Searching YouTube for query: '{query}', period: '{period}'")
    try:
        # 기간 필터를 적용한 검색 실행 (최대 10개 수집 및 자동 조회수 정렬)
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
    
    # GitHub Workflow Dispatch API 주소
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
            print("[App Backend] GitHub Actions successfully triggered (204 No Content)")
            return jsonify({
                "success": True, 
                "message": "GitHub Actions 원격 가상 컴퓨터 기동 성공! 작업을 시작합니다."
            })
        else:
            error_msg = response.json().get('message', '알 수 없는 API 에러')
            print(f"[App Backend] GitHub API failed: {response.status_code} - {error_msg}")
            return jsonify({"error": f"GitHub API 호출 실패 ({response.status_code}): {error_msg}"}), response.status_code
    except Exception as e:
        print(f"[App Backend] Connection error: {e}")
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
        
        # remote_shorts_generator.yml 관련된 가장 최근의 런 스캔
        generator_runs = [r for r in runs_data if 'remote_shorts_generator' in r.get('path', '')]
        
        if not generator_runs:
            return jsonify({"status": "idle", "message": "원격 가동 내역이 없습니다."})
            
        latest_run = generator_runs[0]
        run_status = latest_run.get('status')       # queued, in_progress, completed
        conclusion = latest_run.get('conclusion')   # success, failure, cancelled
        run_id = latest_run.get('id')
        html_url = latest_run.get('html_url')
        
        # 완료되었고 성공했을 시 아티팩트 다운로드 웹 주소 동적 획득
        download_url = ""
        if run_status == "completed" and conclusion == "success":
            download_url = f"https://github.com/{repo_owner}/{repo_name}/actions/runs/{run_id}"
            
        return jsonify({
            "success": True,
            "run_id": run_id,
            "status": run_status,
            "conclusion": conclusion,
            "download_url": download_url,
            "html_url": html_url,
            "created_at": latest_run.get('created_at')
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # 클라우드 호스팅 환경을 위한 0.0.0.0 포트 5000 바인딩
    app.run(host='0.0.0.0', port=5000, debug=True)
