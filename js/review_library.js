/* Static catalogue: no network calls, explicit filtering and incremental display. */
(function(root) {
  'use strict';
  function select(rows, query, category, level) {
    var q = String(query || '').trim().toLowerCase();
    return rows.filter(function(a) {
      return (!q || a.query.includes(q)) && (!category || a.category === category) &&
        (!level || (level === 'read' ? a.level !== 'metadata' : a.level === level));
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {select: select};
  if (!root.document) return;
  var doc = root.document;
  var panel = doc.getElementById('rm-view-reviews');
  if (!panel) return;
  var rows = Array.from(panel.querySelectorAll('.rv-card')).map(function(el) {
    return {element:el, query:el.dataset.query, category:el.dataset.category, level:el.dataset.level};
  });
  var query = doc.getElementById('rv-query'), category = doc.getElementById('rv-category');
  var level = doc.getElementById('rv-level'), count = doc.getElementById('rv-count');
  var more = doc.getElementById('rv-more'), limit = 12;
  function update(reset) {
    if (reset) limit = 12;
    var selected = select(rows, query.value, category.value, level.value);
    rows.forEach(function(a) {a.element.hidden = true;});
    selected.slice(0, limit).forEach(function(a) {a.element.hidden = false;});
    count.textContent = selected.length ? '找到 ' + selected.length + ' 项，显示 ' + Math.min(limit, selected.length) + ' 项。' : '没有匹配资料，可清除检索或切换主题。';
    more.hidden = selected.length <= limit;
  }
  query.addEventListener('input', function() {update(true);});
  [category, level].forEach(function(el) {el.addEventListener('change', function() {update(true);});});
  more.addEventListener('click', function() {limit += 12;update(false);});
  update(true);
})(typeof window !== 'undefined' ? window : globalThis);
