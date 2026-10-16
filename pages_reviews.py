"""Static, escaped review evidence panel for the local research map."""
import html
import json
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parent
def load(name):
    return json.loads((ROOT / 'data' / name).read_text(encoding='utf-8'))
def esc(value):
    return html.escape(str(value), quote=True)
def render_review_panel():
    library = load('review_library.json')
    cross = load('review_crosschecks.json')
    coverage = load('review_coverage.json')
    articles = sorted(library['articles'], key=lambda a: ({'sections':0,'abstract':1,'metadata':2}[a['readingLevel']], a['category'], str(a['year'])))
    refs = {a['id']: a for a in articles}
    counts = Counter(a['readingLevel'] for a in articles)
    def source(a):
        return '<a target="_blank" rel="noopener noreferrer" href="' + esc(a['url']) + '">' + esc(a['title']) + '</a>'
    checks = []
    for c in cross['checks']:
        evidence = ''.join('<li>' + source(refs[e['source']]) + ' · ' + esc(e['location']) + '<p>' + esc(e['finding']) + '</p></li>' for e in c['evidence'])
        checks.append('<details class="rv-check"><summary>' + esc(c['title']) + ' <span class="hint">' + esc(c['status']) + '</span></summary><p>' + esc(c['conclusion']) + '</p><p class="hint">独立性与边界：' + esc(c['independence']) + '</p><ol>' + evidence + '</ol></details>')
    cards = []
    for a in articles:
        authors = '、'.join(a['authors']) or '请见原始记录'
        query = ' '.join([a['title'], authors, a['category'], a['doi'], str(a['year'])]).lower()
        location = esc(a['readingLocation'])
        if a.get('readingURL'):
            location = '<a target="_blank" rel="noopener noreferrer" href="' + esc(a['readingURL']) + '">' + location + '</a>'
        cards.append('<article class="rv-card" data-category="' + esc(a['category']) + '" data-level="' + esc(a['readingLevel']) + '" data-query="' + esc(query) + '"><p class="hint">' + esc(a['category']) + ' · ' + esc(a['year']) + ' · ' + esc(a['readingLabel']) + '</p><h3>' + source(a) + '</h3><p class="hint">' + esc(authors) + '</p><p>' + esc(a['scopeNote']) + '</p><details><summary>书目与阅读位置</summary><p>' + esc(a['journal'] or a['kind']) + '</p><p>DOI：' + esc(a['doi'] or '无 DOI；使用原始记录链接') + '</p><p>' + location + '</p></details></article>')
    coverage_rows = []
    for t in coverage['topics']:
        links = '；'.join(source(refs[s]) for s in t['sourceIDs'])
        coverage_rows.append('<tr><th scope="row">' + esc(t['title']) + '<br><span class="hint">' + esc(t['ring']) + '</span></th><td>' + str(len(t['sourceIDs'])) + ' / ' + str(t['readCount']) + '</td><td>' + esc(t['status']) + '<p>' + esc(t['remaining']) + '</p><details><summary>本主题来源</summary>' + links + '</details></td></tr>')
    coverage_html = '<div class="rm-intro"><h2>资料够完整了吗？先看覆盖与缺口</h2><p>目前仍是可扩展的研究资料集。42 个主题分别检查资料、内容核读与具体议题核对；收录篇数不会自动转成完成率。</p><p>补检新增32组主题查询、480条候选，逐项筛选后补入目录。<a href="../../docs/review-coverage-audit-2026-10-16.md">查看覆盖检查报告</a> · <a href="../../docs/review-evidence/2026-10-16/coverage-matrix.csv" download>下载覆盖表</a></p><details><summary>展开42个主题：资料数 / 已核读数，以及待补工作</summary><div class="rv-table-wrap"><table class="rv-coverage"><thead><tr><th>主题与范围</th><th>资料 / 核读</th><th>状态与缺口</th></tr></thead><tbody>' + ''.join(coverage_rows) + '</tbody></table></div></details></div>'
    options = ''.join('<option>' + esc(c) + '</option>' for c in sorted({a['category'] for a in articles}))
    unresolved = ''.join('<li>' + esc(q['question']) + ' ' + source(refs[q['source']]) + '</li>' for q in cross['openQuestions'])
    return '<section class="rm-panel" id="rm-view-reviews" role="tabpanel" hidden><link rel="stylesheet" href="../../css/review_library.css"><div class="rm-intro"><h2>先读综述，再核对它能说明什么</h2><p>收录 ' + str(len(articles)) + ' 项综述、教程与方法学资料；' + str(counts['abstract']) + ' 项已核读摘要，' + str(counts['sections']) + ' 项已核读指定章节，' + str(counts['metadata']) + ' 项作为书目入口。12 个议题逐项记录判断依据。</p><p class="hint">' + esc(library['scope']) + ' 截至 ' + library['updated'] + '。</p><p><a href="../../docs/review-evidence/2026-10-16/review-catalog.csv" download>下载文献清单 CSV</a> · <a href="../../docs/review-evidence/2026-10-16/reviews.ris" download>下载 RIS 文献库</a> · <a href="../../docs/review-cross-validation-2026-10-16.md">完整核对报告</a></p></div>' + coverage_html + '<h2>12 个交叉核对议题</h2><p class="hint">展开可看不同综述各自支持的内容、阅读位置，以及作者或版本之间的依赖。此处结论不等于实验复现。</p>' + ''.join(checks) + '<details class="rv-check"><summary>尚不能下结论的问题</summary><ul>' + unresolved + '</ul></details><h2>按主题找综述</h2><div class="rv-controls"><label>检索标题、作者或 DOI <input id="rv-query" type="search" placeholder="例如 PSO、Branke、多目标"></label><label>主题 <select id="rv-category"><option value="">全部主题</option>' + options + '</select></label><label>阅读深度 <select id="rv-level"><option value="">全部资料</option><option value="read">已核读摘要或章节</option><option value="sections">已核读指定章节</option><option value="metadata">书目入口</option></select></label></div><p id="rv-count" aria-live="polite"></p><div class="rv-grid">' + ''.join(cards) + '</div><button type="button" id="rv-more">继续显示</button><script defer src="../../js/review_library.js"></script></section>'
