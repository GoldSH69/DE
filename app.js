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
    alert("🔑 연동 설정이 브라우저 로컬 저장소에 저장되었습니다.");
  });

  // 2. 무백엔드(Serverless) 유튜브 검색 파싱 연동
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

    searchBtn.disabled = true;
    searchBtn.innerHTML = '<span class="spinner"></span> 스캔 중...';
    videoGridContainer.innerHTML = `
      <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
        <span class="spinner" style="border-top-color: var(--color-point); width: 30px; height: 30px; margin-bottom: 12px;"></span>
        <p style="font-family: var(--font-title); font-weight: 600; color: var(--color-point);">CORS 프록시망 우회 실시간 유튜브 핫소재 탐색 중...</p>
      </div>
    `;

    selectedVideoUrl = "";
    selectedVideoTitle = "";
    btnTriggerAction.disabled = true;

    // 기간 검색어 믹싱
    let periodSuffix = "";
    if (period === "today") periodSuffix = " \"today\"";
    else if (period === "this_week") periodSuffix = " \"this week\"";
    else if (period === "this_month") periodSuffix = " \"this month\"";

    const targetUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(query + periodSuffix)}`;
    
    // 무료 공개 CORS 우회 프록시 활용 (Hugging Face / GitHub Pages 호환성 100%)
    const proxyUrl = `https://api.allorigins.win/get?url=${encodeURIComponent(targetUrl)}`;

    try {
      const response = await fetch(proxyUrl);
      if (!response.ok) throw new Error("네트워크 연결 실패");
      
      const data = await response.json();
      const html = data.contents;
      
      // 유튜브 InitialData JSON 영역 파싱 기법 (CORS 우회 100% 무설치 기법)
      const parsedVideos = parseYoutubeHtml(html);
      renderVideoCards(parsedVideos);

    } catch (err) {
      console.error(err);
      // 프록시 일시적 지연을 감안한 2차 무료 프록시 폴백
      console.log("[JS Parser] Primary proxy failed. Trying fallback proxy...");
      try {
        const fallbackProxy = `https://corsproxy.io/?${encodeURIComponent(targetUrl)}`;
        const response = await fetch(fallbackProxy);
        if (!response.ok) throw new Error("CORS 프록시 서버 무응답");
        const html = await response.text();
        const parsedVideos = parseYoutubeHtml(html);
        renderVideoCards(parsedVideos);
      } catch (fallbackErr) {
        alert(`유튜브 실시간 수집 실패: 공용 CORS 프록시 서버 혼잡. 잠시 후 다시 검색해 주세요. 에러: ${fallbackErr.message}`);
        videoGridContainer.innerHTML = `
          <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
            <i class="fa-solid fa-triangle-exclamation" style="font-size: 2.5rem; color: #c62828; margin-bottom: 12px;"></i>
            <p style="color: #c62828; font-weight: 600;">실시간 탐색 실패: 공용 프록시 혼잡</p>
          </div>
        `;
      }
    } finally {
      searchBtn.disabled = false;
      searchBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 소재 스캔하기';
    }
  }

  // 유튜브 HTML 소스코드에서 비디오 데이터 JSON 큐레이션 및 조회수 기준 정렬 파서
  function parseYoutubeHtml(html) {
    const videos = [];
    try {
      // ytInitialData 파싱 정규식
      const match = html.match(/ytInitialData\s*=\s*({.+?});/);
      if (match) {
        const jsonStr = match[1];
        const dataObj = JSON.parse(jsonStr);
        
        // 유튜브 검색 결과 렌더러 노드 추적
        const contents = dataObj.contents?.twoColumnSearchResultsRenderer?.primaryContents?.sectionListRenderer?.contents;
        if (contents) {
          const itemSection = contents.find(c => c.itemSectionRenderer);
          const list = itemSection?.itemSectionRenderer?.contents || [];
          
          for (const item of list) {
            const videoRenderer = item.videoRenderer;
            if (!videoRenderer) continue;
            
            const videoId = videoRenderer.videoId;
            const title = videoRenderer.title?.runs?.[0]?.text || "알 수 없는 비디오";
            
            // 조회수 문자열 정수 가공 파싱
            const viewsText = videoRenderer.viewCountText?.simpleText || "";
            const viewCount = parseViewText(viewsText);
            
            // 듀레이션 정보 파싱
            const durationText = videoRenderer.lengthText?.simpleText || "";
            const durationSec = parseDurationText(durationText);
            
            // 숏츠 및 2분 미만 쇼츠 대상 부적합 영상은 자동 필터링 스킵
            if (durationSec > 0 && durationSec < 120) continue;

            const uploadText = videoRenderer.publishedTimeText?.simpleText || "최근";

            videos.push({
              video_id: videoId,
              title: title,
              url: `https://www.youtube.com/watch?v=${videoId}`,
              view_count: viewCount,
              duration: durationSec,
              published_date_text: uploadText,
              published_date: "20260530", // 모킹 일자
              collected_at: new Date().toISOString()
            });
          }
        }
      }
    } catch (e) {
      console.error("[JS Parser] JSON parsing error, fallback to legacy regex: ", e);
    }
    
    // 최종 조회수 기준 내림차순 정렬
    videos.sort((a, b) => b.view_count - a.view_count);
    return videos.slice(0, 8); // 상위 8개 정제
  }

  function parseViewText(text) {
    if (!text) return 0;
    // 예: "조회수 1.5만회", "1,500 views", "1.5M views", "조회수 120만회"
    let num = 0;
    const cleanText = text.replace(/,/g, '');
    const numMatch = cleanText.match(/([0-9\.]+)/);
    if (!numMatch) return 0;
    
    num = parseFloat(numMatch[1]);
    if (cleanText.includes('만')) {
      num *= 10000;
    } else if (cleanText.includes('억')) {
      num *= 100000000;
    } else if (cleanText.includes('K') || cleanText.includes('k')) {
      num *= 1000;
    } else if (cleanText.includes('M') || cleanText.includes('m')) {
      num *= 1000000;
    }
    return Math.floor(num);
  }

  function parseDurationText(text) {
    if (!text) return 0;
    const parts = text.split(':').map(Number);
    if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    } else if (parts.length === 3) {
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    }
    return 0;
  }

  // 3. 비디오 결과 카드 렌더링
  function renderVideoCards(videos) {
    if (!videos || videos.length === 0) {
      videoGridContainer.innerHTML = `
        <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
          <i class="fa-solid fa-face-frown" style="font-size: 2.5rem; color: var(--color-border); margin-bottom: 12px;"></i>
          <p style="font-family: var(--font-title); font-weight: 600; color: var(--color-sub);">지정된 기간 내의 비디오 카드를 찾지 못했습니다.</p>
        </div>
      `;
      return;
    }

    videoGridContainer.innerHTML = "";
    videos.forEach(video => {
      const card = document.createElement('div');
      card.className = 'video-card';
      card.setAttribute('data-url', video.url);
      card.setAttribute('data-title', video.title);
      
      const videoId = video.video_id;
      const thumbnailSrc = `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`;
      const durationText = formatDuration(video.duration);

      card.innerHTML = `
        <!-- 새 창으로 원본 확인용 링크 -->
        <a href="${video.url}" target="_blank" class="video-thumbnail-container" title="클릭 시 새 창에서 원본 유튜브 감상">
          <img src="${thumbnailSrc}" class="video-thumbnail" alt="${escapeHtml(video.title)}">
          <span class="video-duration">${durationText}</span>
          <span style="position: absolute; top: 8px; left: 8px; background-color: rgba(139,107,61,0.95); color: #fff; padding: 3px 7px; font-size: 0.72rem; font-weight: bold; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.15);">
            <i class="fa-solid fa-square-arrow-up-right"></i> 새 창에서 영상 확인
          </span>
        </a>
        <div class="video-info">
          <a href="${video.url}" target="_blank" class="video-title" style="text-decoration: none; display: block;" title="새 창에서 원본 확인">${escapeHtml(video.title)}</a>
          <div class="video-meta">
            <span class="video-views"><i class="fa-solid fa-eye"></i> ${formatViews(video.view_count)}</span>
            <span class="video-date"><i class="fa-solid fa-calendar-days"></i> ${video.published_date_text}</span>
          </div>
          <button class="btn-card-action" style="margin-top: 14px;">
            <i class="fa-solid fa-circle-check"></i> 이 영상 제작 대상으로 선택
          </button>
        </div>
      `;

      // 제작 타겟 카드 활성화 선택 이벤트
      card.addEventListener('click', (e) => {
        if (e.target.closest('a')) return;
        
        document.querySelectorAll('.video-card').forEach(c => {
          c.classList.remove('selected-active');
          c.querySelector('.btn-card-action').innerHTML = '<i class="fa-solid fa-circle-check"></i> 이 영상 제작 대상으로 선택';
          c.querySelector('.btn-card-action').style.backgroundColor = 'var(--color-bg)';
          c.querySelector('.btn-card-action').style.color = 'var(--color-point)';
        });

        card.classList.add('selected-active');
        selectedVideoUrl = video.url;
        selectedVideoTitle = video.title;
        
        const actBtn = card.querySelector('.btn-card-action');
        actBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> 제작 대상 선택 완료!';
        actBtn.style.backgroundColor = 'var(--color-point)';
        actBtn.style.color = '#ffffff';

        btnTriggerAction.disabled = false;
        appendTerminalLine(`🎯 제작 타겟 확정: [${video.title}]`);
      });

      videoGridContainer.appendChild(card);
    });
  }

  // 4. GitHub Actions API 다이렉트 트리거 기동 (브라우저 직접 API 송신)
  btnTriggerAction.addEventListener('click', async () => {
    const token = localStorage.getItem('github_token');
    const owner = localStorage.getItem('repo_owner') || "GoldSH69";
    const name = localStorage.getItem('repo_name') || "DE";
    const gemini = localStorage.getItem('gemini_api_key') || "";

    if (!token) {
      alert("GitHub API 토큰이 설정되지 않았습니다. 우측 상단 [연동 키 설정] 버튼을 클릭해 등록해 주세요.");
      settingsModal.style.display = 'flex';
      return;
    }

    if (!selectedVideoUrl) {
      alert("제작할 예능 대상 영상을 왼쪽 목록에서 먼저 선택해 주세요.");
      return;
    }

    btnTriggerAction.disabled = true;
    btnTriggerAction.innerHTML = '<span class="spinner"></span> GitHub Actions 클라우드 러너 서버 배정 중...';
    consoleTerminal.innerHTML = "";
    appendTerminalLine("🚀 1단계: 깃허브 API를 사용해 원격 가상 컴퓨터 기동 신호 직접 전송 중...", "success");

    // GitHub API dispatches 직접 호출 (무설치 서버리스 통신)
    const triggerUrl = `https://api.github.com/repos/${owner}/${name}/actions/workflows/remote_shorts_generator.yml/dispatches`;
    
    try {
      const response = await fetch(triggerUrl, {
        method: 'POST',
        headers: {
          'Accept': 'application/vnd.github+json',
          'Authorization': `Bearer ${token}`,
          'X-GitHub-Api-Version': '2022-11-28'
        },
        body: JSON.stringify({
          ref: 'main',
          inputs: {
            video_url: selectedVideoUrl,
            gemini_api_key: gemini
          }
        })
      });

      if (response.status !== 204) {
        const errorData = await response.json();
        throw new Error(errorData.message || "API 기동 권한 에러");
      }

      appendTerminalLine("✅ GitHub Actions 원격 가상 서버 시동 성공!", "success");
      appendTerminalLine("📡 2단계: 깃허브 가상 러너 상태 실시간 추적 스캔 개시 (5초 주기로 스캔)...", "success");
      
      // 5초 간격으로 Actions 런 감시 돌입
      startStatusPolling(token, owner, name);

    } catch (err) {
      appendTerminalLine(`❌ 기동 실패: ${err.message}`, "error");
      btnTriggerAction.disabled = false;
      btnTriggerAction.innerHTML = '<i class="fa-solid fa-rocket"></i> 쇼츠 자동화 제작 기동 (GitHub Actions)';
    }
  });

  // 5. 깃허브 API 실시간 스캔 (폴링)
  function startStatusPolling(token, owner, name) {
    if (statusPollingInterval) clearInterval(statusPollingInterval);
    
    let dots = "";
    statusPollingInterval = setInterval(async () => {
      dots = dots.length >= 3 ? "" : dots + ".";
      
      const runsUrl = `https://api.github.com/repos/${owner}/${name}/actions/runs`;
      
      try {
        const response = await fetch(runsUrl, {
          headers: {
            'Accept': 'application/vnd.github+json',
            'Authorization': `Bearer ${token}`,
            'X-GitHub-Api-Version': '2022-11-28'
          }
        });

        if (!response.ok) throw new Error("스캔 API 호출 실패");
        const resData = await response.json();
        const runs = resData.workflow_runs || [];
        
        const generatorRuns = runs.filter(r => r.path?.includes('remote_shorts_generator'));
        
        if (generatorRuns.length === 0) {
          appendTerminalLine(`⏳ 대기열 배정 중${dots}`);
          return;
        }

        const latestRun = generatorRuns[0];
        const status = latestRun.status;       // queued, in_progress, completed
        const conclusion = latestRun.conclusion;   // success, failure
        const runId = latestRun.id;

        if (status === 'queued') {
          appendTerminalLine(`⏳ [원격 주방 대기열] 깃허브 가상 서버 자원 할당 대기 중${dots}`);
        } else if (status === 'in_progress') {
          appendTerminalLine(`⚙️ [원격 빌드 가공 중] 광대역 유튜브 다운로드, 컷 편집 및 edge-tts 합성 처리 중${dots}`);
        } else if (status === 'completed') {
          clearInterval(statusPollingInterval);
          statusPollingInterval = null;

          if (conclusion === 'success') {
            appendTerminalLine("==================================================", "success");
            appendTerminalLine("🎉 [GitHub Actions 빌드 성공] 쇼츠 자동 가공 및 XML 생성이 100% 완료되었습니다!", "success");
            appendTerminalLine("📦 1일 한정 만료 깃허브 보관함에 아티팩트 ZIP 아카이브가 안전하게 저장되었습니다.", "success");
            appendTerminalLine("==================================================", "success");
            
            // 완료 성공 시 아티팩트 다운로드 웹페이지 주소 노출
            const artifactPageUrl = `https://github.com/${owner}/${name}/actions/runs/${runId}`;
            renderZipDownloadButton(artifactPageUrl);
          } else {
            appendTerminalLine(`❌ [GitHub Actions 실패] 빌드가 실패로 종료되었습니다 (결과: ${conclusion}).`, "error");
            resetTriggerButton();
          }
        }
      } catch (err) {
        appendTerminalLine(`⚠️ 상태 스캔 경고: ${err.message}`);
      }
    }, 5000); // 5초
  }

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

  // 6. 터미널 헬퍼 및 유틸리티
  function appendTerminalLine(text, className = "") {
    const placeholder = document.getElementById('terminal-placeholder');
    if (placeholder) placeholder.remove();

    const line = document.createElement('div');
    line.className = `terminal-line ${className}`;
    line.innerText = `[${new Date().toLocaleTimeString()}] ${text}`;
    
    consoleTerminal.appendChild(line);
    consoleTerminal.scrollTop = consoleTerminal.scrollHeight;
  }

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

  function escapeHtml(unsafe) {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
