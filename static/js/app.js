document.addEventListener('DOMContentLoaded', () => {
  // UI 요소 참조
  const searchInput = document.getElementById('search-input');
  const searchPeriod = document.getElementById('search-period');
  const searchBtn = document.getElementById('search-btn');
  const videoGridContainer = document.getElementById('video-grid-container');
  const consoleTerminal = document.getElementById('console-terminal');
  const btnTriggerAction = document.getElementById('btn-trigger-action');
  
  // 모달 요소 참조
  const btnSettings = document.getElementById('btn-settings');
  const settingsModal = document.getElementById('settings-modal');
  const btnModalClose = document.getElementById('btn-modal-close');
  const btnSettingsSave = document.getElementById('btn-settings-save');
  const inputGithubToken = document.getElementById('input-github-token');
  const inputGeminiKey = document.getElementById('input-gemini-key');
  const inputRepoOwner = document.getElementById('input-repo-owner');
  const inputRepoName = document.getElementById('input-repo-name');

  let selectedVideoUrl = "";
  let selectedVideoTitle = "";
  let statusPollingInterval = null;

  // 1. 연동 키 설정 모달 제어
  btnSettings.addEventListener('click', () => {
    // 저장된 기존 설정 로드
    inputGithubToken.value = localStorage.getItem('github_token') || "";
    inputGeminiKey.value = localStorage.getItem('gemini_api_key') || "";
    inputRepoOwner.value = localStorage.getItem('repo_owner') || "GoldSH69";
    inputRepoName.value = localStorage.getItem('repo_name') || "DE";
    
    settingsModal.style.display = 'flex';
  });

  btnModalClose.addEventListener('click', () => {
    settingsModal.style.display = 'none';
  });

  btnSettingsSave.addEventListener('click', () => {
    const token = inputGithubToken.value.trim();
    const gemini = inputGeminiKey.value.trim();
    const owner = inputRepoOwner.value.trim();
    const name = inputRepoName.value.trim();

    if (!token) {
      alert("GitHub Token은 API 연동 구동을 위한 필수 값입니다.");
      return;
    }

    localStorage.setItem('github_token', token);
    localStorage.setItem('gemini_api_key', gemini);
    localStorage.setItem('repo_owner', owner);
    localStorage.setItem('repo_name', name);

    settingsModal.style.display = 'none';
    alert("🔑 연동 설정이 로컬 스토리지에 안전하게 저장되었습니다.");
  });

  // 2. 유튜브 기간 필터 검색
  searchBtn.addEventListener('click', executeSearch);
  searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') executeSearch();
  });

  async function executeSearch() {
    const query = searchInput.value.trim();
    const period = searchPeriod.value;

    if (!query) {
      alert("스캔할 예능 키워드를 입력해 주세요.");
      return;
    }

    // 검색 로딩 UI 시동
    searchBtn.disabled = true;
    searchBtn.innerHTML = '<span class="spinner"></span> 스캔 중...';
    videoGridContainer.innerHTML = `
      <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
        <span class="spinner" style="border-top-color: var(--color-point); width: 30px; height: 30px; margin-bottom: 12px;"></span>
        <p style="font-family: var(--font-title); font-weight: 600; color: var(--color-point);">지정된 기간 내 핫한 유튜브 예능 검색 수집 중...</p>
      </div>
    `;

    // 타겟 비디오 선택 정보 초기화
    selectedVideoUrl = "";
    selectedVideoTitle = "";
    btnTriggerAction.disabled = true;

    try {
      const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query, period: period })
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "검색 실패");

      renderVideoCards(data.results);
    } catch (err) {
      alert(`소재 검색 실패: ${err.message}`);
      videoGridContainer.innerHTML = `
        <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
          <i class="fa-solid fa-triangle-exclamation" style="font-size: 2.5rem; color: #c62828; margin-bottom: 12px;"></i>
          <p style="color: #c62828; font-weight: 600;">실시간 스캔 실패: ${err.message}</p>
        </div>
      `;
    } finally {
      searchBtn.disabled = false;
      searchBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 소재 스캔하기';
    }
  }

  // 3. 비디오 카드 렌더링 및 팝업/선택 분리 바인딩
  function renderVideoCards(videos) {
    if (!videos || videos.length === 0) {
      videoGridContainer.innerHTML = `
        <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
          <i class="fa-solid fa-face-frown" style="font-size: 2.5rem; color: var(--color-border); margin-bottom: 12px;"></i>
          <p style="font-family: var(--font-title); font-weight: 600; color: var(--color-sub);">지정된 기간 내의 후보 동영상을 찾지 못했습니다.</p>
        </div>
      `;
      return;
    }

    videoGridContainer.innerHTML = "";
    videos.forEach((video, index) => {
      const card = document.createElement('div');
      card.className = 'video-card';
      card.setAttribute('data-url', video.url);
      card.setAttribute('data-title', video.title);
      
      const videoId = video.video_id;
      const thumbnailSrc = videoId ? `https://img.youtube.com/vi/${videoId}/mqdefault.jpg` : 'https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?auto=format&fit=crop&w=400&q=80';
      const durationText = video.duration ? formatDuration(video.duration) : "LONG";

      card.innerHTML = `
        <!-- 원본 유튜브 새창 확인 앵커 링크 -->
        <a href="${video.url}" target="_blank" class="video-thumbnail-container" title="클릭 시 새 창에서 원본 유튜브 확인">
          <img src="${thumbnailSrc}" class="video-thumbnail" alt="${escapeHtml(video.title)}">
          <span class="video-duration">${durationText}</span>
          <span style="position: absolute; top: 8px; left: 8px; background-color: rgba(139,107,61,0.9); color: #fff; padding: 2px 6px; font-size: 0.7rem; font-weight: bold; border-radius: 4px;">
            <i class="fa-solid fa-square-arrow-up-right"></i> 새 창에서 보기
          </span>
        </a>
        <div class="video-info">
          <!-- 비디오 제목 앵커 링크 -->
          <a href="${video.url}" target="_blank" class="video-title" style="text-decoration: none; display: block;" title="새 창에서 원본 확인">${escapeHtml(video.title)}</a>
          <div class="video-meta">
            <span class="video-views"><i class="fa-solid fa-eye"></i> ${formatViews(video.view_count)}</span>
            <span class="video-date"><i class="fa-solid fa-calendar-days"></i> ${formatDate(video.published_date)}</span>
          </div>
          <button class="btn-card-action" style="margin-top: 14px;">
            <i class="fa-solid fa-circle-check"></i> 이 영상 제작 대상으로 선택
          </button>
        </div>
      `;

      // 비디오 제작 대상 카드 선택 인터랙션
      card.addEventListener('click', (e) => {
        // 만약 썸네일이나 제목 앵커 태그(새 창 열기)를 누른 경우 카드가 강제 선택되지 않게 앵커 이벤트는 패스
        if (e.target.closest('a')) return;
        
        // 전체 카드 하이라이트 클래스 제거
        document.querySelectorAll('.video-card').forEach(c => {
          c.classList.remove('selected-active');
          c.querySelector('.btn-card-action').innerHTML = '<i class="fa-solid fa-circle-check"></i> 이 영상 제작 대상으로 선택';
          c.querySelector('.btn-card-action').style.backgroundColor = 'var(--color-bg)';
          c.querySelector('.btn-card-action').style.color = 'var(--color-point)';
        });

        // 현재 카드 선택 활성화
        card.classList.add('selected-active');
        selectedVideoUrl = video.url;
        selectedVideoTitle = video.title;
        
        const actBtn = card.querySelector('.btn-card-action');
        actBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> 제작 대상 선택 완료!';
        actBtn.style.backgroundColor = 'var(--color-point)';
        actBtn.style.color = '#ffffff';

        // 제작 기동 버튼 활성화
        btnTriggerAction.disabled = false;
        
        appendTerminalLine(`🎯 제작 타겟 확정: [${video.title}]`);
      });

      videoGridContainer.appendChild(card);
    });
  }

  // 4. GitHub Actions 원격 빌드 기동
  btnTriggerAction.addEventListener('click', async () => {
    const token = localStorage.getItem('github_token');
    const owner = localStorage.getItem('repo_owner') || "GoldSH69";
    const name = localStorage.getItem('repo_name') || "DE";
    const gemini = localStorage.getItem('gemini_api_key') || "";

    if (!token) {
      alert("GitHub API 연동 토큰이 없습니다. 우측 상단 [연동 키 설정] 버튼을 클릭해 설정해 주세요.");
      settingsModal.style.display = 'flex';
      return;
    }

    if (!selectedVideoUrl) {
      alert("제작할 동영상 대상을 왼쪽 목록에서 선택해 주세요.");
      return;
    }

    // UI 잠금 및 로딩 개시
    btnTriggerAction.disabled = true;
    btnTriggerAction.innerHTML = '<span class="spinner"></span> GitHub Actions 클라우드 컴퓨터 시동 중...';
    consoleTerminal.innerHTML = "";
    appendTerminalLine("🚀 1단계: 깃허브 서버로 원격 가공 신호 전송 중...", "success");

    try {
      const response = await fetch('/api/trigger_actions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_url: selectedVideoUrl,
          github_token: token,
          gemini_api_key: gemini,
          repo_owner: owner,
          repo_name: name
        })
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Actions 기동 실패");

      appendTerminalLine(`✅ ${data.message}`, "success");
      appendTerminalLine("📡 2단계: 깃허브 가상 러너 상태 실시간 추적 스캔 돌입 (5초 주기로 스캔)...", "success");
      
      // 5초 간격으로 깃허브 액션 원격 빌드 진척률 감시 개시 (Polling)
      startStatusPolling(token, owner, name);

    } catch (err) {
      appendTerminalLine(`❌ 기동 실패: ${err.message}`, "error");
      btnTriggerAction.disabled = false;
      btnTriggerAction.innerHTML = '<i class="fa-solid fa-rocket"></i> 쇼츠 자동화 제작 기동 (GitHub Actions)';
    }
  });

  // 5. 깃허브 Actions Runs 목록 주기적 스캔 (폴링)
  function startStatusPolling(token, owner, name) {
    if (statusPollingInterval) clearInterval(statusPollingInterval);
    
    let dots = "";
    statusPollingInterval = setInterval(async () => {
      dots = dots.length >= 3 ? "" : dots + ".";
      try {
        const response = await fetch('/api/check_status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            github_token: token,
            repo_owner: owner,
            repo_name: name
          })
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "상태 조회 오류");

        const status = data.status;
        const conclusion = data.conclusion;

        if (status === 'queued') {
          appendTerminalLine(`⏳ [원격 주방 대기열] 깃허브 가상 서버 배정 대기 중${dots}`);
        } else if (status === 'in_progress') {
          appendTerminalLine(`⚙️ [원격 빌드 구동 중] 기가비트망 동영상 다운로드, 컷 편집 및 edge-tts 합성 처리 중${dots}`);
        } else if (status === 'completed') {
          clearInterval(statusPollingInterval);
          statusPollingInterval = null;

          if (conclusion === 'success') {
            appendTerminalLine("==================================================", "success");
            appendTerminalLine("🎉 [GitHub Actions 빌드 성공] 쇼츠 자동 컷팅 가공이 100% 완료되었습니다!", "success");
            appendTerminalLine("📦 1일 한정 깃허브 보관함에 아티팩트 ZIP 아카이브가 성공적으로 업로드되었습니다.", "success");
            appendTerminalLine("==================================================", "success");
            
            // 터미널 하단에 ZIP 다운로드 버튼 동적 렌더링 주입
            renderZipDownloadButton(data.download_url);
          } else {
            appendTerminalLine(`❌ [GitHub Actions 실패] 빌드가 실패로 완료되었습니다 (결과: ${conclusion}). 깃허브 Actions 탭에서 세부 로그를 검사해 주세요.`, "error");
            resetTriggerButton();
          }
        }
      } catch (err) {
        appendTerminalLine(`⚠️ 상태 스캔 경고: ${err.message}`);
      }
    }, 5000); // 5초 간격
  }

  // 성공 완료 시 터미널 액션 영역에 ZIP 다운로드 원클릭 버튼을 매끄럽게 교체 렌더링
  function renderZipDownloadButton(downloadUrl) {
    const parent = btnTriggerAction.parentElement;
    parent.innerHTML = `
      <a href="${downloadUrl}" target="_blank" class="btn-control btn-save-local" style="height: 52px; font-size: 1.05rem; text-decoration: none; display: flex; justify-content: center; align-items: center; gap: 8px;">
        <i class="fa-solid fa-file-zipper"></i> 완성본 ZIP 압축 아카이브 다운로드
      </a>
      <button id="btn-restart-studio" class="btn-control btn-download-zip" style="height: 52px; font-size: 0.95rem; margin-top: 12px;">
        <i class="fa-solid fa-rotate-left"></i> 새 영상 제작 시작하기
      </button>
    `;

    document.getElementById('btn-restart-studio').addEventListener('click', () => {
      window.location.reload();
    });
  }

  function resetTriggerButton() {
    btnTriggerAction.disabled = false;
    btnTriggerAction.innerHTML = '<i class="fa-solid fa-rocket"></i> 쇼츠 자동화 제작 기동 (GitHub Actions)';
  }

  // 6. 데이터 유틸리티들
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
