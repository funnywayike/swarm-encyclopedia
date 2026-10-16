(() => {
  "use strict";
  const currentScript = document.currentScript;
  if (!currentScript || !currentScript.src) return;
  const indexUrl = new URL("../search-index.json", currentScript.src);
  const nav = document.querySelector(".nav-links");
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "site-search-open";
  trigger.setAttribute("aria-label", "搜索站内内容");
  trigger.title = "搜索站内内容（Ctrl/⌘ K）";
  trigger.innerHTML = '<span aria-hidden="true">⌕</span><span>搜索</span><kbd>Ctrl K</kbd>';
  if (nav) nav.appendChild(trigger);

  const dialog = document.createElement("dialog");
  dialog.className = "site-search-dialog";
  dialog.setAttribute("aria-labelledby", "site-search-title");
  dialog.innerHTML =
    '<div class="site-search-shell">' +
      '<div class="site-search-head"><h2 id="site-search-title">搜索百科内容</h2>' +
      '<button type="button" class="site-search-close" aria-label="关闭搜索">关闭 <kbd>Esc</kbd></button></div>' +
      '<div class="site-search-field"><input type="search" id="site-search-input" autocomplete="off" ' +
      'placeholder="搜索算法、问题、论文、团队或关键词…" aria-label="输入搜索关键词">' +
      '<p class="site-search-help">支持中文、英文名称和缩写；英文搜索不区分大小写。输入多个词可缩小范围。</p></div>' +
      '<p class="site-search-status" role="status" aria-live="polite">正在准备全站搜索…</p>' +
      '<div class="site-search-results" role="listbox" aria-label="搜索结果"></div>' +
    '</div>';
  document.body.appendChild(dialog);

  const input = dialog.querySelector("#site-search-input");
  const status = dialog.querySelector(".site-search-status");
  const results = dialog.querySelector(".site-search-results");
  let indexPromise = null;
  let items = [];

  const normalize = (value) => String(value || "")
    .normalize("NFKC")
    .toLocaleLowerCase("en-US")
    .replace(/\s+/g, " ")
    .trim();

  function ensureIndex() {
    if (!indexPromise) {
      indexPromise = fetch(indexUrl.href, { cache: "force-cache" })
        .then((response) => {
          if (!response.ok) throw new Error("index unavailable");
          return response.json();
        })
        .then((data) => {
          items = (data.items || []).map((item) => ({
            ...item,
            _title: normalize(item.title),
            _text: normalize(item.text),
            _summary: normalize(item.summary),
          }));
          return items;
        });
    }
    return indexPromise;
  }

  function snippet(item, terms) {
    const source = item.text || item.summary || "";
    const folded = source.toLocaleLowerCase("en-US");
    let position = -1;
    for (const term of terms) {
      const at = folded.indexOf(term);
      if (at >= 0 && (position < 0 || at < position)) position = at;
    }
    if (position < 0) return source.slice(0, 170);
    const start = Math.max(0, position - 62);
    const end = Math.min(source.length, position + 112);
    return (start ? "…" : "") + source.slice(start, end) + (end < source.length ? "…" : "");
  }

  function showEmpty(message) {
    results.replaceChildren();
    const empty = document.createElement("div");
    empty.className = "site-search-empty";
    empty.textContent = message;
    results.appendChild(empty);
  }

  function render(query) {
    const normalized = normalize(query);
    if (!normalized) {
      status.textContent = "搜索覆盖站内页面和研究案例。";
      showEmpty("输入关键词开始查找。");
      return;
    }
    if (!items.length) {
      status.textContent = "正在读取索引…";
      ensureIndex().then(() => render(query)).catch(() => {
        status.textContent = "搜索索引暂时无法读取。";
        showEmpty("请通过网站地址或本地服务器打开页面后重试。");
      });
      return;
    }
    const terms = normalized.split(" ").filter(Boolean);
    const ranked = [];
    for (const item of items) {
      const searchable = item._title + " " + item._summary + " " + item._text;
      if (!terms.every((term) => searchable.includes(term))) continue;
      let score = item._title.includes(normalized) ? 500 : 0;
      for (const term of terms) {
        if (item._title.includes(term)) score += 100;
        if (item._summary.includes(term)) score += 24;
        if (item._text.includes(term)) score += 4;
      }
      ranked.push({ item, score });
    }
    ranked.sort((a, b) => b.score - a.score || a.item.title.localeCompare(b.item.title, "zh-CN"));
    const unique = [];
    const seen = new Set();
    for (const match of ranked) {
      if (seen.has(match.item.url)) continue;
      seen.add(match.item.url);
      unique.push(match.item);
      if (unique.length === 15) break;
    }
    status.textContent = unique.length
      ? "找到 " + ranked.length + " 条相关内容，显示最相关的 " + unique.length + " 条。"
      : "没有找到匹配内容。";
    results.replaceChildren();
    if (!unique.length) {
      showEmpty("试试算法缩写、中文名称，或把关键词缩短一些。");
      return;
    }
    const rootPath = new URL(".", indexUrl).pathname;
    for (const item of unique) {
      const href = new URL(item.url, indexUrl);
      if (href.origin !== location.origin || !href.pathname.startsWith(rootPath)) continue;
      const link = document.createElement("a");
      link.className = "site-search-result";
      link.href = href.href;
      link.setAttribute("role", "option");
      const title = document.createElement("b");
      title.textContent = item.title;
      const category = document.createElement("small");
      category.textContent = item.category || "站内内容";
      const summary = document.createElement("span");
      summary.textContent = snippet(item, terms);
      link.append(title, category, summary);
      results.appendChild(link);
    }
  }

  function openSearch() {
    if (!dialog.open) dialog.showModal();
    input.focus();
    ensureIndex().then(() => render(input.value)).catch(() => {
      status.textContent = "搜索索引暂时无法读取。";
      showEmpty("请通过网站地址或本地服务器打开页面后重试。");
    });
  }

  trigger.addEventListener("click", openSearch);
  dialog.querySelector(".site-search-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  input.addEventListener("input", () => {
    if (!items.length) {
      ensureIndex().then(() => render(input.value)).catch(() => {
        status.textContent = "搜索索引暂时无法读取。";
        showEmpty("请通过网站地址或本地服务器打开页面后重试。");
      });
    } else {
      render(input.value);
    }
  });
  document.addEventListener("keydown", (event) => {
    const target = event.target;
    const editing = target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearch();
    } else if (event.key === "/" && !editing && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      openSearch();
    }
  });

  const params = new URLSearchParams(location.search);
  const requestedView = params.get("view");
  if (requestedView) {
    const tab = Array.from(document.querySelectorAll(".rm-tab"))
      .find((button) => button.dataset.view === requestedView);
    if (tab) tab.click();
  }
  const requestedNode = params.get("node");
  const requestedAnchor = decodeURIComponent(location.hash.slice(1));
  requestAnimationFrame(() => {
    if (requestedNode) {
      const node = Array.from(document.querySelectorAll("[data-node]"))
        .find((button) => button.dataset.node === requestedNode);
      if (node) node.click();
    }
    const target = requestedAnchor && document.getElementById(requestedAnchor);
    if (target) target.scrollIntoView({ block: "start", behavior: "smooth" });
  });
})();
