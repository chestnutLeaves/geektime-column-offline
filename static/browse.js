/* 浏览入口共用搜索和来源记录；原始链接与完整列表在禁用 JavaScript 时仍可访问。 */
(() => {
  'use strict';
  const returnKey = 'library-course-return';
  const browsePaths = new Set(['/', '/courses/index.html', '/articles/index.html', '/geektime/index.html', '/relationships/index.html', '/downloads/index.html']);

  function canonicalPath(pathname) {
    // 根首页的文件形式视为同一个入口，其他来源必须是明确的目录首页。
    return pathname === '/index.html' ? '/' : pathname;
  }

  function redirectLegacyHome() {
    const url = new URL(location.href);
    if (canonicalPath(url.pathname) !== '/') return false;
    const hadCourseFilter = ['q', 'category', 'sort'].some(key => url.searchParams.has(key));
    if (!hadCourseFilter && url.hash !== '#library') return false;
    // replace 避免后退时反复经过旧地址；筛选参数及定位锚点完整保留。
    url.pathname = '/courses/index.html';
    location.replace(url.pathname + url.search + url.hash);
    return true;
  }

  if (redirectLegacyHome()) return;
  if (!document.body.classList.contains('browse-page')) return;
  const main = document.querySelector('.browse-main');
  if (!main) return;
  const search = main.querySelector('#collection-search');
  const resultCount = main.querySelector('#collection-result-count');
  const empty = main.querySelector('#collection-empty');
  const items = Array.from(main.querySelectorAll('[data-browse-item]'));
  const groups = Array.from(main.querySelectorAll('section[data-browse-group]'));
  const searchableItems = items.map(item => ({item, text: (item.querySelector('.article-title') || item).textContent.toLocaleLowerCase()}));
  const canSearch = search && resultCount && empty;

  function filterCollection(updateAddress = false) {
    if (!canSearch) return;
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    searchableItems.forEach(({item, text}) => {
      item.hidden = !text.includes(query);
      if (!item.hidden) visible += 1;
    });
    // 分组整体收起会同时隐藏标题，避免搜索后留下没有内容的章节标题。
    groups.forEach(group => {
      group.hidden = !Array.from(group.querySelectorAll('[data-browse-item]')).some(item => !item.hidden);
    });
    resultCount.textContent = query ? '找到 ' + visible + ' / ' + items.length + ' 项' : '共 ' + items.length + ' 项';
    empty.hidden = visible > 0;
    if (updateAddress) {
      const params = new URLSearchParams(location.search);
      if (search.value.trim()) params.set('q', search.value.trim());
      else params.delete('q');
      const value = params.toString();
      history.replaceState(history.state, '', location.pathname + (value ? '?' + value : '') + location.hash);
    }
  }

  function restoreCollection() {
    if (redirectLegacyHome() || !canSearch) return;
    // 以 URL 为准覆盖浏览器自动恢复的输入值，前进、后退与重新加载使用同一筛选。
    search.value = new URLSearchParams(location.search).get('q') || '';
    filterCollection();
  }

  function rememberSource(event) {
    if (event.defaultPrevented || (event.type === 'auxclick' && event.button !== 1)) return;
    const link = event.target.closest?.('a[href]');
    if (!link || !main.contains(link)) return;
    try {
      const target = new URL(link.href, location.origin);
      if (target.origin !== location.origin || target.username || target.password) return;
      // 仅内容详情、专栏目录和 PDF 记录来源；分类切换、来源说明及外链不覆盖它。
      if (browsePaths.has(canonicalPath(target.pathname))) return;
      if (!/^\/(?:courses\/[^/]+\/[^/]+\.html|(?:articles|geektime|relationships)\/[^/]+\.html|downloads\/[^/]+\.pdf)$/.test(target.pathname)) return;
      const path = canonicalPath(location.pathname);
      if (!browsePaths.has(path)) return;
      const hash = path === '/courses/index.html' ? '#library' : location.hash;
      sessionStorage.setItem(returnKey, path + location.search + hash);
    } catch (_) { /* 禁用存储或无效链接不阻止正常阅读。 */ }
  }

  if (canSearch) {
    search.addEventListener('input', () => filterCollection(true));
    search.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        event.preventDefault();search.value = '';filterCollection(true);
      }
    });
    main.querySelectorAll('.collection-tools').forEach(control => {control.hidden = false;});
    restoreCollection();
  }
  main.addEventListener('click', rememberSource);
  main.addEventListener('auxclick', rememberSource);
  window.addEventListener('popstate', restoreCollection);
  window.addEventListener('pageshow', restoreCollection);
  window.addEventListener('hashchange', redirectLegacyHome);
})();
