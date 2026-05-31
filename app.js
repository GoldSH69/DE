document.addEventListener('DOMContentLoaded', () => {
  // UI 요소 참조
  const searchInput = document.getElementById('search-input');
  const searchPeriod = document.getElementById('search-period');
  const searchBtn = document.getElementById('search-btn');
  const videoGridContainer = document.getElementById('video-grid-container');
  const consoleTerminal = document.getElementById('console-terminal');
  const btnSaveLocal = document.getElementById('btn-save-local');
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
  const recentSearchesContainer = document.getElementById('recent-searches-container');

  let selectedVideoUrl = "";
  let selectedVideoTitle = "";
  let statusPollingInterval = null;
  let activeEventSource = null;

  // 1. 연동 키 설정 모달 제어
  btnSettings.addEventListener('click', () => {
    inputGithubToken.value = localStorage.getItem('github_token') || "";
    inputGeminiKey.value = localStorage.getItem('gemini_api_key') || "";
    inputRepoOwner.value = localStorage.getItem('repo_owner') || "GoldSH69";
    inputRepoName.value = localStorage.getItem('repo_name') || "DE";
    document.getElementById('input-youtube-cookies').value = localStorage.getItem('youtube_cookies') || "";
    
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
    const cookies = document.getElementById('input-youtube-cookies').value.trim();

    if (!token) {
      alert("GitHub Token은 API 연동 구동을 위한 필수 값입니다.");
      return;
    }

    localStorage.setItem('github_token', token);
    localStorage.setItem('gemini_api_key', gemini);
    localStorage.setItem('repo_owner', owner);
    localStorage.setItem('repo_name', name);
    localStorage.setItem('youtube_cookies', cookies);

    settingsModal.style.display = 'none';
    alert("🔑 연동 설정이 브라우저 로컬 저장소에 저장되었습니다.");
  });

  // 최근 검색어 렌더링 초기 구동
  renderRecentSearches();

  // 2. 최근 검색어 로직 관리
  function renderRecentSearches() {
    const searches = JSON.parse(localStorage.getItem('recent_searches') || '[]');
    recentSearchesContainer.innerHTML = "";
    
    if (searches.length === 0) {
      recentSearchesContainer.style.display = 'none';
      return;
    }
    
    recentSearchesContainer.style.display = 'flex';
    searches.forEach(keyword => {
      const badge = document.createElement('span');
      badge.className = 'search-badge';
      badge.innerText = keyword;
      badge.addEventListener('click', () => {
        searchInput.value = keyword;
        executeSearch();
      });
      recentSearchesContainer.appendChild(badge);
    });
  }

  function saveRecentSearch(keyword) {
    if (!keyword) return;
    let searches = JSON.parse(localStorage.getItem('recent_searches') || '[]');
    
    searches = searches.filter(k => k !== keyword);
    searches.unshift(keyword);
    
    if (searches.length > 8) searches.pop();
    
    localStorage.setItem('recent_searches', JSON.stringify(searches));
    renderRecentSearches();
  }

  // 3. 지능형 4중 CORS 프록시 자동 우회 로테이션 유튜브 검색
  searchBtn.addEventListener('click', executeSearch);
  searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') executeSearch();
  });

  const proxyEndpoints = [
    url => `https://api.allorigins.win/get?url=${encodeURIComponent(url)}`,
    url => `https://corsproxy.io/?${encodeURIComponent(url)}`,
    url => `https://api.codetabs.com/v1/proxy?url=${encodeURIComponent(url)}`,
    url => `https://api.cors.lol/?url=${encodeURIComponent(url)}`,
    url => `https://thingproxy.freeboard.io/fetch/${url}`
  ];

  function extractYoutubeVideoId(url) {
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=|shorts\/)([^#\&\?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
  }
  const invidiousInstances = [
    'https://inv.thepixora.com',
    'https://yt.chocolatemoo53.com',
    'https://yewtu.be',
    'https://invidious.projectsegfau.lt',
    'https://invidious.privacydev.net',
    'https://inv.tux.im',
    'https://invidious.slipfox.xyz',
    'https://invidious.nerdvpn.de'
  ];

  async function executeSearch() {
    const query = searchInput.value.trim();
    const period = searchPeriod.value;

    if (!query) {
      alert("스캔할 예능 키워드 또는 유튜브 영상 URL을 입력해 주세요.");
      return;
    }

    saveRecentSearch(query);

    searchBtn.disabled = true;
    searchBtn.innerHTML = '<span class="spinner"></span> 스캔 중...';
    
    // 유튜브 직접 영상 주소(URL) 감지 시 bypass 처리
    const directVideoId = extractYoutubeVideoId(query);
    if (directVideoId) {
      videoGridContainer.innerHTML = `
        <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
          <span class="spinner" style="border-top-color: var(--color-point); width: 30px; height: 30px; margin-bottom: 12px;"></span>
          <p style="font-family: var(--font-title); font-weight: 600; color: var(--color-point);">입력하신 유튜브 영상 정보 로딩 중...</p>
        </div>
      `;
      
      selectedVideoUrl = "";
      selectedVideoTitle = "";
      btnSaveLocal.disabled = true;
      btnTriggerAction.disabled = true;

      try {
        const oembedUrl = `https://www.youtube.com/oembed?url=${encodeURIComponent(query)}&format=json`;
        const response = await fetch(oembedUrl);
        if (!response.ok) throw new Error("oEmbed 호출 실패");
        const data = await response.json();
        
        const video = {
          video_id: directVideoId,
          title: data.title || "직접 입력한 유튜브 영상",
          url: query,
          view_count: 0,
          duration: 0,
          published_date_text: data.author_name || "유튜브 직접 링크",
          published_date: "",
          collected_at: new Date().toISOString()
        };
        
        renderVideoCards([video]);
        appendTerminalLine(`✅ 직접 링크 파싱 성공: [${video.title}]`, "success");
      } catch (err) {
        console.warn("[oEmbed Fail] Retrying with noembed...", err);
        try {
          const noembedUrl = `https://noembed.com/embed?url=${encodeURIComponent(query)}`;
          const response = await fetch(noembedUrl);
          const data = await response.json();
          if (data.error) throw new Error(data.error);

          const video = {
            video_id: directVideoId,
            title: data.title || "직접 입력한 유튜브 영상",
            url: query,
            view_count: 0,
            duration: 0,
            published_date_text: data.author_name || "유튜브 직접 링크",
            published_date: "",
            collected_at: new Date().toISOString()
          };
          
          renderVideoCards([video]);
          appendTerminalLine(`✅ 직접 링크 파싱 성공 (noembed): [${video.title}]`, "success");
        } catch (fallbackErr) {
          const video = {
            video_id: directVideoId,
            title: "직접 입력한 유튜브 영상",
            url: query,
            view_count: 0,
            duration: 0,
            published_date_text: "직접 링크",
            published_date: "",
            collected_at: new Date().toISOString()
          };
          renderVideoCards([video]);
          appendTerminalLine(`⚠️ 정보 로드 제한으로 기본 영상 정보로 세팅 완료 (ID: ${directVideoId})`);
        }
      }
      
      searchBtn.disabled = false;
      searchBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 소재 스캔하기';
      return;
    }

    videoGridContainer.innerHTML = `
      <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
        <span class="spinner" style="border-top-color: var(--color-point); width: 30px; height: 30px; margin-bottom: 12px;"></span>
        <p style="font-family: var(--font-title); font-weight: 600; color: var(--color-point);">멀티티어 탐색망을 통해 인기 영상 스캔 중...</p>
      </div>
    `;

    selectedVideoUrl = "";
    selectedVideoTitle = "";
    btnSaveLocal.disabled = true;
    btnTriggerAction.disabled = true;

    // 0단계: 로컬 백엔드 API 검색 시도 (로컬 서버 구동 시 최고 속도 및 100% 성공율 보장)
    const hostname = window.location.hostname;
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1' || hostname.startsWith('192.168.');
    
    if (isLocal) {
      appendTerminalLine("🏠 로컬 백엔드 탐색 엔진 구동 시도 중...", "success");
      try {
        const response = await fetch('/api/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: query, period: period })
        });
        
        if (response.ok) {
          const data = await response.json();
          if (data.success && data.results && data.results.length > 0) {
            renderVideoCards(data.results);
            appendTerminalLine(`✅ 로컬 스캔 성공: [${query}] (${data.results.length}개 후보 발굴)`, "success");
            searchBtn.disabled = false;
            searchBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 소재 스캔하기';
            return;
          }
        }
      } catch (err) {
        console.warn("[Local Search Fail] Falling back to remote proxies...", err);
      }
    }

    let periodSuffix = "";
    let dateParam = "";
    if (period === "today") {
      periodSuffix = " date:today";
      dateParam = "today";
    } else if (period === "this_week") {
      periodSuffix = " date:week";
      dateParam = "week";
    } else if (period === "this_month") {
      periodSuffix = " date:month";
      dateParam = "month";
    } else if (period === "this_year") {
      periodSuffix = " date:year";
      dateParam = "year";
    }

    // 1단계: 6중 인비디어스 오픈 API 로테이션 검색 시도 (CORS 완전 개방 구조)
    appendTerminalLine("📡 1단계: 6중 인비디어스 오픈 검색망 연동 시도 중...");
    let searchSuccess = false;
    
    for (let i = 0; i < invidiousInstances.length; i++) {
      const instance = invidiousInstances[i];
      const searchUrl = `${instance}/api/v1/search?q=${encodeURIComponent(query)}&date=${dateParam}&type=video`;
      
      console.log(`[Invidious Search] Trying instance: ${instance}`);
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 6000); // 6초 타임아웃
        
        const response = await fetch(searchUrl, { signal: controller.signal });
        clearTimeout(timeoutId);
        
        if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
        
        const items = await response.json();
        if (Array.isArray(items) && items.length > 0) {
          const videos = items
            .filter(item => item.type === 'video' && item.videoId)
            .map(item => ({
              video_id: item.videoId,
              title: item.title,
              url: `https://www.youtube.com/watch?v=${item.videoId}`,
              view_count: item.viewCount || 0,
              duration: item.lengthSeconds || 0,
              published_date_text: item.publishedText || "최근",
              published_date: "",
              collected_at: new Date().toISOString()
            }))
            .filter(v => !(v.duration > 0 && v.duration < 120));
            
          if (videos.length > 0) {
            videos.sort((a, b) => b.view_count - a.view_count);
            const topVideos = videos.slice(0, 8);
            renderVideoCards(topVideos);
            appendTerminalLine(`✅ 오픈 검색 스캔 성공 (${instance.replace('https://', '')})`, "success");
            searchSuccess = true;
            break;
          }
        }
      } catch (err) {
        console.warn(`[Invidious Search] Instance ${instance} failed: ${err.message}`);
        appendTerminalLine(`⚠️ 오픈 검색망 #${i + 1} 혼잡... 우회망 #${i + 2} 스위칭 중`);
      }
    }

    // 2단계: 5중 프록시 로테이션 HTML 스크래핑 검색 시도 (최종 백업)
    if (!searchSuccess) {
      appendTerminalLine("📡 2단계: 5중 프록시 로테이션 HTML 스크래퍼 시동 중...");
      const targetUrl = `https://www.youtube.com/results?search_query=${encodeURIComponent(query + periodSuffix)}`;
      let parsedVideos = [];
      let success = false;

      for (let i = 0; i < proxyEndpoints.length; i++) {
        const getProxyUrl = proxyEndpoints[i];
        const requestUrl = getProxyUrl(targetUrl);
        
        console.log(`[JS Parser] Trying CORS Proxy #${i + 1}...`);
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 6500);

          const response = await fetch(requestUrl, { signal: controller.signal });
          clearTimeout(timeoutId);

          if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
          
          let html = "";
          if (requestUrl.includes('allorigins')) {
            const data = await response.json();
            html = data.contents;
          } else {
            html = await response.text();
          }

          parsedVideos = parseYoutubeHtml(html);
          
          if (parsedVideos.length > 0) {
            success = true;
            break;
          }
        } catch (err) {
          console.warn(`[JS Parser] Proxy #${i + 1} Failed: ${err.message}. Retrying next...`);
          appendTerminalLine(`⚠️ ${i + 1}번 프록시 혼잡... 우회 경로 #${i + 2}번 자동 스위칭 중`, "error");
        }
      }

      if (success) {
        renderVideoCards(parsedVideos);
      } else {
        alert("⚠️ 유튜브 검색 서버 혼잡: 전 세계 우회 검색망이 일시 지연 상태입니다.\n\n💡 해결 방법:\n가공 소스로 점찍어 둔 특정 영상이 있으시다면, 해당 영상의 주소(URL)를 직접 검색창에 붙여넣어 보세요. 지연 없이 1초 만에 즉시 가져올 수 있습니다.");
        videoGridContainer.innerHTML = `
          <div class="terminal-placeholder" style="grid-column: span 2; padding: 60px 0;">
            <i class="fa-solid fa-triangle-exclamation" style="font-size: 2.5rem; color: #c62828; margin-bottom: 12px;"></i>
            <p style="color: #c62828; font-weight: 600;">실시간 스캔 실패: 검색망 전체 지연</p>
            <p style="font-size: 0.85rem; color: var(--color-sub); margin-top: 8px;">원하는 영상의 유튜브 주소(URL)를 검색창에 직접 입력하여 바로 가공을 시작할 수도 있습니다.</p>
          </div>
        `;
      }
    }

    searchBtn.disabled = false;
    searchBtn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> 소재 스캔하기';
  }  function parseYoutubeHtml(html) {
    const videos = [];
    try {
      const match = html.match(/ytInitialData\s*=\s*({.+?});/);
      if (match) {
        const jsonStr = match[1];
        const dataObj = JSON.parse(jsonStr);
        
        const contents = dataObj.contents?.twoColumnSearchResultsRenderer?.primaryContents?.sectionListRenderer?.contents;
        if (contents) {
          const itemSection = contents.find(c => c.itemSectionRenderer);
          const list = itemSection?.itemSectionRenderer?.contents || [];
          
          for (const item of list) {
            const videoRenderer = item.videoRenderer;
            if (!videoRenderer) continue;
            
            const videoId = videoRenderer.videoId;
            const title = videoRenderer.title?.runs?.[0]?.text || "알 수 없는 비디오";
            
            const viewsText = videoRenderer.viewCountText?.simpleText || "";
            const viewCount = parseViewText(viewsText);
            
            const durationText = videoRenderer.lengthText?.simpleText || "";
            const durationSec = parseDurationText(durationText);
            
            if (durationSec > 0 && durationSec < 120) continue;

            const uploadText = videoRenderer.publishedTimeText?.simpleText || "최근";

            videos.push({
              video_id: videoId,
              title: title,
              url: `https://www.youtube.com/watch?v=${videoId}`,
              view_count: viewCount,
              duration: durationSec,
              published_date_text: uploadText,
              published_date: "20260530",
              collected_at: new Date().toISOString()
            });
          }
        }
      }
    } catch (e) {
      console.error("[JS Parser] JSON parsing error: ", e);
    }
    
    videos.sort((a, b) => b.view_count - a.view_count);
    return videos.slice(0, 8);
  }

  function parseViewText(text) {
    if (!text) return 0;
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

  // 4. 비디오 결과 카드 렌더링
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
            <span class="video-date"><i class="fa-solid fa-calendar-days"></i> ${video.published_date_text || video.published_date || "최근"}</span>
          </div>
          <button class="btn-card-action" style="margin-top: 14px;">
            <i class="fa-solid fa-circle-check"></i> 이 영상 제작 대상으로 선택
          </button>
        </div>
      `;

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

        // 듀열 제어 버튼 모두 활성화
        btnSaveLocal.disabled = false;
        btnTriggerAction.disabled = false;
        
        appendTerminalLine(`🎯 제작 타겟 확정: [${video.title}]`);
      });

      videoGridContainer.appendChild(card);
    });
  }

  // ==================================================================
  // 1번 상황 버튼: 로컬 컴퓨터 즉시 가공 저장 클릭 이벤트 복원
  // ==================================================================
  btnSaveLocal.addEventListener('click', () => {
    // 깃허브 페이지 등 완전 외부 접속 상황 감지 체크 
    const hostname = window.location.hostname;
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1' || hostname.startsWith('192.168.');
    
    if (!isLocal) {
      appendTerminalLine("⚠️ [로컬 감지 실패] 깃허브 웹페이지로 인터넷 원격 접속 중이시므로 내 컴퓨터 폴더에 다이렉트 저장은 불가능합니다. 우측의 [GitHub Actions] 버튼을 클릭해 기동해 주세요.", "error");
      alert("외부 인터넷 접속 중에는 로컬 직접 저장을 지원하지 않습니다.\n\n우측의 [GitHub Actions] 버튼을 사용하여 원격으로 제작하시고 ZIP 아카이브를 다운로드해 가시기 바랍니다.");
      return;
    }

    if (!selectedVideoUrl) {
      alert("제작할 예능 대상 영상을 선택해 주세요.");
      return;
    }

    if (activeEventSource) activeEventSource.close();

    consoleTerminal.innerHTML = "";
    btnSaveLocal.disabled = true;
    btnTriggerAction.disabled = true;

    appendTerminalLine("🏠 로컬 파이썬 요리 엔진 준비 중...", "success");

    // 로컬 저장 SSE API 개시
    const localCookies = localStorage.getItem('youtube_cookies') || "";
    const sseUrl = `/api/stream_generate_local?video_url=${encodeURIComponent(selectedVideoUrl)}&title=${encodeURIComponent(selectedVideoTitle)}&cookies=${encodeURIComponent(localCookies)}`;
    activeEventSource = new EventSource(sseUrl);

    activeEventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.status === 'progress') {
        appendTerminalLine(data.message);
      } else if (data.status === 'analysis') {
        renderGeminiAnalysis(data.data);
      } else if (data.status === 'complete_local') {
        appendTerminalLine(data.message, "success");
        appendTerminalLine(`📁 CapCut FCP 7 XML 복제 주소: ${data.xml_path}`, "success");
        
        // 경로 클립보드 복사 배려 서비스
        navigator.clipboard.writeText(data.xml_path).then(() => {
          alert(`🎉 [로컬 직접 저장 완료!]\n\nCapCut XML 파일이 내 컴퓨터 output/ 폴더에 직접 수립 완료되었습니다.\n\n경로: ${data.xml_path}\n\n(경로가 복사되었습니다! CapCut '가져오기' 주소창에 Ctrl+V 하세요!)`);
        }).catch(() => {
          alert(`🎉 [로컬 직접 저장 완료!]\n\nCapCut XML 파일이 내 컴퓨터 output/ 폴더에 수립되었습니다.\n\n경로: ${data.xml_path}`);
        });

        resetDualButtons();
        activeEventSource.close();
        activeEventSource = null;
      } else if (data.status === 'error') {
        appendTerminalLine(`❌ 로컬 에러: ${data.message}`, "error");
        resetDualButtons();
        activeEventSource.close();
        activeEventSource = null;
      }
    };

    activeEventSource.onerror = () => {
      appendTerminalLine("❌ 로컬 서버 통신 지연이 발생하여 연결을 해제합니다.", "error");
      resetDualButtons();
      activeEventSource.close();
      activeEventSource = null;
    };
  });

  // ==================================================================
  // 2번 상황 버튼: GitHub Actions API 다이렉트 트리거 기동 (원격/클라우드용)
  // ==================================================================
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

    btnSaveLocal.disabled = true;
    btnTriggerAction.disabled = true;
    btnTriggerAction.innerHTML = '<span class="spinner"></span> 깃허브 러너 배정 중...';
    consoleTerminal.innerHTML = "";
    appendTerminalLine("🚀 1단계: 깃허브 API를 사용해 원격 가상 컴퓨터 기동 신호 직접 전송 중...", "success");

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
            gemini_api_key: gemini,
            youtube_cookies: localStorage.getItem('youtube_cookies') || ""
          }
        })
      });

      if (response.status !== 204) {
        const errorData = await response.json();
        throw new Error(errorData.message || "API 기동 권한 에러");
      }

      appendTerminalLine("✅ GitHub Actions 원격 가상 서버 시동 성공!", "success");
      appendTerminalLine("📡 2단계: 깃허브 가상 러너 상태 실시간 추적 스캔 개시 (5초 주기로 스캔)...", "success");
      
      startStatusPolling(token, owner, name);

    } catch (err) {
      appendTerminalLine(`❌ 기동 실패: ${err.message}`, "error");
      resetDualButtons();
    }
  });

  // 6. 깃허브 API 실시간 스캔 (폴링)
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
        const status = latestRun.status;
        const conclusion = latestRun.conclusion;
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
            
            const artifactPageUrl = `https://github.com/${owner}/${name}/actions/runs/${runId}`;
            renderZipDownloadButton(artifactPageUrl);
          } else {
            appendTerminalLine(`❌ [GitHub Actions 실패] 빌드가 실패로 종료되었습니다 (결과: ${conclusion}).`, "error");
            resetDualButtons();
          }
        }
      } catch (err) {
        appendTerminalLine(`⚠️ 상태 스캔 경고: ${err.message}`);
      }
    }, 5000);
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

  function resetDualButtons() {
    btnSaveLocal.disabled = false;
    btnTriggerAction.disabled = false;
    btnTriggerAction.innerHTML = '<i class="fa-solid fa-rocket"></i> 쇼츠 자동화 제작 기동 (GitHub Actions)';
  }

  // 7. 터미널 헬퍼 및 유틸리티
  function appendTerminalLine(text, className = "") {
    const placeholder = document.getElementById('terminal-placeholder');
    if (placeholder) placeholder.remove();

    const line = document.createElement('div');
    line.className = `terminal-line ${className}`;
    line.innerText = `[${new Date().toLocaleTimeString()}] ${text}`;
    
    consoleTerminal.appendChild(line);
    consoleTerminal.scrollTop = consoleTerminal.scrollHeight;
  }

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
