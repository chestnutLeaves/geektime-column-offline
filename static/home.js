/* 搜索、分类、排序都在本地执行，发布时间未知的专栏始终排在时间列表末尾。 */
(() => {
  const grid = document.querySelector('#course-grid');
  if (!grid) return;
  const cards = Array.from(grid.querySelectorAll('.course-card'));
  const input = document.querySelector('#course-search');
  const sortButton = document.querySelector('#course-sort');
  const sortMenu = document.querySelector('#sort-options');
  const sortOptions = Array.from(sortMenu.querySelectorAll('[data-sort]'));
  const categories = Array.from(document.querySelectorAll('.category-button'));
  const quickButtons = Array.from(document.querySelectorAll('[data-query]'));
  const clear = document.querySelector('#clear-filters');
  const more = document.querySelector('#load-more');
  const library = document.querySelector('#library');
  const pageSize = 24;
  let category = 'all';
  let sortValue = 'date';
  let visibleLimit = pageSize;
  let filtered = [];

  function render() {
    const query = input.value.trim().toLocaleLowerCase();
    filtered = cards.filter(card => (category === 'all' || card.dataset.category === category) && card.dataset.search.includes(query));
    if (sortValue === 'date') {
      // 仅比较明确时间；月份已知的条目在对应月末，只有年份的条目在该年末，不将估算线索参与排序。
      filtered.sort((a, b) => Number(b.dataset.year) - Number(a.dataset.year) || b.dataset.published.localeCompare(a.dataset.published));
    }
    if (sortValue === 'name') filtered.sort((a, b) => a.dataset.title.localeCompare(b.dataset.title, 'zh-CN', {numeric: true}));
    if (sortValue === 'count') filtered.sort((a, b) => Number(b.dataset.count) - Number(a.dataset.count));
    cards.forEach(card => {card.hidden = true;});
    filtered.forEach((card, index) => {grid.append(card);card.hidden = index >= visibleLimit;});
    document.querySelector('#result-count').textContent = String(filtered.length);
    categories.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.category === category)));
    quickButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.query.toLowerCase() === query)));
    const selected = categories.find(button => button.dataset.category === category);
    document.querySelector('#library-title').firstChild.textContent = (category === 'all' ? '技术专栏' : selected.dataset.label) + ' ';
    document.querySelector('.library-hint').textContent = sortValue === 'date' ? '按发布时间从新到旧 · 未知时间排最后' : '选一个专栏，开始今天的阅读';
    document.querySelector('#empty-state').hidden = filtered.length > 0;
    grid.hidden = filtered.length === 0;
    clear.hidden = !query && category === 'all';
    document.querySelector('.load-area').hidden = filtered.length === 0;
    document.querySelector('#shown-count').textContent = '已展示 ' + Math.min(visibleLimit, filtered.length) + ' / ' + filtered.length + ' 个专栏';
    more.hidden = visibleLimit >= filtered.length;
    const currentSort = sortOptions.find(option => option.dataset.sort === sortValue);
    document.querySelector('#sort-label').textContent = currentSort.dataset.label;
    sortButton.setAttribute('aria-label', '排序：' + currentSort.dataset.label);
    sortOptions.forEach(option => option.setAttribute('aria-selected', String(option === currentSort)));
    const params = new URLSearchParams();
    if (input.value.trim()) params.set('q', input.value.trim());
    if (category !== 'all') params.set('category', category);
    if (sortValue !== 'date') params.set('sort', sortValue);
    const search = params.toString();
    history.replaceState(history.state, '', location.pathname + (search ? '?' + search : '') + location.hash);
  }

  function restore(resetLimit = true) {
    const params = new URLSearchParams(location.search);
    input.value = params.get('q') || '';
    category = categories.some(button => button.dataset.category === params.get('category')) ? params.get('category') : 'all';
    // 旧版 default 和无效参数统一回到发布时间排序。
    sortValue = ['name', 'count'].includes(params.get('sort')) ? params.get('sort') : 'date';
    if (resetLimit) visibleLimit = pageSize;
    render();
  }

  function closeSort(returnFocus = false) {
    sortMenu.hidden = true;
    sortButton.setAttribute('aria-expanded', 'false');
    if (returnFocus) sortButton.focus({preventScroll: true});
  }

  function openSort(index) {
    sortMenu.hidden = false;
    sortButton.setAttribute('aria-expanded', 'true');
    const selected = index ?? sortOptions.findIndex(option => option.dataset.sort === sortValue);
    sortOptions[selected].focus({preventScroll: true});
  }

  function reset() {
    input.value = '';
    category = 'all';
    visibleLimit = pageSize;
    render();
    input.focus({preventScroll: true});
  }

  input.addEventListener('input', () => {visibleLimit = pageSize;render();});
  sortButton.addEventListener('click', () => sortMenu.hidden ? openSort() : closeSort());
  sortButton.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();openSort(event.key === 'ArrowUp' ? sortOptions.length - 1 : undefined);
    }
  });
  sortOptions.forEach(option => option.addEventListener('click', () => {
    sortValue = option.dataset.sort;visibleLimit = pageSize;render();closeSort(true);
  }));
  sortMenu.addEventListener('keydown', event => {
    const index = sortOptions.indexOf(document.activeElement);
    const next = {ArrowDown: (index + 1) % sortOptions.length, ArrowUp: (index - 1 + sortOptions.length) % sortOptions.length, Home: 0, End: sortOptions.length - 1};
    if (event.key in next) {event.preventDefault();sortOptions[next[event.key]].focus();}
    if (event.key === 'Escape') {event.preventDefault();closeSort(true);}
  });
  document.addEventListener('pointerdown', event => {if (!event.target.closest('.sort-field')) closeSort();});
  document.addEventListener('focusin', event => {if (!event.target.closest('.sort-field')) closeSort();});
  categories.forEach(button => button.addEventListener('click', () => {
    category = button.dataset.category;visibleLimit = pageSize;render();
    library.scrollIntoView({block: 'start', behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  }));
  quickButtons.forEach(button => button.addEventListener('click', () => {input.value = button.dataset.query;category = 'all';visibleLimit = pageSize;render();}));
  clear.addEventListener('click', reset);
  document.querySelector('#reset-search').addEventListener('click', reset);
  more.addEventListener('click', () => {
    const firstNew = filtered[visibleLimit];visibleLimit += pageSize;render();
    firstNew?.querySelector('.course-link').focus({preventScroll: true});
  });
  // 来源由 browse.js 统一记录，避免把总首页的最近阅读误写成专栏入口。
  document.addEventListener('keydown', event => {
    const typing = event.target.closest('input, textarea, select, [contenteditable]');
    if (event.key === '/' && !typing && !event.ctrlKey && !event.metaKey && !event.altKey) {event.preventDefault();closeSort();input.focus();}
    if (event.key === 'Escape' && document.activeElement === input) {input.value = '';visibleLimit = pageSize;render();}
    if (event.key === 'Escape' && !sortMenu.hidden) closeSort(true);
  });
  window.addEventListener('popstate', () => restore());
  window.addEventListener('pageshow', event => {
    // 后退命中页面缓存时，以地址栏恢复筛选，并保留此前展开的卡片数量。
    if (event.persisted) {closeSort();restore(false);}
  });
  document.querySelectorAll('.toolbar, .quick-search, .category-section').forEach(element => {element.hidden = false;});
  restore();
})();
