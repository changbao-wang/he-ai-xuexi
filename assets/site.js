(function () {
  'use strict';

  function init() {
    const storageKey = 'he-ai-xuexi:bookmarks:v1';
    const bookmarkButtons = Array.from(document.querySelectorAll('[data-bookmark]'));
    const storageStatuses = Array.from(document.querySelectorAll('[data-storage-status]'));
    let bookmarks = new Set();
    let refreshArchive = function () {};

    function announceStorage(message) {
      storageStatuses.forEach(function (node) { node.textContent = message; });
    }

    function validDate(value) {
      if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
      const date = new Date(value + 'T00:00:00Z');
      return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
    }

    function parseBookmarks(raw) {
      if (!raw) return new Set();
      const values = JSON.parse(raw);
      if (!Array.isArray(values)) throw new Error('Invalid bookmark data');
      return new Set(values.filter(validDate));
    }

    function readBookmarks() {
      try {
        bookmarks = parseBookmarks(window.localStorage.getItem(storageKey));
      } catch (error) {
        announceStorage('暂时无法读取本机收藏。收藏只保存在当前浏览器，请确认浏览器允许本地存储。');
      }
    }

    function refreshBookmarks() {
      bookmarkButtons.forEach(function (button) {
        const date = button.dataset.bookmark;
        const saved = bookmarks.has(date);
        button.setAttribute('aria-pressed', String(saved));
        button.setAttribute('aria-label', (saved ? '取消收藏 ' : '收藏 ') + date + ' 日报');
        const label = button.querySelector('[data-bookmark-label]');
        if (label) label.textContent = saved ? '已收藏' : '收藏';
        if (!validDate(date)) button.disabled = true;
      });
      refreshArchive();
    }

    readBookmarks();
    bookmarkButtons.forEach(function (button) {
      button.addEventListener('click', function () {
        const date = button.dataset.bookmark;
        if (!validDate(date)) return;
        // Read again before writing so a recent change in another tab is retained.
        let next;
        try {
          next = parseBookmarks(window.localStorage.getItem(storageKey));
          if (next.has(date)) next.delete(date);
          else next.add(date);
          window.localStorage.setItem(storageKey, JSON.stringify(Array.from(next).sort()));
        } catch (error) {
          announceStorage('本次收藏操作未保存。请允许浏览器使用本地存储后重试。');
          return;
        }
        bookmarks = next;
        announceStorage(bookmarks.has(date) ? '已收藏，保存在当前浏览器中。' : '已取消收藏。');
        refreshBookmarks();
      });
    });

    window.addEventListener('storage', function (event) {
      if (event.key !== storageKey && event.key !== null) return;
      readBookmarks();
      refreshBookmarks();
    });

    const archive = document.querySelector('[data-archive]');
    if (archive) {
      const search = archive.querySelector('#daily-search');
      const topicButtons = Array.from(archive.querySelectorAll('[data-topic]'));
      const savedButton = archive.querySelector('[data-saved-filter]');
      const count = archive.querySelector('#result-count');
      const empty = archive.querySelector('#archive-empty');
      const clear = archive.querySelector('#clear-filters');
      const moreTopics = archive.querySelector('[data-more-topics]');
      const moreTopicButtons = moreTopics ? Array.from(moreTopics.querySelectorAll('[data-topic]')) : [];
      const activeTopicStatus = archive.querySelector('[data-active-topic]');
      const reports = Array.from(archive.querySelectorAll('[data-report]')).map(function (element) {
        let topics = [];
        try {
          const value = JSON.parse(element.dataset.topics || '[]');
          if (Array.isArray(value)) topics = value.filter(function (item) { return typeof item === 'string'; });
        } catch (error) { /* A malformed tag list must not hide an otherwise readable report. */ }
        return { element: element, date: element.dataset.date, search: normalize(element.dataset.search || element.textContent), topics: topics };
      });
      const allowedTopics = new Set(topicButtons.map(function (button) { return button.dataset.topic; }));
      let activeTopic = '';
      let onlySaved = false;

      function normalize(value) {
        return String(value || '').normalize('NFKC').toLocaleLowerCase('zh-CN').trim().replace(/\s+/g, ' ');
      }

      function readQuery() {
        const params = new URL(window.location.href).searchParams;
        if (search) search.value = params.get('q') || '';
        const topic = params.get('topic') || '';
        activeTopic = allowedTopics.has(topic) ? topic : '';
        onlySaved = params.get('saved') === '1';
      }

      function updateQuery() {
        const url = new URL(window.location.href);
        const query = search ? search.value.trim() : '';
        if (query) url.searchParams.set('q', query);
        else url.searchParams.delete('q');
        if (activeTopic) url.searchParams.set('topic', activeTopic);
        else url.searchParams.delete('topic');
        if (onlySaved) url.searchParams.set('saved', '1');
        else url.searchParams.delete('saved');
        try { window.history.replaceState(window.history.state, '', url); } catch (error) { /* Filtering still works in restricted or file previews. */ }
      }

      refreshArchive = function () {
        const words = normalize(search ? search.value : '').split(' ').filter(Boolean);
        let visible = 0;
        reports.forEach(function (report) {
          const matches = words.every(function (word) { return report.search.includes(word); }) &&
            (!activeTopic || report.topics.includes(activeTopic)) && (!onlySaved || bookmarks.has(report.date));
          report.element.hidden = !matches;
          if (matches) visible += 1;
        });
        topicButtons.forEach(function (button) { button.setAttribute('aria-pressed', String(button.dataset.topic === activeTopic)); });
        if (moreTopics && moreTopicButtons.some(function (button) { return button.dataset.topic === activeTopic; })) moreTopics.open = true;
        if (activeTopicStatus) {
          activeTopicStatus.hidden = !activeTopic;
          activeTopicStatus.textContent = activeTopic ? '当前主题：' + activeTopic : '';
        }
        if (savedButton) savedButton.setAttribute('aria-pressed', String(onlySaved));
        if (count) count.textContent = visible + ' 篇日报';
        if (empty) empty.hidden = visible !== 0;
      };

      function applyFilters() {
        refreshArchive();
        updateQuery();
      }

      if (search) search.addEventListener('input', applyFilters);
      topicButtons.forEach(function (button) {
        button.addEventListener('click', function () {
          activeTopic = button.dataset.topic || '';
          applyFilters();
        });
      });
      if (savedButton) savedButton.addEventListener('click', function () {
        onlySaved = !onlySaved;
        applyFilters();
      });
      if (clear) clear.addEventListener('click', function () {
        if (search) search.value = '';
        activeTopic = '';
        onlySaved = false;
        applyFilters();
        if (search) search.focus();
      });
      window.addEventListener('popstate', function () { readQuery(); refreshArchive(); });
      readQuery();
    }
    refreshBookmarks();

    const tocPanel = document.querySelector('[data-toc-panel]');
    if (tocPanel && typeof window.matchMedia === 'function') {
      const mobileReading = window.matchMedia('(max-width: 760px)');
      function adaptToc() { tocPanel.open = !mobileReading.matches; }
      adaptToc();
      if (typeof mobileReading.addEventListener === 'function') mobileReading.addEventListener('change', adaptToc);
      else if (typeof mobileReading.addListener === 'function') mobileReading.addListener(adaptToc);
    }

    const menuToggle = document.querySelector('[data-menu-toggle]');
    const navigation = document.querySelector('#main-nav');
    if (menuToggle && navigation) {
      function setMenu(open) {
        menuToggle.setAttribute('aria-expanded', String(open));
        menuToggle.setAttribute('aria-label', open ? '收起导航' : '展开导航');
        navigation.dataset.open = String(open);
      }
      setMenu(false);
      menuToggle.addEventListener('click', function () { setMenu(menuToggle.getAttribute('aria-expanded') !== 'true'); });
      navigation.addEventListener('click', function (event) {
        if (event.target.closest('a')) setMenu(false);
      });
      document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && menuToggle.getAttribute('aria-expanded') === 'true') {
          setMenu(false);
          menuToggle.focus();
        }
      });
    }

    const progress = document.querySelector('[data-reading-progress]');
    const readingBody = document.querySelector('[data-reading-body]');
    if (progress && readingBody) {
      let scheduled = false;
      progress.setAttribute('role', 'progressbar');
      progress.setAttribute('aria-label', '阅读进度');
      progress.setAttribute('aria-valuemin', '0');
      progress.setAttribute('aria-valuemax', '100');
      function updateProgress() {
        scheduled = false;
        const rect = readingBody.getBoundingClientRect();
        const viewport = window.innerHeight;
        const distance = rect.height - viewport * 0.65;
        const value = distance > 0 ? Math.min(1, Math.max(0, (viewport * 0.2 - rect.top) / distance)) : (rect.bottom <= viewport * 0.85 ? 1 : 0);
        progress.style.transform = 'scaleX(' + value + ')';
        progress.style.transformOrigin = 'left center';
        progress.setAttribute('aria-valuenow', String(Math.round(value * 100)));
      }
      function queueProgress() {
        if (!scheduled) { scheduled = true; window.requestAnimationFrame(updateProgress); }
      }
      window.addEventListener('scroll', queueProgress, { passive: true });
      window.addEventListener('resize', queueProgress);
      window.addEventListener('load', queueProgress);
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(queueProgress);
      queueProgress();
    }

    function legacyCopy(value) {
      const previous = document.activeElement;
      const field = document.createElement('textarea');
      field.value = value;
      field.setAttribute('readonly', '');
      field.setAttribute('aria-label', '页面链接');
      field.style.position = 'fixed';
      field.style.left = '-9999px';
      field.style.top = '0';
      document.body.appendChild(field);
      let copied = false;
      try {
        field.select();
        copied = document.execCommand('copy');
      } catch (error) { copied = false; }
      finally {
        field.remove();
        if (previous && typeof previous.focus === 'function') previous.focus({ preventScroll: true });
      }
      return copied;
    }

    document.querySelectorAll('[data-copy-link]').forEach(function (button) {
      button.addEventListener('click', async function () {
        const statuses = document.querySelectorAll('[data-share-status]');
        let copied = false;
        try {
          if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(window.location.href);
            copied = true;
          }
        } catch (error) { /* Try the browser's selection-based copy next. */ }
        if (!copied) copied = legacyCopy(window.location.href);
        statuses.forEach(function (node) { node.textContent = copied ? '链接已复制，可以分享了。' : '未能自动复制，请复制浏览器地址栏中的链接。'; });
      });
    });

    document.documentElement.classList.add('js');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
}());
