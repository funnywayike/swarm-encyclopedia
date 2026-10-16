/* 界面语言：中文 / English。
 *
 * 做法：页面本体是中文（构建产物），英文由运行时词典 data/i18n_en.json（构建成 js/i18n_en.js，只在英文模式下加载）翻译：
 *   ① 带 data-en 属性的元素：整个元素内容换成 data-en（页面标题、名称这类来自数据的文字）；
 *   ② 元素级：不含块级子元素的元素，整段文字（textContent，规整空白后）命中词典就整段替换；词典值可以带 <b>/<a> 标签（句子中间夹着加粗/链接的情况）；
 *   ③ 文本节点：规整后的文字命中词典就替换；再按 patterns（正则 → 模板）处理带数字的动态文字；
 *   ④ 属性 title / aria-label / placeholder / alt；
 *   ⑤ Canvas 的 fillText / strokeText 同样查词典；
 *   ⑥ MutationObserver：脚本之后动态生成的文字（状态栏、成绩表……）也会被翻译。
 * 命不中的文字保持中文；翻译完页面里仍有大段中文时，顶部显示一条说明。
 * 切换语言 = 记住选择 + 刷新页面（不需要还原）。
 * 默认语言：?lang=en|zh > 上次的选择 > 浏览器语言（非中文 → 英文）。
 */
