/* 两类目录各加载一份静态点评；所有文案以文本节点渲染，不执行 JSON 中的 HTML。 */
(() => {
  'use strict';
  const source = document.body.dataset.reviewSource;
  if (!source) return;
  const targets = [...document.querySelectorAll('[data-review-key]')];
  if (!targets.length) return;
  const recommendations = {recommended: '值得阅读', selective: '按需阅读', reference: '历史参考', uncertain: '待进一步核验'};
  const currencies = {stable: '原理为主', mixed: '部分需更新', dated: '实操偏旧', contextual: '有时代背景', unknown: '时效待核验'};
  let request, active = null, pinned = false, sequence = 0, showTimer, hideTimer, suppressFocus = false;
  const panel = document.createElement('section');
  panel.id = 'reading-review';
  panel.className = 'review-popover';
  panel.hidden = true;
  panel.tabIndex = -1;
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-modal', 'false');
  panel.setAttribute('aria-labelledby', 'review-title');
  panel.setAttribute('aria-describedby', 'review-summary');
  document.body.append(panel);

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function load() {
    // 单页共享请求；失败后清空 Promise，下一次打开或点击重试可重新获取。
    if (!request) {
      request = fetch(source, {cache: 'no-cache', credentials: 'same-origin'})
        .then(response => {
          if (!response.ok) throw new Error('点评资源不可用');
          return response.json();
        }).then(data => {
          if (data.schema_version !== 1 || !Array.isArray(data.entries) || typeof data.methodology !== 'string') throw new Error('点评格式不兼容');
          const entries = new Map();
          for (const entry of data.entries) {
            if (typeof entry.path !== 'string' || entries.has(entry.path)) throw new Error('点评路径重复或无效');
            entries.set(entry.path, entry);
          }
          return {...data, entries};
        }).catch(error => { request = null; throw error; });
    }
    return request;
  }

  function close(restoreFocus = false) {
    clearTimeout(showTimer);
    clearTimeout(hideTimer);
    sequence += 1;
    const button = active?.querySelector('.review-trigger');
    button?.setAttribute('aria-expanded', 'false');
    active = null;
    pinned = false;
    panel.hidden = true;
    if (restoreFocus && button) {
      // Escape 返回触发按钮时，不再由 focusin 立即重新打开。
      suppressFocus = true;
      button.focus({preventScroll: true});
      suppressFocus = false;
    }
  }

  function position() {
    if (!active || panel.hidden) return;
    const margin = 12, gap = 10;
    const width = document.documentElement.clientWidth;
    const height = window.innerHeight;
    const anchor = active.getBoundingClientRect();
    const box = panel.getBoundingClientRect();
    let left, top;
    if (width <= 600) {
      left = margin;
      top = height - box.height - margin;
    } else {
      left = anchor.right + gap;
      top = anchor.top;
      if (left + box.width > width - margin) {
        if (anchor.left - box.width - gap >= margin) left = anchor.left - box.width - gap;
        else {
          left = anchor.left;
          top = anchor.bottom + gap;
          if (top + box.height > height - margin) top = anchor.top - box.height - gap;
        }
      }
    }
    panel.style.left = Math.max(margin, Math.min(left, width - box.width - margin)) + 'px';
    panel.style.top = Math.max(margin, Math.min(top, height - box.height - margin)) + 'px';
  }

  function shell(title, message) {
    panel.replaceChildren();
    const top = element('div', 'review-popover-top');
    top.append(element('span', 'review-eyebrow', '阅读点评'));
    const dismiss = element('button', 'review-close', '关闭');
    dismiss.type = 'button';
    dismiss.setAttribute('aria-label', '关闭阅读点评');
    dismiss.addEventListener('click', () => close(true));
    top.append(dismiss);
    const heading = element('h2', '', title);
    heading.id = 'review-title';
    const summary = element('p', '', message);
    summary.id = 'review-summary';
    panel.append(top, heading, summary);
    return summary;
  }

  function safeLink(url, external) {
    if (typeof url !== 'string') return null;
    try {
      // 本地证据只允许内容页；外部资料只接受 HTTPS，拒绝脚本和协议相对地址。
      if (!external && !/^\/(?:courses|articles|geektime)\/[^?#]+\.html$/.test(url)) return null;
      const parsed = new URL(url, location.origin);
      if (parsed.username || parsed.password) return null;
      if (external ? parsed.protocol !== 'https:' : parsed.origin !== location.origin) return null;
      return parsed.href;
    } catch (_) { return null; }
  }

  function render(data, entry) {
    if (!entry || !recommendations[entry.recommendation] || !currencies[entry.currency] ||
        !['title', 'summary', 'currency_note', 'reading_advice'].every(key => typeof entry[key] === 'string' && entry[key].trim())) {
      shell(active.dataset.title || active.querySelector('.article-title')?.textContent || '阅读点评', '这项内容暂未完成点评，你仍可正常打开阅读。');
      return;
    }
    const summary = shell(entry.title, entry.summary);
    const badges = element('div', 'review-badges');
    const rating = element('span', 'review-badge', recommendations[entry.recommendation]);
    rating.dataset.tone = entry.recommendation === 'recommended' ? 'positive' : entry.recommendation === 'uncertain' ? 'neutral' : 'caution';
    const currency = element('span', 'review-badge', currencies[entry.currency]);
    currency.dataset.tone = entry.currency === 'stable' ? 'positive' : entry.currency === 'unknown' ? 'neutral' : 'caution';
    badges.append(rating, currency);
    summary.before(badges);
    const details = element('dl');
    details.append(element('dt', '', '时效判断'), element('dd', '', entry.currency_note), element('dt', '', '怎么读'), element('dd', '', entry.reading_advice));
    panel.append(details);
    const evidence = element('details', 'review-evidence');
    evidence.append(element('summary', '', '查看点评依据与范围'), element('p', '', data.methodology));
    const links = element('ul');
    function appendLink(item, external) {
      const href = safeLink(external ? item?.url : item?.path, external);
      if (!href || typeof item?.title !== 'string') return;
      const li = element('li');
      const link = element('a', '', item.title);
      link.href = href;
      if (external) { link.target = '_blank'; link.rel = 'noopener noreferrer'; }
      li.append(link); links.append(li);
    }
    if (Array.isArray(entry.evidence)) entry.evidence.forEach(item => appendLink(item, false));
    if (Array.isArray(entry.reference_ids)) entry.reference_ids.forEach(id => appendLink(data.references?.[id], true));
    evidence.append(links);
    evidence.addEventListener('toggle', position);
    panel.append(evidence, element('small', 'review-date', `${data.reviewer || '编辑点评'} · ${data.reviewed_at || '日期未标注'} · 基于内容摘样`));
  }

  async function open(target, pin = false, moveFocus = false) {
    clearTimeout(showTimer); clearTimeout(hideTimer);
    if (active === target && !panel.hidden) {
      pinned ||= pin;
      if (moveFocus) panel.focus({preventScroll: true});
      return;
    }
    active?.querySelector('.review-trigger')?.setAttribute('aria-expanded', 'false');
    active = target;
    pinned = pin;
    const revision = ++sequence;
    active.querySelector('.review-trigger')?.setAttribute('aria-expanded', 'true');
    shell(target.dataset.title || target.querySelector('.article-title')?.textContent || '阅读点评', '正在加载点评…');
    panel.hidden = false;
    panel.scrollTop = 0;
    position();
    if (moveFocus) panel.focus({preventScroll: true});
    try {
      const data = await load();
      if (revision !== sequence) return;
      render(data, data.entries.get(target.dataset.reviewKey));
    } catch (_) {
      if (revision !== sequence) return;
      shell('点评暂时无法加载', '阅读入口仍然可用。请稍后重试，或检查静态点评文件是否已一起部署。');
      const retry = element('button', 'review-retry', '重试加载');
      retry.type = 'button';
      retry.addEventListener('click', () => { close(); open(target, true, true); });
      panel.append(retry);
    }
    position();
  }

  function scheduleClose() {
    clearTimeout(showTimer);
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      if (!pinned && !panel.matches(':hover') && !active?.matches(':hover') &&
          !panel.contains(document.activeElement) && !active?.contains(document.activeElement)) close();
    }, 220);
  }

  targets.forEach(target => {
    const trigger = target.querySelector('.review-trigger');
    if (!trigger) return;
    trigger.hidden = false;
    target.addEventListener('pointerenter', event => {
      if (event.pointerType === 'touch' || pinned) return;
      clearTimeout(hideTimer); clearTimeout(showTimer);
      showTimer = setTimeout(() => open(target), 240);
    });
    target.addEventListener('pointerleave', scheduleClose);
    target.addEventListener('focusin', event => {
      if (!suppressFocus && !pinned && event.target.matches(':focus-visible')) open(target);
    });
    target.addEventListener('focusout', scheduleClose);
    trigger.addEventListener('click', () => {
      if (active === target && pinned) close();
      else open(target, true, true);
    });
  });
  panel.addEventListener('pointerenter', () => clearTimeout(hideTimer));
  panel.addEventListener('pointerleave', scheduleClose);
  panel.addEventListener('focusout', () => {
    setTimeout(() => {
      if (!panel.hidden && !panel.contains(document.activeElement) && !active?.contains(document.activeElement)) close();
    }, 0);
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !panel.hidden) {
      event.preventDefault(); event.stopPropagation(); close(panel.contains(document.activeElement));
    }
  }, true);
  document.addEventListener('click', event => {
    // 重试会替换浮层子节点，使用原始事件路径，避免把已移除按钮误当外部点击。
    const path = event.composedPath();
    if (active && !path.includes(active) && !path.includes(panel)) close();
  });
  document.addEventListener('input', () => close());
  document.addEventListener('change', () => close());
  document.addEventListener('scroll', event => {
    if (!panel.contains(event.target)) close();
  }, true);
  window.addEventListener('resize', () => close());
  window.addEventListener('pagehide', () => close());
  // 预加载不阻塞任何原始链接；错误在用户主动查看时以可重试状态呈现。
  load().catch(() => {});
})();
