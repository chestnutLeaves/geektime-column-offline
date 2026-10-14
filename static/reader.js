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
  try {
    const saved = sessionStorage.getItem('library-course-return');
    if (saved) {
      const url = new URL(saved, location.origin);
      if (url.origin === location.origin && ['/', '/courses/index.html'].includes(url.pathname)) {
        document.querySelectorAll('.return-to-library, .switcher-link[data-section="courses"]').forEach(link => {link.href = url.pathname + url.search + url.hash;});
      }
    }
  } catch (_) { /* 存储不可用时保留标准书库链接。 */ }

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
