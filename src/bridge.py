import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from moviepy import VideoFileClip, AudioFileClip

def get_media_duration(file_path, is_video=True):
    """비디오 또는 오디오 파일의 길이를 MoviePy를 사용하여 초 단위로 정확히 가져옵니다."""
    try:
        if is_video:
            clip = VideoFileClip(file_path)
            duration = clip.duration
            clip.close()
        else:
            clip = AudioFileClip(file_path)
            duration = clip.duration
            clip.close()
        return duration
    except Exception as e:
        print(f"[Bridge] Warning: Could not get duration for {os.path.basename(file_path)}. Fallback to 5.0 seconds. Error: {e}")
        return 5.0

def filepath_to_url(abs_path):
    """로컬 파일의 절대 경로를 FCP 7 XML에서 요구하는 표준 로컬 URL로 변환합니다."""
    # 윈도우 경로의 역슬래시를 슬래시로 변경하고 드라이브 문자를 포맷팅
    normalized = abs_path.replace('\\', '/')
    if not normalized.startswith('/'):
        normalized = '/' + normalized
    return f"file://{normalized}"

def create_fcp_xml(video_cuts, tts_voices, output_xml_path, fps=30):
    """비디오 컷 클립과 매칭되는 TTS 나레이션 음성 파일들을 정밀하게 배치한 Final Cut Pro 7 XML을 동적으로 생성합니다."""
    print("[Bridge] Initiating Final Cut Pro 7 XML generator...")
    
    # 1. XML 기본 뼈대 노드 구축
    xmeml = ET.Element("xmeml", version="5")
    sequence = ET.SubElement(xmeml, "sequence", id="sequence-1")
    
    ET.SubElement(sequence, "name").text = "Dopamine Explorer Shorts Timeline"
    
    # 레이트(Rate) 설정 노드
    rate = ET.SubElement(sequence, "rate")
    ET.SubElement(rate, "timebase").text = str(fps)
    ET.SubElement(rate, "ntsc").text = "TRUE"
    
    media = ET.SubElement(sequence, "media")
    video = ET.SubElement(media, "video")
    video_track = ET.SubElement(video, "track")
    
    audio = ET.SubElement(media, "audio")
    audio_track = ET.SubElement(audio, "track")
    
    current_frame = 0
    
    # 2. 비디오 클립과 TTS 클립을 루프 돌며 동기 배치
    for idx in range(max(len(video_cuts), len(tts_voices))):
        clip_id_str = f"clip-{idx + 1}"
        audio_id_str = f"audio-{idx + 1}"
        
        # 기본 파일 경로 확보
        video_path = video_cuts[idx] if idx < len(video_cuts) else None
        audio_path = tts_voices[idx] if idx < len(tts_voices) else None
        
        # 파일 길이 정밀 측정
        v_duration = get_media_duration(video_path, is_video=True) if video_path else 0.0
        a_duration = get_media_duration(audio_path, is_video=False) if audio_path else 0.0
        
        # [스마트 싱크] 오디오(대사)가 잘리지 않도록 비디오 컷과 오디오 중 더 긴 쪽에 구간 타임라인 길이를 맞춰 배치
        actual_duration = max(v_duration, a_duration)
        if actual_duration == 0.0:
            continue
            
        clip_frames = int(actual_duration * fps)
        v_clip_frames = int(v_duration * fps) if video_path else 0
        a_clip_frames = int(a_duration * fps) if audio_path else 0
        
        start_frame = current_frame
        end_frame = current_frame + clip_frames
        
        # 비디오 클립 추가
        if video_path:
            clipitem = ET.SubElement(video_track, "clipitem", id=clip_id_str)
            ET.SubElement(clipitem, "name").text = os.path.basename(video_path)
            # FCP XML에서는 각 클립 본연의 총 프레임 길이를 duration으로 설정
            ET.SubElement(clipitem, "duration").text = str(v_clip_frames)
            
            # 클립의 Rate 정보
            c_rate = ET.SubElement(clipitem, "rate")
            ET.SubElement(c_rate, "timebase").text = str(fps)
            ET.SubElement(c_rate, "ntsc").text = "TRUE"
            
            # 비디오 소스 편집점 지정 (0부터 소스 비디오 길이만큼 끝까지 재생)
            ET.SubElement(clipitem, "in").text = "0"
            ET.SubElement(clipitem, "out").text = str(v_clip_frames)
            
            # 타임라인 배치 구간 지정
            ET.SubElement(clipitem, "start").text = str(start_frame)
            ET.SubElement(clipitem, "end").text = str(start_frame + v_clip_frames) # 만약 오디오가 더 길다면 비디오가 멈춘 채 대기하도록 FCPXML 속성을 고려할 수도 있지만, 우선은 단순 컷배치로 지정
            
            # 파일 절대경로 리소스 세부정보 등록
            file_node = ET.SubElement(clipitem, "file", id=f"file-v-{idx + 1}")
            ET.SubElement(file_node, "name").text = os.path.basename(video_path)
            ET.SubElement(file_node, "pathurl").text = filepath_to_url(video_path)
            
            # 파일 본래의 rate 등록
            f_rate = ET.SubElement(file_node, "rate")
            ET.SubElement(f_rate, "timebase").text = str(fps)
            ET.SubElement(f_rate, "ntsc").text = "TRUE"

        # 오디오 클립 추가
        if audio_path:
            audio_clipitem = ET.SubElement(audio_track, "clipitem", id=audio_id_str)
            ET.SubElement(audio_clipitem, "name").text = os.path.basename(audio_path)
            ET.SubElement(audio_clipitem, "duration").text = str(a_clip_frames)
            
            a_rate = ET.SubElement(audio_clipitem, "rate")
            ET.SubElement(a_rate, "timebase").text = str(fps)
            ET.SubElement(a_rate, "ntsc").text = "TRUE"
            
            ET.SubElement(audio_clipitem, "in").text = "0"
            ET.SubElement(audio_clipitem, "out").text = str(a_clip_frames)
            
            # 오디오도 똑같이 start_frame에서 시작하여 오디오 본래 길이만큼 배치
            ET.SubElement(audio_clipitem, "start").text = str(start_frame)
            ET.SubElement(audio_clipitem, "end").text = str(start_frame + a_clip_frames)
            
            file_node_a = ET.SubElement(audio_clipitem, "file", id=f"file-a-{idx + 1}")
            ET.SubElement(file_node_a, "name").text = os.path.basename(audio_path)
            ET.SubElement(file_node_a, "pathurl").text = filepath_to_url(audio_path)
            
            f_rate_a = ET.SubElement(file_node_a, "rate")
            ET.SubElement(f_rate_a, "timebase").text = str(fps)
            ET.SubElement(f_rate_a, "ntsc").text = "TRUE"
            
        # 다음 구간 배치를 위해 누적 프레임 인덱스 갱신 (더 긴 쪽 프레임 기준)
        current_frame += clip_frames
        
    # 시퀀스 총 듀레이션 정보 업데이트
    ET.SubElement(sequence, "duration").text = str(current_frame)
    
    # 3. 예쁘게 포맷팅된 XML 쓰기
    xml_str = ET.tostring(xmeml, encoding="utf-8")
    parsed_xml = minidom.parseString(xml_str)
    pretty_xml_str = parsed_xml.toprettyxml(indent="  ", encoding="utf-8")
    
    try:
        with open(output_xml_path, 'wb') as f:
            f.write(pretty_xml_str)
        print(f"[Bridge] CapCut FCP 7 XML created successfully -> {output_xml_path}")
    except Exception as e:
        print(f"[Bridge] Error writing XML file: {e}")
        raise e

