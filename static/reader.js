/* 章节目录独立滚动；筛选和定位不改变正文或正文滚动位置。 */
(() => {
  const switcher = document.querySelector('.library-switcher');
  if (switcher) {
    document.addEventListener('pointerdown', event => {if (!switcher.contains(event.target)) switcher.open = false;});
    document.addEventListener('focusin', event => {if (!switcher.contains(event.target)) switcher.open = false;});
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && switcher.open) {switcher.open = false;switcher.querySelector('summary').focus();}
    });
  }
  const returnKey = 'library-course-return';
  const browsePaths = new Set(['/', '/courses/index.html', '/articles/index.html', '/geektime/index.html', '/relationships/index.html', '/downloads/index.html']);
  const returnLabels = {
    '/': '首页',
    '/courses/index.html': '技术专栏',
    '/articles/index.html': '技术文章',
    '/geektime/index.html': '技术文章',
    '/relationships/index.html': '生活文章',
    '/downloads/index.html': 'PDF 书籍',
  };
  // 保存生成页的栏目入口，缓存页面恢复或来源失效时不能统一覆盖为首页。
  const returnLinks = Array.from(document.querySelectorAll('.return-to-library')).map(link => ({
    link, href: link.getAttribute('href'), text: link.textContent,
  }));

  function normalizeReturn(value) {
    // 只接受本站浏览入口；存储内容不能把返回链接替换成外部网站或任意文件。
    if (typeof value !== 'string' || !value.trim()) return null;
    try {
      const url = new URL(value, location.origin);
      if (url.origin !== location.origin || url.username || url.password) return null;
      if (url.pathname === '/index.html') url.pathname = '/';
      // 旧版首页本身就是专栏目录，历史筛选地址迁移后仍应回到专栏。
      if (url.pathname === '/' && (['q', 'category', 'sort'].some(key => url.searchParams.has(key)) || url.hash === '#library')) {
        url.pathname = '/courses/index.html';
      }
      if (!browsePaths.has(url.pathname)) return null;
      return url;
    } catch (_) { return null; }
  }

  function restoreReturnLinks() {
    let source = null;
    try {
      const saved = sessionStorage.getItem(returnKey);
      source = normalizeReturn(saved);
      if (source) {
        const migrated = source.pathname + source.search + source.hash;
        if (migrated !== saved) sessionStorage.setItem(returnKey, migrated);
      } else if (saved) {
        sessionStorage.removeItem(returnKey);
      }
    } catch (_) { /* 存储不可用时保留生成页对应的栏目入口。 */ }
    const returnTo = source ? source.pathname + source.search + source.hash : null;
    returnLinks.forEach(({link, href, text}) => {
      if (source) {
        link.href = returnTo;
        link.textContent = '← 返回' + returnLabels[source.pathname];
      } else {
        if (href === null) link.removeAttribute('href');
        else link.setAttribute('href', href);
        link.textContent = text;
      }
    });
    // 返回来源与内容分类是两个动作：只有来源本身为专栏时，分类入口才沿用筛选。
    const courses = source?.pathname === '/courses/index.html' ? returnTo : '/courses/index.html';
    document.querySelectorAll('.switcher-link[data-section="courses"]').forEach(link => {link.href = courses;});
  }

  restoreReturnLinks();
  window.addEventListener('pageshow', restoreReturnLinks);

  const directory = document.querySelector('.chapter-directory');
  if (!directory) return;
  const smallScreen = window.matchMedia('(max-width: 760px)');
  const summary = directory.querySelector('summary');
  const links = directory.querySelector('.chapter-links');
  const items = Array.from(links.querySelectorAll('li'));
  const input = document.querySelector('#chapter-search');
  const locate = document.querySelector('#locate-current');
  const current = links.querySelector('.active');
  const empty = directory.querySelector('.chapter-empty');
  const count = directory.querySelector('.chapter-count');

  function fitDirectory() {
    if (!directory.open) return;
    // 桌面占满余下高度；手机目录展开后最多占半屏，避免遮住阅读内容。
    const available = smallScreen.matches ? Math.min(innerHeight * 0.48, 420) : innerHeight - links.getBoundingClientRect().top - 24;
    links.style.maxHeight = Math.max(64, available) + 'px';
  }

  function revealCurrent() {
    if (!current || !directory.open) return;
    const top = current.getBoundingClientRect().top - links.getBoundingClientRect().top;
    if (top < 0 || top + current.offsetHeight > links.clientHeight) {
      links.scrollTop += top - Math.max(12, (links.clientHeight - current.offsetHeight) / 2);
    }
  }

  function filterChapters() {
    const query = input.value.trim().toLocaleLowerCase();
    let visible = 0;
    items.forEach(item => {item.hidden = !item.textContent.toLocaleLowerCase().includes(query);if (!item.hidden) visible += 1;});
    empty.hidden = visible > 0;
    count.textContent = query ? visible + ' / ' + items.length + ' 篇' : items.length + ' 篇';
    fitDirectory();
  }

  function adaptDirectory() {
    directory.open = !smallScreen.matches;
    summary.tabIndex = smallScreen.matches ? 0 : -1;
    requestAnimationFrame(() => {fitDirectory();revealCurrent();});
  }

  directory.querySelector('.chapter-tools').hidden = false;
  input.addEventListener('input', () => {filterChapters();links.scrollTop = 0;});
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') {event.preventDefault();input.value = '';filterChapters();revealCurrent();}
  });
  locate.hidden = !current;
  locate.addEventListener('click', () => {input.value = '';directory.open = true;filterChapters();revealCurrent();current?.focus({preventScroll: true});});
  summary.addEventListener('click', event => {if (!smallScreen.matches) event.preventDefault();});
  directory.addEventListener('toggle', () => {requestAnimationFrame(() => {fitDirectory();revealCurrent();});});
  smallScreen.addEventListener('change', adaptDirectory);
  window.addEventListener('resize', fitDirectory);
  if (document.fonts?.ready) document.fonts.ready.then(() => {fitDirectory();revealCurrent();});
  adaptDirectory();
})();
