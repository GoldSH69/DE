document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('search-input');
  const searchBtn = document.getElementById('search-btn');
  const videoGridContainer = document.getElementById('video-grid-container');
  const consoleTerminal = document.getElementById('console-terminal');
  const btnSaveLocal = document.getElementById('btn-save-local');
  const btnDownloadZip = document.getElementById('btn-download-zip');

  let activeEventSource = null;
  let currentXmlPath = "";

  // 1. 유튜브 키워드 검색 처리
  searchBtn.addEventListener('click', executeSearch);
  searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') executeSearch();
  });

  async function executeSearch() {
    const query = searchInput.value.trim();
    if (!query) {
      alert("스캔할 예능 키워드를 입력해 주세요.");
      return;
    }

    // 로딩 UI 설정
    searchBtn.disabled = true;
    searchBtn.innerHTML = '<span class="spinner"></span> 스캔 중...';
    videoGridContainer.innerHTML = `
      <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
        <span class="spinner" style="border-top-color: var(--color-point); width: 30px; height: 30px; margin-bottom: 12px;"></span>
        <p style="font-family: var(--font-title); font-weight: 600; color: var(--color-point);">YouTube 전역 실시간 예능 소재 탐색 중...</p>
      </div>
    `;

    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query })
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "검색 실패");

      renderVideoCards(data.results);
    } catch (err) {
      alert(`소재 검색 실패: ${err.message}`);
      videoGridContainer.innerHTML = `
        <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
          <i class="fa-solid fa-triangle-exclamation" style="font-size: 2.5rem; color: #c62828; margin-bottom: 12px;"></i>
          <p style="color: #c62828; font-weight: 600;">실시간 탐색 실패: ${err.message}</p>
        </div>
      `;
    } finally {
      searchBtn.disabled = false;
      searchBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 소재 스캔하기';
    }
  }

  // 2. 비디오 결과 카드 렌더링
  function renderVideoCards(videos) {
    if (!videos || videos.length === 0) {
      videoGridContainer.innerHTML = `
        <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
          <i class="fa-solid fa-face-frown" style="font-size: 2.5rem; color: var(--color-border); margin-bottom: 12px;"></i>
          <p style="font-family: var(--font-title); font-weight: 600; color: var(--color-sub);">검색 조건에 맞는 동영상을 찾지 못했습니다. 다른 검색어로 시도해 보세요.</p>
        </div>
      `;
      return;
    }

    videoGridContainer.innerHTML = "";
    videos.forEach(video => {
      const card = document.createElement('div');
      card.className = 'video-card';
      
      // 유튜브 썸네일 이미지 확보 (없으면 유튜브 기본 이미지로 대체)
      const videoId = video.video_id;
      const thumbnailSrc = videoId ? `https://img.youtube.com/vi/${videoId}/mqdefault.jpg` : 'https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?auto=format&fit=crop&w=400&q=80';
      
      const durationText = video.duration ? formatDuration(video.duration) : "LONG";

      card.innerHTML = `
        <div class="video-thumbnail-container">
          <img src="${thumbnailSrc}" class="video-thumbnail" alt="${escapeHtml(video.title)}">
          <span class="video-duration">${durationText}</span>
        </div>
        <div class="video-info">
          <div class="video-title" title="${escapeHtml(video.title)}">${escapeHtml(video.title)}</div>
          <div class="video-meta">
            <span class="video-views"><i class="fa-solid fa-eye"></i> ${formatViews(video.view_count)}</span>
            <span class="video-date"><i class="fa-solid fa-calendar-days"></i> ${formatDate(video.published_date)}</span>
          </div>
          <button class="btn-card-action">
            <i class="fa-solid fa-scissors"></i> 쇼츠 자동화 제작하기
          </button>
        </div>
      `;

      // 카드 클릭 시 파이프라인 가동 연동
      card.addEventListener('click', () => {
        triggerShortsGeneration(video.url, video.title);
      });

      videoGridContainer.appendChild(card);
    });
  }

  // 3. 실시간 SSE 쇼츠 제작 기동
  function triggerShortsGeneration(videoUrl, title) {
    if (activeEventSource) {
      activeEventSource.close();
    }

    // 터미널 초기화 및 로딩 표시
    consoleTerminal.innerHTML = "";
    btnSaveLocal.disabled = true;
    btnDownloadZip.disabled = true;
    currentXmlPath = "";

    appendTerminalLine("⚙️ Dopamine Engine 준비 중...", "success");

    // SSE 커넥션 개시
    const sseUrl = `/api/stream_generate?video_url=${encodeURIComponent(videoUrl)}&title=${encodeURIComponent(title)}`;
    activeEventSource = new EventSource(sseUrl);

    activeEventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.status === 'progress') {
        appendTerminalLine(data.message);
      } else if (data.status === 'analysis') {
        renderGeminiAnalysis(data.data);
      } else if (data.status === 'complete') {
        appendTerminalLine(data.message, "success");
        appendTerminalLine(`📁 FCP 7 XML 파일이 생성되었습니다: ${data.xml_path}`, "success");
        currentXmlPath = data.xml_path;
        
        // 듀얼 제어 버튼 활성화
        btnSaveLocal.disabled = false;
        btnDownloadZip.disabled = false;
        
        activeEventSource.close();
        activeEventSource = null;
      } else if (data.status === 'error') {
        appendTerminalLine(`❌ 에러 발생: ${data.message}`, "error");
        activeEventSource.close();
        activeEventSource = null;
      }
    };

    activeEventSource.onerror = (err) => {
      appendTerminalLine("❌ 서버 통신 오류가 발생했습니다. 실시간 스트림 연결이 해제되었습니다.", "error");
      activeEventSource.close();
      activeEventSource = null;
    };
  }

  // 4. 터미널 출력 보조 함수
  function appendTerminalLine(text, className = "") {
    const placeholder = document.getElementById('terminal-placeholder');
    if (placeholder) placeholder.remove();

    const line = document.createElement('div');
    line.className = `terminal-line ${className}`;
    line.innerText = `[${new Date().toLocaleTimeString()}] ${text}`;
    
    consoleTerminal.appendChild(line);
    consoleTerminal.scrollTop = consoleTerminal.scrollHeight;
  }

  // Gemini 기획 결과를 터미널 안에 깔끔하게 테이블 형식으로 출력
  function renderGeminiAnalysis(analysis) {
    appendTerminalLine("==================================================", "success");
    appendTerminalLine(`💡 Gemini AI 쇼츠 기획안 수집 완료`, "success");
    appendTerminalLine(`기획 사유: ${analysis.rationale}`);
    appendTerminalLine(`총 분량: ${analysis.total_duration_seconds}초`, "success");
    appendTerminalLine("--------------------------------------------------");
    
    analysis.selected_scenes.forEach((scene, i) => {
      appendTerminalLine(`  🎬 씬 ${i + 1} [${scene.start_time} ~ ${scene.end_time}]`);
      appendTerminalLine(`    - 나레이션(JA): ${scene.tts_text}`);
      appendTerminalLine(`    - 한글자막(KO): ${scene.caption}`);
    });
    appendTerminalLine("==================================================", "success");
  }

  // 5. 듀얼 제어 버튼 액션 핸들러
  
  // 1번 버튼: 로컬 폴더 직접 저장 연동 (클립보드 복사 헬퍼 기능 포함)
  btnSaveLocal.addEventListener('click', () => {
    if (!currentXmlPath) return;
    
    // 파일 경로를 클립보드에 복사해 줌으로써 사용자가 캡컷에서 복사-붙여넣기로 즉각 임포트하도록 배려
    navigator.clipboard.writeText(currentXmlPath).then(() => {
      alert(`🎉 [로컬 저장 완료!]\n\nCapCut XML 파일이 내 컴퓨터에 이미 저장되어 있습니다.\n\n경로: ${currentXmlPath}\n\n(경로가 클립보드에 복사되었습니다! CapCut의 '가져오기' 창 주소창에 Ctrl+V 하시면 1초 만에 바로 가져오실 수 있습니다.)`);
    }).catch(err => {
      alert(`🎉 [로컬 저장 완료!]\n\nCapCut XML 파일이 내 컴퓨터에 이미 저장되어 있습니다.\n\n경로: ${currentXmlPath}`);
    });
  });

  // 2번 버튼: 브라우저 ZIP 다운로드 스트림 기동
  btnDownloadZip.addEventListener('click', () => {
    appendTerminalLine("📦 project 아웃풋 ZIP 압축 다운로드 준비 중...");
    window.location.href = '/api/download_project';
  });

  // 6. 데이터 포맷 유틸리티
  function formatDuration(sec) {
    if (!sec) return "00:00";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  function formatViews(views) {
    if (!views) return "0";
    if (views >= 100000000) {
      return `${(views / 100000000).toFixed(1)}억`;
    }
    if (views >= 10000) {
      return `${(views / 10000).toFixed(1)}만`;
    }
    return views.toLocaleString();
  }

  function formatDate(dateStr) {
    if (!dateStr || dateStr.length !== 8) return dateStr || "";
    // YYYYMMDD -> YYYY-MM-DD
    return `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
  }

  function escapeHtml(unsafe) {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
