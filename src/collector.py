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

def search_videos_by_keywords(keywords, limit_per_keyword=5, period="this_week"):
    """키워드 검색을 통해 특정 기간(하루, 1주, 한달) 동안의 고성과 영상을 수집 및 조회수 순 정렬합니다."""
    import urllib.parse
    videos = []
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
    }
    
    # 기간 필터 sp 값 매핑
    sp_value = ""
    if period == "today":
        sp_value = "EgIIAg%3D%3D"
    elif period == "this_week":
        sp_value = "EgQIATAB"
    elif period == "this_month":
        sp_value = "EgQIAhAB"
    elif period == "this_year":
        sp_value = "EgQIAxAB"
        
    for kw in keywords:
        if sp_value:
            # 기간 필터가 지정된 경우 YouTube 검색 결과 URL 조립
            encoded_kw = urllib.parse.quote(kw)
            search_query = f"https://www.youtube.com/results?search_query={encoded_kw}&sp={sp_value}"
        else:
            search_query = f"ytsearch{limit_per_keyword}:{kw}"
            
        print(f"[Collector] Live searching YouTube: {search_query}")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search_query, download=False)
                entries = info.get('entries', []) if info else []
                
                # 만약 기간 필터링된 결과가 0개라면, 필터를 해제하고 일반 검색으로 자동 폴백
                if not entries and sp_value:
                    print(f"[Collector] Strict period filter '{period}' returned 0 results. Falling back to general search for '{kw}'...")
                    fallback_query = f"ytsearch{limit_per_keyword}:{kw}"
                    info = ydl.extract_info(fallback_query, download=False)
                    entries = info.get('entries', []) if info else []
                
                # 지정된 수집 갯수 제한 적용
                entries = entries[:limit_per_keyword]
                
                for entry in entries:
                    if not entry:
                        continue
                    
                    duration = entry.get('duration')
                    if duration and duration < 120:  # 2분 미만은 쇼츠 소재로 부적합하므로 자동 필터링 스킵
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
                        "view_count": entry.get('view_count', 0) or 0,
                        "duration": duration,
                        "published_date": raw_date or datetime.now().strftime("%Y%m%d"),
                        "published_date_text": published_date_text,
                        "collected_at": datetime.now().isoformat()
                    })
        except Exception as e:
            print(f"[Collector] Error searching keyword '{kw}': {e}")
            
    # 전체 수집 후 조회수 높은 순으로 최종 내림차순 정렬
    videos.sort(key=lambda x: x.get('view_count', 0), reverse=True)
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