(function () {
  "use strict";
  var CJK = /[㐀-鿿豈-﫿]/;
  var LANG = "zh";
  try {
    var q = /[?&]lang=(en|zh)\b/.exec(location.search);
    var saved = null;
    try { saved = localStorage.getItem("lang"); } catch (e) { /* 无存储也能用 */ }
    if (q) { LANG = q[1]; try { localStorage.setItem("lang", LANG); } catch (e) { /* ignore */ } }
    else if (saved === "en" || saved === "zh") LANG = saved;
    else LANG = /^zh/i.test(navigator.language || "zh") ? "zh" : "en";
  } catch (e) { LANG = "zh"; }

  var SRC = (document.currentScript && document.currentScript.src) || "";
  var root = document.documentElement;
  root.setAttribute("data-lang", LANG);
  if (LANG === "en") { root.classList.add("lang-en"); root.setAttribute("lang", "en"); }

  var dict = null, patterns = [];
  function norm(s) { return s.replace(/\s+/g, " ").trim(); }

  // seg=true：文本节点 / 属性 / canvas 文字允许「按 · 拆段、部分翻译」；整个元素的 textContent 不允许
  // （否则「名称 + 角标」这种元素会被拆得只译一半，而不是退回去逐个子节点翻译）
  function lookup(zh, seg) {
    if (!dict || !zh || !CJK.test(zh)) return null;
    var k = norm(zh);
    if (Object.prototype.hasOwnProperty.call(dict, k)) return dict[k];
    for (var i = 0; i < patterns.length; i++) {
      var m = patterns[i][0].exec(k);
      if (m) {
        return patterns[i][1].replace(/\$(\d)/g, function (_, n) {
          var g = m[+n] || "";
          // 捕获组里的文字也查词典（可以嵌套：名称 + 编码后缀 + 方向后缀）
          var t = lookup(g);
          return t === null ? g : t;
        });
      }
    }
    // 状态栏这类「甲 · 乙 · 丙」的组合文字：按 " · " 拆开逐段翻译，只要有一段命中就算成功
    if (seg && k.indexOf(" · ") > 0) {
      var parts = k.split(" · "), hit = false;
      var out = parts.map(function (p) {
        var t = lookup(p, true);
        if (t !== null) { hit = true; return t; }
        return p;
      });
      if (hit) return out.join(" · ");
    }
    return null;
  }

  // 词典值里的站内链接统一写成 /problem/x/ ，替换进页面时还原成站点根的绝对地址。
  var SITE_ROOT = SRC.replace(/js\/i18n\.js(\?.*)?$/, "");
  function uncanon(h) { return h.replace(/(href|src)="\/(?!\/)/g, function (_, a) { return a + '="' + SITE_ROOT; }); }

  // 词典值里不带属性的标签（<a>、<b>、<span>…）沿用页面上原来的同名元素（保留 id、href、事件和脚本里持有的引用），
  // 只替换里面的文字；带属性的标签（<a href="/x/">）按词典值新建。
  function adopt(el, html) {
    var orig = {};
    [].forEach.call(el.querySelectorAll("*"), function (o) { (orig[o.tagName] = orig[o.tagName] || []).push(o); });
    var tpl = document.createElement("template");
    tpl.innerHTML = uncanon(html);
    var used = {};
    [].forEach.call(tpl.content.querySelectorAll("*"), function (n) {
      var t = n.tagName, i = used[t] || 0;
      used[t] = i + 1;
      var o = orig[t] && orig[t][i];
      if (o && n.attributes.length === 0) {
        while (o.firstChild) o.removeChild(o.firstChild);
        while (n.firstChild) o.appendChild(n.firstChild);
        n.parentNode.replaceChild(o, n);
      }
    });
    el.innerHTML = "";
    el.appendChild(tpl.content);
  }

  var SKIP = { SCRIPT: 1, STYLE: 1, CODE: 1, PRE: 1, SVG: 1, CANVAS: 1, TEXTAREA: 1, NOSCRIPT: 1 };
  var BLOCK = "p,div,ul,ol,li,table,thead,tbody,tr,h1,h2,h3,h4,h5,h6,section,details,summary,blockquote,form,pre";

  function translateAttrs(el) {
    var names = ["title", "aria-label", "placeholder", "alt"];
    for (var i = 0; i < names.length; i++) {
      var v = el.getAttribute && el.getAttribute(names[i]);
      if (v && CJK.test(v)) {
        var t = lookup(v, true);
        if (t !== null) el.setAttribute(names[i], t);
      }
    }
  }

  function translateText(node) {
    var raw = node.nodeValue;
    if (!raw || !CJK.test(raw)) return;
    var t = lookup(raw, true);
    if (t === null) return;
    var lead = /^\s*/.exec(raw)[0], tail = /\s*$/.exec(raw)[0];
    node.nodeValue = lead + t + tail;
  }

  // 「一句话」容器：直接含有文字（不只是 · 之类的分隔符），或者最多只有一个子元素；
  // 纯由多个 <a>/<span> 并排组成的菜单、徽章行不算——它们逐个子元素翻译。
  var WORD = /[A-Za-z㐀-鿿]/;
  function isUnit(el) {
    var elems = 0;
    for (var c = el.firstChild; c; c = c.nextSibling) {
      if (c.nodeType === 3 && WORD.test(c.nodeValue)) return true;
      if (c.nodeType === 1) elems++;
    }
    return elems <= 1;
  }

  function walk(el) {
    if (el.nodeType === 3) { translateText(el); return; }
    if (el.nodeType !== 1 || SKIP[el.tagName]) return;
    if (el.hasAttribute("data-no-i18n")) return;
    translateAttrs(el);
    var en = el.getAttribute("data-en");
    if (en !== null && en !== "") { el.innerHTML = en; el.removeAttribute("data-en"); return; }
    if (CJK.test(el.textContent || "") && !el.querySelector(BLOCK) && isUnit(el)) {
      var t = lookup(el.textContent);
      if (t !== null) {
        if (t.indexOf("<") >= 0) adopt(el, t); else el.textContent = t;
        return;
      }
    }
    for (var c = el.firstChild; c; c = c.nextSibling) walk(c);
  }

  var pending = false;
  function translateAll() {
    pending = false;
    if (!dict) return;
    walk(document.body);
    var ti = document.querySelector("title");
    if (ti) {
      var te = ti.getAttribute("data-en");
      if (te) { document.title = te; } else { var tt = lookup(ti.textContent); if (tt !== null) document.title = tt; }
    }
    banner();
  }

  function banner() {
    if (document.getElementById("zhOnlyNote")) return;
    var main = document.getElementById("main") || document.querySelector("main") || document.body;
    var txt = main.textContent || "", n = 0;
    for (var i = 0; i < txt.length && n < 400; i++) if (CJK.test(txt.charAt(i))) n++;
    if (n < 400) return;
    var d = document.createElement("div");
    d.id = "zhOnlyNote";
    d.className = "zh-only-note";
    d.setAttribute("lang", "en");
    d.textContent = "The interface is in English, but the detailed explanations on this page are written in Chinese only. " +
      "The English summary is at the top where available.";
    main.insertBefore(d, main.firstChild);
  }

  function schedule() {
    if (pending) return;
    pending = true;
    // 用 setTimeout 而不是 requestAnimationFrame：页面在后台标签页时 rAF 不触发，译文会停在中文
    setTimeout(translateAll, 40);
  }

  function patchCanvas() {
    var P = window.CanvasRenderingContext2D && CanvasRenderingContext2D.prototype;
    if (!P || P.__i18n) return;
    ["fillText", "strokeText"].forEach(function (name) {
      var orig = P[name];
      P[name] = function (text) {
        if (typeof text === "string" && CJK.test(text)) {
          var t = lookup(text, true);
          if (t !== null) arguments[0] = t;
        }
        return orig.apply(this, arguments);
      };
    });
    P.__i18n = true;
  }

  function start() {
    var btn = document.getElementById("langToggle");
    if (btn) {
      btn.textContent = LANG === "en" ? "中" : "EN";
      btn.title = LANG === "en" ? "切换到中文 / Switch to Chinese" : "Switch to English / 切换到英文";
      btn.onclick = function () {
        try { localStorage.setItem("lang", LANG === "en" ? "zh" : "en"); } catch (e) { /* ignore */ }
        var u = location.href.replace(/([?&])lang=(en|zh)&?/, "$1").replace(/[?&]$/, "");
        location.href = u;
      };
    }
    if (LANG !== "en") return;
    patchCanvas();
    var s = document.createElement("script");
    s.src = SRC.replace(/i18n\.js(\?.*)?$/, "i18n_en.js");
    s.onload = function () {
      var d = window.I18N_EN || {};
      dict = {};
      patterns = (d.patterns || []).map(function (p) { return [new RegExp(p[0]), p[1]]; });
      // 词典键里的 {n}（一串数字）/ {*}（任意文字）是占位符：键 → 正则；值里的 {n} / {*} 依次换成捕获内容，{1}…{9} 按编号取
      var S = d.strings || {};
      Object.keys(S).forEach(function (k) {
        if (k.indexOf("{n}") < 0 && k.indexOf("{*}") < 0) { dict[k] = S[k]; return; }
        var re = new RegExp("^" + k.replace(/[.*+?^$()|[\]\\]/g, "\\$&")
          .replace(/\{n\}/g, "(\\d+(?:\\.\\d+)?)").replace(/\{\\\*\}/g, "(.+?)") + "$");
        var i = 0;
        patterns.push([re, S[k].replace(/\{(n|\*|\d)\}/g, function (_, t) { return "$" + (/\d/.test(t) ? t : ++i); })]);
      });
      translateAll();
      new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true, characterData: true });
      window.addEventListener("themechange", schedule);
    };
    document.head.appendChild(s);
  }

  window.I18N = { lang: LANG, t: function (zh) { var r = lookup(zh, true); return r === null ? zh : r; } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
