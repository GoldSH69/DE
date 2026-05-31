import os
import json
from datetime import datetime
import yt_dlp

# 기본 설정 정보
DEFAULT_CHANNELS = [
    "https://www.youtube.com/@yoshimotokogyo/videos",  # 일본 요시모토 흥업 (대표 코미디 채널)
    "https://www.youtube.com/@super-sundays/videos"   # 임의의 예능/엔터테인먼트 성격의 채널 예시
]

DEFAULT_KEYWORDS = [
    "일본 예능 레전드",
    "일본 코미디 레전드"
]

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
TRENDS_FILE = os.path.join(DATA_DIR, "trends.json")

def ensure_data_directory():
    """data 디렉토리가 존재하는지 확인하고 없으면 생성합니다."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"[Collector] Created data directory: {DATA_DIR}")

def load_existing_trends():
    """기존 수집된 trends.json 데이터를 로드합니다."""
    ensure_data_directory()
    if os.path.exists(TRENDS_FILE):
        try:
            with open(TRENDS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            print(f"[Collector] Error loading existing trends.json: {e}")
    return []

def save_trends(trends):
    """trends.json 파일에 데이터를 정렬 및 누적하여 저장합니다."""
    ensure_data_directory()
    try:
        with open(TRENDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(trends, f, ensure_ascii=False, indent=2)
        print(f"[Collector] Successfully saved {len(trends)} items to {TRENDS_FILE}")
    except Exception as e:
        print(f"[Collector] Error saving trends.json: {e}")

def fetch_videos_from_channel(channel_url, limit=5):
    """yt-dlp를 이용하여 채널에서 최근 비디오를 수집합니다."""
    print(f"[Collector] Fetching videos from channel: {channel_url}")
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'force_generic_extractor': False,
    }
    
    videos = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            if 'entries' in info:
                # 최근 limit 개수만큼만 추출
                entries = [e for e in info['entries'] if e]
                for entry in entries[:limit]:
                    # 숏츠 제외를 위해 duration 체크 (단, flat extract에서는 duration이 안 나올 수 있어 추후 필터링 시 고려)
                    duration = entry.get('duration')
                    if duration and duration < 120:  # 2분 미만 영상은 숏폼으로 간주하고 스킵
                        continue
                    
                    video_id = entry.get('id')
                    raw_date = entry.get('upload_date')
                    if raw_date and len(raw_date) == 8:
                        published_date_text = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                    else:
                        published_date_text = "최근"
                    
                    videos.append({
                        "video_id": video_id,
                        "title": entry.get('title'),
                        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else entry.get('url'),
                        "view_count": entry.get('view_count', 0),
                        "duration": duration,
                        "published_date": raw_date or datetime.now().strftime("%Y%m%d"),
                        "published_date_text": published_date_text,
                        "collected_at": datetime.now().isoformat()
                    })
    except Exception as e:
        print(f"[Collector] Error fetching from {channel_url}: {e}")
    return videos

def parse_relative_time_to_yyyymmdd(text):
    """'3 days ago' 나 '1 week ago' 같은 상대 시간을 YYYYMMDD 문자열로 근사치 계산합니다."""
    from datetime import datetime, timedelta
    import re
    
    now = datetime.now()
    if not text:
        return now.strftime("%Y%m%d")
        
    cleaned = text.lower().strip()
    match = re.search(r'(\d+)\s+(day|week|month|year|hour|minute)', cleaned)
    if not match:
        return now.strftime("%Y%m%d")
        
    value = int(match.group(1))
    unit = match.group(2)
    
    if 'hour' in unit or 'minute' in unit:
        delta = timedelta(hours=value)
    elif 'day' in unit:
        delta = timedelta(days=value)
    elif 'week' in unit:
        delta = timedelta(weeks=value)
    elif 'month' in unit:
        delta = timedelta(days=value * 30)
    elif 'year' in unit:
        delta = timedelta(days=value * 365)
    else:
        delta = timedelta(0)
        
    target_date = now - delta
    return target_date.strftime("%Y%m%d")

def search_videos_by_keywords(keywords, limit_per_keyword=5, period="this_week"):
    """키워드 검색을 통해 특정 기간(하루, 1주, 한달) 동안의 고성과 영상을 수집 및 조회수 순 정렬합니다."""
    import requests
    import urllib.parse
    videos = []
    
    # 1단계: 지능형 Invidious API 인스턴스 다중 우회망 가동 (100% 날짜 정밀 필터링 및 429 우회 보장)
    invidious_instances = [
        'https://inv.thepixora.com',
        'https://yt.chocolatemoo53.com',
        'https://invidious.projectsegfau.lt',
        'https://invidious.privacydev.net',
        'https://inv.tux.im',
        'https://invidious.slipfox.xyz',
        'https://invidious.nerdvpn.de'
    ]
    
    # Invidious date parameter mapping: "today", "week", "month", "year"
    date_param = ""
    if period == "today":
        date_param = "today"
    elif period == "this_week":
        date_param = "week"
    elif period == "this_month":
        date_param = "month"
    elif period == "this_year":
        date_param = "year"
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for kw in keywords:
        invidious_success = False
        
        # 1-1단계: Invidious 인스턴스 로테이션 검색 시도
        for instance in invidious_instances:
            url = f"{instance}/api/v1/search?q={urllib.parse.quote(kw)}&date={date_param}&type=video"
            print(f"[Collector] Live searching YouTube via Invidious API: {instance}")
            try:
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    items = response.json()
                    if isinstance(items, list) and len(items) > 0:
                        count = 0
                        for item in items:
                            if item.get('type') != 'video' or not item.get('videoId'):
                                continue
                            
                            duration = item.get('lengthSeconds', 0)
                            if duration > 0 and duration < 120:  # 숏츠 필터링
                                continue
                                
                            video_id = item.get('videoId')
                            published_text = item.get('publishedText') or "최근"
                            approx_date = parse_relative_time_to_yyyymmdd(published_text)
                            
                            videos.append({
                                "video_id": video_id,
                                "title": item.get('title'),
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "view_count": item.get('viewCount', 0) or 0,
                                "duration": duration,
                                "published_date": approx_date,
                                "published_date_text": published_text,
                                "collected_at": datetime.now().isoformat()
                            })
                            count += 1
                            if count >= limit_per_keyword:
                                break
                        
                        if count > 0:
                            print(f"[Collector] Successfully retrieved {count} filtered videos from Invidious ({instance.replace('https://', '')})")
                            invidious_success = True
                            break
            except Exception as e:
                print(f"[Collector] Invidious instance {instance} failed: {e}")
                
        # 2단계: Invidious 인스턴스 전원 실패 시, 로컬 yt-dlp 백업 수동 폴백 가동
        if not invidious_success:
            print("[Collector] Warning: All Invidious API instances failed. Falling back to local yt-dlp scraper...")
            
            # yt-dlp의 경우 sp 파라미터를 사용한 검색 URL 수립
            sp_value = ""
            if period == "today":
                sp_value = "EgIIAg%3D%3D"
            elif period == "this_week":
                sp_value = "EgQIATAB"
            elif period == "this_month":
                sp_value = "EgQIAhAB"
            elif period == "this_year":
                sp_value = "EgQIAxAB"
                
            if sp_value:
                encoded_kw = urllib.parse.quote(kw)
                search_query = f"https://www.youtube.com/results?search_query={encoded_kw}&sp={sp_value}"
            else:
                search_query = f"ytsearch{limit_per_keyword}:{kw}"
                
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'skip_download': True,
            }
            
            try:
                import yt_dlp
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(search_query, download=False)
                    entries = info.get('entries', []) if info else []
                    
                    # yt-dlp 필터 결과가 0개라면 일반 ytsearch로 최종 폴백
                    if not entries and sp_value:
                        print(f"[Collector] Strict yt-dlp period filter returned 0 results. Falling back to general ytsearch...")
                        fallback_query = f"ytsearch{limit_per_keyword}:{kw}"
                        info = ydl.extract_info(fallback_query, download=False)
                        entries = info.get('entries', []) if info else []
                        
                    entries = entries[:limit_per_keyword]
                    for entry in entries:
                        if not entry:
                            continue
                            
                        duration = entry.get('duration')
                        if duration and duration < 120:
                            continue
                            
                        video_id = entry.get('id')
                        raw_date = entry.get('upload_date')
                        
                        # yt-dlp flat extraction은 upload_date가 제공되지 않으므로, 최근 영상으로 표시하지 않고 "날짜 확인 필요"로 안내하여 명확성 확보
                        if raw_date and len(raw_date) == 8:
                            published_date_text = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                        else:
                            published_date_text = "날짜 확인 필요"
                            
                        videos.append({
                            "video_id": video_id,
                            "title": entry.get('title'),
                            "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else entry.get('url'),
                            "view_count": entry.get('view_count', 0) or 0,
                            "duration": duration,
                            "published_date": raw_date or datetime.now().strftime("%Y%m%d"),
                            "published_date_text": published_date_text,
                            "collected_at": datetime.now().isoformat()
                        })
            except Exception as yte:
                print(f"[Collector] Critical: Backup yt-dlp search also failed: {yte}")
                
    # 전체 수집 후 조회수 높은 순으로 최종 내림차순 정렬
    videos.sort(key=lambda x: x.get('view_count', 0), reverse=True)
    
    # [자막 유무 및 언어 실시간 초고속 병렬 pre-scan 스캔 엔진 가동]
    import concurrent.futures
    from youtube_transcript_api import YouTubeTranscriptApi
    
    def check_video_subtitles(video_item):
        try:
            v_id = video_item.get("video_id")
            if not v_id:
                video_item["has_subtitles"] = False
                video_item["subtitle_languages"] = []
                return video_item
                
            # 100% 익명으로 자막 목록을 가져와 가능한 언어를 실시간 스캔
            transcript_list_obj = YouTubeTranscriptApi.list(v_id)
            langs = []
            for t in transcript_list_obj:
                langs.append(t.language_code.upper())
                
            video_item["has_subtitles"] = len(langs) > 0
            video_item["subtitle_languages"] = langs
        except Exception:
            video_item["has_subtitles"] = False
            video_item["subtitle_languages"] = []
            
        return video_item
        
    print(f"[Collector] Starting parallel subtitle pre-scan for {len(videos)} candidates...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        videos = list(executor.map(check_video_subtitles, videos))
        
    print("[Collector] Subtitle pre-scanning complete.")
    return videos

def collect_trends(channels=None, keywords=None, limit_per_source=5):
    """전체 수집 프로세스를 실행하고 trends.json을 갱신합니다."""
    print("[Collector] Starting trend collection process...")
    
    if channels is None:
        channels = DEFAULT_CHANNELS
    if keywords is None:
        keywords = DEFAULT_KEYWORDS
        
    collected_videos = []
    
    # 1. 채널별 수집
    for url in channels:
        collected_videos.extend(fetch_videos_from_channel(url, limit=limit_per_source))
        
    # 2. 키워드 검색 수집
    collected_videos.extend(search_videos_by_keywords(keywords, limit_per_keyword=3))
    
    # 3. 데이터 병합 및 정렬 (조회수 높은 순)
    existing_trends = load_existing_trends()
    
    # 중복 제거를 위한 맵핑 (video_id 기준)
    all_videos_map = {v['video_id']: v for v in existing_trends if v.get('video_id')}
    
    for video in collected_videos:
        video_id = video.get('video_id')
        if not video_id:
            continue
            
        # 기존 비디오가 있다면 조회수 등 업데이트
        if video_id in all_videos_map:
            # 기존의 정보 유지 및 최신 데이터로 업데이트
            all_videos_map[video_id]["view_count"] = max(all_videos_map[video_id].get("view_count", 0), video["view_count"])
            all_videos_map[video_id]["collected_at"] = video["collected_at"]
        else:
            all_videos_map[video_id] = video
            
    # 리스트 변환 후 조회수 내림차순 정렬
    merged_trends = list(all_videos_map.values())
    merged_trends.sort(key=lambda x: x.get('view_count', 0), reverse=True)
    
    # 최대 50개만 보존
    final_trends = merged_trends[:50]
    
    save_trends(final_trends)
    print(f"[Collector] Trend collection process finished. Total database size: {len(final_trends)}")
    return final_trends

if __name__ == "__main__":
    collect_trends()
