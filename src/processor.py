import os
import re
import asyncio
import yt_dlp
from moviepy import VideoFileClip
import edge_tts

OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
VIDEO_CUTS_DIR = os.path.join(OUTPUT_DIR, "video_cuts")
TTS_VOICES_DIR = os.path.join(OUTPUT_DIR, "tts_voices")

def ensure_directories():
    """출력 디렉토리들이 존재하도록 보장합니다."""
    for directory in [OUTPUT_DIR, VIDEO_CUTS_DIR, TTS_VOICES_DIR]:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"[Processor] Created directory: {directory}")

def time_str_to_seconds(time_str):
    """'MM:SS' 또는 'HH:MM:SS' 형식의 타임코드를 초(seconds) 단위의 실수로 변환합니다."""
    parts = time_str.split(':')
    if len(parts) == 2:  # MM:SS
        return int(parts[0]) * 60 + float(parts[1])
    elif len(parts) == 3:  # HH:MM:SS
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    try:
        return float(time_str)
    except ValueError:
        raise ValueError(f"지원하지 않는 타임코드 형식입니다: {time_str}")

def download_youtube_video(video_url, output_filename="origin_video.mp4"):
    """yt-dlp를 사용하여 고화질 비디오를 다운로드합니다 (이미 존재하면 다운로드 건너뜀)."""
    ensure_directories()
    target_path = os.path.join(OUTPUT_DIR, output_filename)
    
    if os.path.exists(target_path) and os.path.getsize(target_path) > 1024 * 1024:
        print(f"[Processor] Found existing video: {target_path}. Skipping download.")
        return target_path

    print(f"[Processor] Downloading video from {video_url}...")
    # 비디오 포맷은 mp4 중 고화질 다운로드
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': target_path,
        'quiet': False,
        'merge_output_format': 'mp4',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        print(f"[Processor] Download completed: {target_path}")
        return target_path
    except Exception as e:
        print(f"[Processor] Error during downloading video: {e}")
        # 간혹 포맷 문제로 병합 실패할 시를 위한 일반 포맷 다운로드 폴백
        print("[Processor] Retrying with generic best format...")
        try:
            ydl_opts['format'] = 'best'
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            return target_path
        except Exception as retry_e:
            print(f"[Processor] Critical download failure: {retry_e}")
            raise retry_e

def cut_video_clips(origin_video_path, selected_scenes):
    """원본 동영상 파일에서 지정된 타임라인 구간들을 MoviePy로 잘라냅니다."""
    ensure_directories()
    print(f"[Processor] Opening original video: {origin_video_path}")
    
    cut_files = []
    
    # moviepy로 원본 영상 로드
    try:
        clip = VideoFileClip(origin_video_path)
        
        for idx, scene in enumerate(selected_scenes):
            start_str = scene.get("start_time")
            end_str = scene.get("end_time")
            
            start_sec = time_str_to_seconds(start_str)
            end_sec = time_str_to_seconds(end_str)
            
            output_clip_path = os.path.join(VIDEO_CUTS_DIR, f"cut_{idx + 1}.mp4")
            print(f"[Processor] Trimming clip {idx + 1}: {start_str} ({start_sec}s) ~ {end_str} ({end_sec}s)...")
            
            # MoviePy 2.x와 1.x 하위 호환 처리
            if hasattr(clip, "subclipped"):
                sub_clip = clip.subclipped(start_sec, end_sec)
            else:
                # MoviePy 1.x 구 문법
                sub_clip = clip.subclip(start_sec, end_sec)
                
            # 오디오 포함하여 저장 (임시 파일 제거 옵션 탑재)
            sub_clip.write_videofile(
                output_clip_path,
                codec="libx264",
                audio_codec="aac",
                logger=None  # 복잡한 로그 미출력
            )
            print(f"[Processor] Saved trimmed clip: {output_clip_path}")
            cut_files.append(output_clip_path)
            
        clip.close()
    except Exception as e:
        print(f"[Processor] Error during video cutting: {e}")
        raise e
        
    return cut_files

async def synthesize_single_tts(text, output_path, voice="ja-JP-NanamiNeural"):
    """단일 텍스트를 edge-tts를 통해 mp3 파일로 합성합니다."""
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        print(f"[Processor] Synthesized TTS -> {output_path} ({len(text)} chars)")
    except Exception as e:
        print(f"[Processor] TTS Synthesis failed for '{text[:15]}...': {e}")
        raise e

async def generate_tts_voices(selected_scenes, voice="ja-JP-NanamiNeural"):
    """선택된 씬들의 일본어 대본(tts_text)을 edge-tts로 비동기 순차 합성합니다."""
    ensure_directories()
    print(f"[Processor] Starting neural TTS synthesis ({voice}) with safety delay...")
    
    tts_files = []
    
    for idx, scene in enumerate(selected_scenes):
        tts_text = scene.get("tts_text")
        if not tts_text:
            print(f"[Processor] Warning: Empty tts_text for scene {idx + 1}. Skipping TTS.")
            continue
            
        output_voice_path = os.path.join(TTS_VOICES_DIR, f"voice_{idx + 1}.mp3")
        
        # 실제 합성 실행
        await synthesize_single_tts(tts_text, output_voice_path, voice)
        tts_files.append(output_voice_path)
        
        # 1초 안전 슬립 딜레이 (IP 임시 차단 원천 봉쇄)
        if idx < len(selected_scenes) - 1:
            await asyncio.sleep(0.8)
            
    print(f"[Processor] All {len(tts_files)} TTS voices synthesized successfully.")
    return tts_files

def run_processing_pipeline(video_url, selected_scenes, voice="ja-JP-NanamiNeural"):
    """동영상 다운로드, 컷 편집, TTS 합성을 총괄 실행하는 동기식 브릿지 래퍼 함수입니다."""
    # 1. 비디오 다운로드
    video_filename = f"origin_{selected_scenes[0].get('start_time').replace(':', '')}.mp4" if selected_scenes else "origin_video.mp4"
    origin_video_path = download_youtube_video(video_url, output_filename=video_filename)
    
    # 2. 컷 편집
    cut_files = cut_video_clips(origin_video_path, selected_scenes)
    
    # 3. 비동기 TTS 실행 (동기 함수 내에서 비동기 이벤트 루프 구동)
    try:
        tts_files = asyncio.run(generate_tts_voices(selected_scenes, voice))
    except RuntimeError:
        # 이미 이벤트 루프가 작동 중인 특수 스레드/서버 환경 대처
        try:
            loop = asyncio.get_event_loop()
            tts_files = loop.run_until_complete(generate_tts_voices(selected_scenes, voice))
        except Exception as inner_e:
            print(f"[Processor] Event loop fallback failed: {inner_e}")
            raise inner_e
        
    return cut_files, tts_files

if __name__ == "__main__":
    # 간단한 작동 모듈 테스트
    test_scenes = [
        {"start_time": "00:05", "end_time": "00:10", "tts_text": "こんにちは。テスト音声です。", "caption": "안녕하세요. 테스트 음성입니다."}
    ]
    # 실제 구동 테스트를 원하면 아래 주석 해제 후 실행
    # run_processing_pipeline("https://www.youtube.com/watch?v=dQw4w9WgXcQ", test_scenes)
    pass
