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
    """yt-dlp를 사용하여 고화질 비디오를 100% 익명으로 다운로드합니다 (이미 존재하면 다운로드 건너뜀)."""
    ensure_directories()
    target_path = os.path.join(OUTPUT_DIR, output_filename)
    
    if os.path.exists(target_path) and os.path.getsize(target_path) > 1024 * 1024:
        print(f"[Processor] Found existing video: {target_path}. Skipping download.")
        return target_path

    print(f"[Processor] Downloading video from {video_url} anonymously...")
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

def cut_video_clips(origin_video_path, selected_scenes, video_cuts_dir=None):
    """원본 동영상 파일에서 지정된 타임라인 구간들을 MoviePy로 잘라냅니다."""
    if video_cuts_dir is None:
        video_cuts_dir = VIDEO_CUTS_DIR
        ensure_directories()
    else:
        os.makedirs(video_cuts_dir, exist_ok=True)
        
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
            
            output_clip_path = os.path.join(video_cuts_dir, f"cut_{idx + 1}.mp4")
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

async def generate_tts_voices(selected_scenes, voice="ja-JP-NanamiNeural", tts_voices_dir=None):
    """선택된 씬들의 일본어 대본(tts_text)을 edge-tts로 비동기 순차 합성합니다."""
    if tts_voices_dir is None:
        tts_voices_dir = TTS_VOICES_DIR
        ensure_directories()
    else:
        os.makedirs(tts_voices_dir, exist_ok=True)
        
    print(f"[Processor] Starting neural TTS synthesis ({voice}) with safety delay...")
    
    tts_files = []
    
    for idx, scene in enumerate(selected_scenes):
        tts_text = scene.get("tts_text")
        if not tts_text:
            print(f"[Processor] Warning: Empty tts_text for scene {idx + 1}. Skipping TTS.")
            continue
            
        output_voice_path = os.path.join(tts_voices_dir, f"voice_{idx + 1}.mp3")
        
        # 실제 합성 실행
        await synthesize_single_tts(tts_text, output_voice_path, voice)
        tts_files.append(output_voice_path)
        
        # 1초 안전 슬립 딜레이 (IP 임시 차단 원천 봉쇄)
        if idx < len(selected_scenes) - 1:
            await asyncio.sleep(0.8)
            
    print(f"[Processor] All {len(tts_files)} TTS voices synthesized successfully.")
    return tts_files

def run_processing_pipeline(video_url, selected_scenes, voice="ja-JP-NanamiNeural", project_dir=None):
    """동영상 다운로드, 컷 편집, TTS 합성을 총괄 실행하는 동기식 브릿지 래퍼 함수입니다."""
    from src.main import extract_youtube_video_id
    
    # 1. 비디오 다운로드 (루트 공통 캐싱 적용으로 대역폭 극적 보존)
    video_id = extract_youtube_video_id(video_url) or "video"
    video_filename = f"origin_{video_id}.mp4"
    origin_video_path = download_youtube_video(video_url, output_filename=video_filename)
    
    # 프로젝트 고유 경로 오버라이드 계산
    if project_dir:
        video_cuts_dir = os.path.join(project_dir, "video_cuts")
        tts_voices_dir = os.path.join(project_dir, "tts_voices")
    else:
        video_cuts_dir = VIDEO_CUTS_DIR
        tts_voices_dir = TTS_VOICES_DIR
        ensure_directories()
        
    # 2. 컷 편집
    cut_files = cut_video_clips(origin_video_path, selected_scenes, video_cuts_dir=video_cuts_dir)
    
    # 3. 비동기 TTS 실행 (동기 함수 내에서 비동기 이벤트 루프 구동)
    try:
        tts_files = asyncio.run(generate_tts_voices(selected_scenes, voice, tts_voices_dir=tts_voices_dir))
    except RuntimeError:
        # 이미 이벤트 루프가 작동 중인 특수 스레드/서버 환경 대처
        try:
            loop = asyncio.get_event_loop()
            tts_files = loop.run_until_complete(generate_tts_voices(selected_scenes, voice, tts_voices_dir=tts_voices_dir))
        except Exception as inner_e:
            print(f"[Processor] Event loop fallback failed: {inner_e}")
            raise inner_e
        
    return cut_files, tts_files