def create_subtitles_srt(selected_scenes, video_cuts, tts_voices, output_srt_path, fps=30):
    """자막 텍스트와 실제 배치되는 파일들의 길이를 기반으로 싱크가 맞는 .srt 파일을 생성합니다."""
    print("[Bridge] Generating synchronized SRT subtitle file...")
    
    srt_lines = []
    current_time_sec = 0.0
    
    for idx, scene in enumerate(selected_scenes):
        video_path = video_cuts[idx] if idx < len(video_cuts) else None
        audio_path = tts_voices[idx] if idx < len(tts_voices) else None
        
        v_duration = get_media_duration(video_path, is_video=True) if video_path else 0.0
        a_duration = get_media_duration(audio_path, is_video=False) if audio_path else 0.0
        
        actual_duration = max(v_duration, a_duration)
        if actual_duration == 0.0:
            continue
            
        start_time = current_time_sec
        end_time = current_time_sec + actual_duration
        
        # SRT 타임코드 포맷팅: HH:MM:SS,mmm
        def format_srt_time(seconds):
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = int(seconds % 60)
            ms = int((seconds - int(seconds)) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            
        start_str = format_srt_time(start_time)
        end_str = format_srt_time(end_time)
        
        caption = scene.get("caption", "")
        
        srt_lines.append(f"{idx + 1}")
        srt_lines.append(f"{start_str} --> {end_str}")
        srt_lines.append(caption)
        srt_lines.append("") # 빈 줄
        
        current_time_sec += actual_duration
        
    try:
        with open(output_srt_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(srt_lines))
        print(f"[Bridge] SRT subtitles created successfully -> {output_srt_path}")
    except Exception as e:
        print(f"[Bridge] Error writing SRT file: {e}")

if __name__ == "__main__":
    # 목킹 테스트용 예시
    # create_fcp_xml(["cut_1.mp4"], ["voice_1.mp3"], "test.xml")
    pass
