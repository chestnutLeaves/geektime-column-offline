/* 阅读记录只写入当前站点的 localStorage；不保存正文，不向服务器发送数据。 */
(() => {
  'use strict';
  const KEY = 'reading-library.history.v1';
  const LIMIT = 50;
  const empty = () => ({version: 1, clearedAt: 0, entries: []});
  const clamp = (value, min, max) => Math.min(max, Math.max(min, Number(value) || 0));

  // 存储内容也需要校验，只接受本站实际文章路径，防止异常链接或旧数据影响页面。
  function articlePath(value) {
    try {
      const url = new URL(value, location.origin);
      if (url.origin !== location.origin) return null;
      const parts = url.pathname.split('/').map(part => decodeURIComponent(part));
      if (parts.some(part => /[/\\\x00-\x1f]/.test(part))) return null;
      const path = parts.map(part => encodeURIComponent(part).replace(/[!'()*]/g, char => '%' + char.charCodeAt(0).toString(16).toUpperCase())).join('/');
      if (!/^\/(?:courses\/[^/]+|articles|geektime|relationships)\/[^/]+\.html$/.test(path)) return null;
      return parts.at(-1) === 'index.html' ? null : path;
    } catch (_) { return null; }
  }

  function normalizeEntry(value) {
    if (!value || typeof value !== 'object') return null;
    const url = typeof value.url === 'string' ? articlePath(value.url) : null;
    if (!url || typeof value.title !== 'string' || !value.title.trim() || !Number.isFinite(value.readAt)) return null;
    const position = value.position || {};
    return {
      url, title: value.title.trim().slice(0, 400),
      collection: typeof value.collection === 'string' ? value.collection.trim().slice(0, 200) : '',
      collectionUrl: url.slice(0, url.lastIndexOf('/') + 1) + 'index.html',
      readAt: clamp(value.readAt, 0, Date.now()),
      position: {
        progress: clamp(position.progress, 0, 1),
        scrollY: clamp(position.scrollY, 0, 1e8),
        anchorIndex: Number.isInteger(position.anchorIndex) ? clamp(position.anchorIndex, -1, 1e6) : -1,
        anchorOffset: clamp(position.anchorOffset, -1e5, 1e7),
      },
    };
  }

  function read() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return empty();
      const data = JSON.parse(raw);
      // 未来版本不覆盖；损坏数据退回空记录，后续正常阅读可重新建立记录。
      if (data && data.version !== undefined && data.version !== 1) return null;
      if (!data || !Array.isArray(data.entries)) return empty();
      const seen = new Set();
      const entries = data.entries.slice(0, 500).map(normalizeEntry).filter(Boolean)
        .sort((a, b) => b.readAt - a.readAt)
        .filter(entry => {if (seen.has(entry.url)) return false;seen.add(entry.url);return true;})
        .slice(0, LIMIT);
      return {version: 1, clearedAt: clamp(data.clearedAt, 0, Date.now()), entries};
    } catch (_) { return empty(); }
  }

  function write(data) {
    try {localStorage.setItem(KEY, JSON.stringify(data));return true;} catch (_) {return false;}
  }

  function save(entry) {
    const data = read();
    if (!data) return false;
    data.entries = [entry, ...data.entries.filter(item => item.url !== entry.url)].slice(0, LIMIT);
    return write(data);
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function progressLabel(entry) {
    const percent = Math.round(entry.position.progress * 100);
    return percent >= 99 ? '已到文末' : percent > 0 ? '读至 ' + percent + '%' : '刚开始阅读';
  }

  function timeLabel(timestamp) {
    const minutes = Math.floor(Math.max(0, Date.now() - timestamp) / 60000);
    if (minutes < 1) return '刚刚';
    if (minutes < 60) return minutes + ' 分钟前';
    if (minutes < 1440) return Math.floor(minutes / 60) + ' 小时前';
    const days = Math.floor(minutes / 1440);
    if (days < 7) return days + ' 天前';
    return new Date(timestamp).toLocaleDateString('zh-CN');
  }

  function initHome() {
    const section = document.querySelector('#recent-reading');
    if (!section) return;
    const list = section.querySelector('.recent-list');
    const more = section.querySelector('#recent-more');
    const clear = section.querySelector('#recent-clear');
    const confirmation = section.querySelector('.history-confirm');
    const status = document.querySelector('#history-status');
    let expanded = false;

    function render() {
      const entries = read()?.entries || [];
      section.hidden = !entries.length;
      list.replaceChildren();
      section.querySelector('#recent-count').textContent = String(entries.length);
      (expanded ? entries : entries.slice(0, 3)).forEach(entry => {
        const item = element('li', 'recent-item');
        const link = element('a', 'recent-link');
        link.href = entry.url;
        link.append(element('span', 'recent-collection', entry.collection || '文章'), element('span', 'recent-title', entry.title));
        const info = element('span', 'recent-info');
        info.append(element('span', 'recent-progress', progressLabel(entry)));
        const time = element('time', '', timeLabel(entry.readAt));
        time.dateTime = new Date(entry.readAt).toISOString();
        time.title = new Date(entry.readAt).toLocaleString('zh-CN');
        info.append(time);
        link.append(info);
        item.append(link);
        list.append(item);
      });
      more.hidden = entries.length <= 3;
      more.textContent = expanded ? '收起记录' : '查看全部 ' + entries.length + ' 条';
      more.setAttribute('aria-expanded', String(expanded));
      list.classList.toggle('expanded', expanded);

      // 专栏卡片保持目录入口，另加独立的继续阅读链接，不嵌套链接。
      document.querySelectorAll('.course-card').forEach(card => {
        const href = new URL(card.querySelector('.course-link').href).pathname;
        const latest = entries.find(entry => entry.collectionUrl === href);
        card.querySelector('.course-resume')?.remove();
        if (!latest) return;
        const resume = element('a', 'course-resume');
        resume.href = latest.url;
        resume.title = '继续阅读：' + latest.title + '（' + progressLabel(latest) + '）';
        resume.append(element('span', 'resume-label', '继续阅读 · ' + progressLabel(latest)), element('span', 'resume-title', latest.title));
        card.querySelector('.card-bottom').before(resume);
      });
    }

    function cancelClear() {confirmation.hidden = true;clear.hidden = false;}
    more.addEventListener('click', () => {expanded = !expanded;render();});
    clear.addEventListener('click', () => {
      confirmation.hidden = false;clear.hidden = true;
      section.querySelector('#history-confirm-clear').focus({preventScroll: true});
    });
    section.querySelector('#history-cancel-clear').addEventListener('click', () => {cancelClear();clear.focus();});
    confirmation.addEventListener('keydown', event => {if (event.key === 'Escape') {cancelClear();clear.focus();}});
    section.querySelector('#history-confirm-clear').addEventListener('click', () => {
      // 写入清空时间，让其他标签页取消尚未保存的位置，防止旧记录重新出现。
      if (!write({version: 1, clearedAt: Date.now(), entries: []})) {
        status.textContent = '浏览器未允许修改阅读记录，请检查网站存储设置。';return;
      }
      expanded = false;cancelClear();render();
      status.textContent = '已清空此浏览器中的阅读记录。';
      document.querySelector('#course-search')?.focus({preventScroll: true});
    });
    window.addEventListener('storage', event => {if (event.key === KEY || event.key === null) {cancelClear();render();}});
    window.addEventListener('pageshow', render);
    document.addEventListener('visibilitychange', () => {if (!document.hidden) render();});
    render();
  }

  function initArticle() {
    const current = document.querySelector('.chapter-links a.active');
    const main = document.querySelector('.reading-main');
    const url = articlePath(location.href);
    // 只记录正文页；首页、专栏目录、资料页和 PDF 下载页不会污染最近阅读。
    if (!current || !main || !url || articlePath(current.href) !== url) return;
    const overview = document.querySelector('.course-overview');
    const oldData = read();
    const previous = oldData?.entries.find(entry => entry.url === url);
    const entry = normalizeEntry({url, title: current.textContent, collection: overview?.textContent || '', readAt: Date.now(), position: previous?.position});
    const footer = main.querySelector('.reading-footer');
    const anchors = Array.from(main.querySelectorAll('h1,h2,h3,h4,p,pre,table,blockquote,li,img')).filter(node => !footer?.contains(node));
    let restoring = false;
    let paused = false;
    let dirty = false;
    let saveTimer;
    let restoreTimer;
    let observer;
    let clearGeneration = oldData?.clearedAt || 0;
    let notice;
    let noticeTimer;
    let warned = false;

    function headerOffset() {return (document.querySelector('.topbar')?.getBoundingClientRect().height || 88) + 18;}
    function range() {
      const start = Math.max(0, main.getBoundingClientRect().top + scrollY - headerOffset());
      const bottom = footer ? footer.getBoundingClientRect().top + scrollY : main.getBoundingClientRect().bottom + scrollY;
      const end = Math.max(start, Math.min(document.documentElement.scrollHeight - innerHeight, bottom - innerHeight + 24));
      return {start, end};
    }

    function capture() {
      const {start, end} = range();
      const line = scrollY + headerOffset();
      // 保留可见段落及段内偏移，字号、窗口宽度或图片高度变化时仍靠近原来的段落。
      let index = -1;
      for (let i = 0; i < anchors.length; i += 1) {
        const top = anchors[i].getBoundingClientRect().top + scrollY;
        if (top <= line) index = i;
        else break;
      }
      return {
        progress: end > start ? clamp((scrollY - start) / (end - start), 0, 1) : 1,
        scrollY,
        anchorIndex: index,
        anchorOffset: index < 0 ? 0 : line - (anchors[index].getBoundingClientRect().top + scrollY),
      };
    }

    function showNotice(text, allowRestart = false) {
      if (!notice) {notice = element('div', 'reading-notice');notice.setAttribute('role', 'status');document.body.append(notice);}
      notice.replaceChildren(element('span', '', text));
      if (allowRestart) {
        const restart = element('button', '', '回到开头');restart.type = 'button';
        restart.addEventListener('click', () => {
          stopRestore();paused = false;window.scrollTo({top: 0, behavior: 'instant'});dirty = true;persist();notice.hidden = true;
        });
        notice.append(restart);
      }
      const close = element('button', 'notice-close', '×');close.type = 'button';close.setAttribute('aria-label', '关闭阅读提示');
      close.addEventListener('click', () => {notice.hidden = true;});notice.append(close);notice.hidden = false;
      clearTimeout(noticeTimer);noticeTimer = setTimeout(() => {if (!notice.contains(document.activeElement)) notice.hidden = true;}, 10000);
    }

    function warnStorage() {
      if (warned) return;
      warned = true;showNotice('浏览器暂时无法保存阅读记录，仍可正常阅读。');
    }

    function persist() {
      clearTimeout(saveTimer);
      if (paused || restoring || !dirty) return;
      const data = read();
      if (data && data.clearedAt !== clearGeneration) {paused = true;dirty = false;return;}
      entry.position = capture();entry.readAt = Date.now();
      if (!save(entry)) warnStorage();
      dirty = false;
    }

    function stopRestore() {
      restoring = false;observer?.disconnect();clearTimeout(restoreTimer);
    }

    function restorePosition() {
      if (!restoring) return;
      const position = previous.position;
      const anchor = anchors[position.anchorIndex];
      const {start, end} = range();
      let top = position.scrollY < start ? position.scrollY : start + (end - start) * position.progress;
      if (anchor && position.scrollY >= start) {
        top = anchor.getBoundingClientRect().top + scrollY + Math.min(position.anchorOffset, anchor.getBoundingClientRect().height) - headerOffset();
      }
      window.scrollTo({top: Math.max(0, top), behavior: 'instant'});
    }

    function beginVisit() {
      if (document.hidden || paused) return;
      if ((read()?.clearedAt || 0) !== clearGeneration) {paused = true;dirty = false;return;}
      entry.readAt = Date.now();
      if (!save(entry)) warnStorage();
    }

    // 地址带锚点时尊重显式跳转；首次阅读保留浏览器正常定位，不自动拉回顶部。
    if (previous?.position.scrollY > 32 && !location.hash) {
      history.scrollRestoration = 'manual';restoring = true;
      requestAnimationFrame(restorePosition);
      if (document.fonts?.ready) document.fonts.ready.then(restorePosition);
      if ('ResizeObserver' in window) {observer = new ResizeObserver(restorePosition);observer.observe(main);}
      window.addEventListener('load', restorePosition, {once: true});
      restoreTimer = setTimeout(stopRestore, 5000);
      showNotice('已回到上次阅读位置', true);
    }
    beginVisit();

    function userAction(event) {
      // 触碰或滚动就停止自动校正，避免图片加载时与用户争抢滚动位置。
      stopRestore();
      if (paused && !document.hidden && !event.target.closest?.('.topbar, .reading-sidebar')) {
        clearGeneration = read()?.clearedAt || 0;paused = false;
      }
    }
    ['wheel', 'touchstart', 'pointerdown', 'keydown'].forEach(type => window.addEventListener(type, userAction, {passive: true}));
    window.addEventListener('scroll', () => {
      if (restoring || paused || document.hidden) return;
      dirty = true;clearTimeout(saveTimer);saveTimer = setTimeout(persist, 500);
    }, {passive: true});
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) persist();
      else if (!paused) beginVisit();
    });
    window.addEventListener('pagehide', persist);
    window.addEventListener('pageshow', event => {if (event.persisted && !paused) beginVisit();});
    window.addEventListener('hashchange', stopRestore);
    window.addEventListener('storage', event => {
      if (event.key !== KEY && event.key !== null) return;
      const data = read();
      if (event.key === null || !event.newValue || data?.clearedAt !== clearGeneration) {
        paused = true;dirty = false;clearTimeout(saveTimer);stopRestore();
        if (notice) notice.hidden = true;
      }
    });
  }

  initHome();
  initArticle();
})();