def merge_shorts_video(cut_files, tts_files, selected_scenes, output_merged_path, voice_delay=0.5):
    """MoviePy를 사용하여 자른 영상 클립들과 합성된 TTS 나레이션을 싱크에 맞춰 하나의 완성본 MP4 비디오로 합칩니다."""
    from moviepy import VideoFileClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
    import os
    
    print(f"[Processor] Merging {len(cut_files)} clips and {len(tts_files)} voices into a single short...")
    
    clips = []
    try:
        for idx in range(len(cut_files)):
            video_path = cut_files[idx]
            audio_path = tts_files[idx] if idx < len(tts_files) else None
            
            # 1. 비디오 클립 로드
            v_clip = VideoFileClip(video_path)
            v_dur = v_clip.duration
            
            # 2. 오디오 설정
            original_audio = v_clip.audio
            
            if audio_path and os.path.exists(audio_path):
                # 3. TTS 나레이션 오디오 로드
                tts_audio = AudioFileClip(audio_path)
                a_dur = tts_audio.duration
                
                # 첫 번째 조각인 경우 후킹을 위해 나레이션 목소리 시작을 voice_delay(0.5초) 만큼 딜레이
                if idx == 0:
                    if hasattr(tts_audio, 'with_start'):
                        delayed_tts = tts_audio.with_start(voice_delay)
                    else:
                        delayed_tts = tts_audio.set_start(voice_delay)
                    # 비디오 길이가 나레이션보다 짧으면 오디오가 잘리지 않도록 비디오 멈춤(정지화면) 대기 연장
                    actual_duration = max(v_dur, a_dur + voice_delay)
                else:
                    if hasattr(tts_audio, 'with_start'):
                        delayed_tts = tts_audio.with_start(0.0)
                    else:
                        delayed_tts = tts_audio.set_start(0.0)
                    actual_duration = max(v_dur, a_dur)
                
                # 오디오 채널 합성: 원본 영상 배경음(약간 줄임) + AI 성우 나레이션
                # 원본 음량은 예능 배경음 역할을 하도록 0.35배로 조율, 성우 목소리는 1.0배로 돋보이게 설정
                if original_audio:
                    if hasattr(original_audio, 'with_volume_scaled'):
                        background_audio = original_audio.with_volume_scaled(0.35)
                    elif hasattr(original_audio, 'multiply_volume'):
                        background_audio = original_audio.multiply_volume(0.35)
                    else:
                        background_audio = original_audio
                else:
                    background_audio = None
                
                audio_tracks = []
                if background_audio:
                    audio_tracks.append(background_audio)
                audio_tracks.append(delayed_tts)
                
                mixed_audio = CompositeAudioClip(audio_tracks)
                if hasattr(mixed_audio, 'with_duration'):
                    mixed_audio = mixed_audio.with_duration(actual_duration)
                else:
                    mixed_audio = mixed_audio.set_duration(actual_duration)
                
                # 비디오 길이가 나레이션보다 짧은 경우, 마지막 프레임 정지 상태로 영상 길이 연장
                if actual_duration > v_dur:
                    # 마지막 프레임을 정지 화면으로 연장
                    extended_v_clip = v_clip.with_duration(actual_duration) if hasattr(v_clip, 'with_duration') else v_clip.set_duration(actual_duration)
                    v_clip_final = extended_v_clip.with_audio(mixed_audio) if hasattr(extended_v_clip, 'with_audio') else extended_v_clip.set_audio(mixed_audio)
                else:
                    v_clip_final = v_clip.with_audio(mixed_audio) if hasattr(v_clip, 'with_audio') else v_clip.set_audio(mixed_audio)
            else:
                # TTS가 없거나 매칭 실패 시 원본 비디오 그대로 사용
                v_clip_final = v_clip
                
            clips.append(v_clip_final)
            
        # 4. 모든 시퀀스 클립들을 하나로 이어 붙이기
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # 5. 완성본 비디오를 고해상도 MP4 파일로 내보내기 (렌더링)
        final_clip.write_videofile(
            output_merged_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=os.path.join(os.path.dirname(output_merged_path), "temp-audio.m4a"),
            remove_temp=True,
            logger=None
        )
        
        # 리소스 해제
        final_clip.close()
        for c in clips:
            c.close()
            
        print(f"[Processor] Unified Shorts Video created successfully -> {output_merged_path}")
        return output_merged_path
        
    except Exception as e:
        print(f"[Processor] Failed to merge shorts video: {e}")
        import traceback
        traceback.print_exc()
        raise e

if __name__ == "__main__":
    pass
