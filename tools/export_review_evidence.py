"""Export the curated review directory and the claim-level audit (no article full texts)."""
import csv
import json
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/review-evidence/2026-10-16'
def load(name):
    return json.loads((ROOT / 'data' / name).read_text(encoding='utf-8'))
def export():
    library = load('review_library.json')
    checks = load('review_crosschecks.json')
    discovery = load('review_candidates.json')
    articles = library['articles']
    refs = {a['id']: a for a in articles}
    OUT.mkdir(parents=True, exist_ok=True)
    fields = ['id','year','title','authors','doi','url','journal','kind','articleType','category','language','readingLevel','readingLabel','readingLocation','scopeNote']
    with (OUT / 'review-catalog.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for a in articles:
            row = {k:a[k] for k in fields}
            row['authors'] = '; '.join(a['authors'])
            w.writerow(row)
    ris = []
    for a in articles:
        typ = 'CHAP' if a['publicationType'] == 'book-chapter' else 'JOUR' if a['publicationType'] == 'journal-article' else 'GEN'
        ris.extend(['TY  - ' + typ, 'ID  - ' + a['id'], 'TI  - ' + a['title']])
        ris.extend('AU  - ' + name for name in a['authors'])
        if a['year']: ris.append('PY  - ' + str(a['year']))
        if a['journal']: ris.append('T2  - ' + a['journal'])
        if a['doi']: ris.append('DO  - ' + a['doi'])
        ris.extend(['UR  - ' + a['url'], 'N1  - ' + a['readingLabel'] + '；' + a['readingLocation'], 'ER  - ', ''])
    (OUT / 'reviews.ris').write_text('\n'.join(ris), encoding='utf-8')
    with (OUT / 'claim-matrix.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['claim','title','status','source','doi','location','finding','independence'])
        w.writeheader()
        for c in checks['checks']:
            for e in c['evidence']:
                w.writerow(dict(claim=c['id'],title=c['title'],status=c['status'],source=e['source'],doi=refs[e['source']]['doi'],location=e['location'],finding=e['finding'],independence=c['independence']))
    counts = Counter(a['readingLevel'] for a in articles)
    total = sum(len(q['items']) for q in discovery['searches'])
    unique = len({a['DOI'].lower() for q in discovery['searches'] for a in q['items'] if a.get('DOI')})
    lines = ['# 综述资料收集与交叉核对报告', '', '2026-10-16；研究资料与核对记录。', '',
        '## 本轮做到什么程度', '',
        '收录 ' + str(len(articles)) + ' 项综述、教程和方法学资料，按 DOI 或原始链接去重。已核读摘要 ' + str(counts['abstract']) + ' 项，已核读指定章节 ' + str(counts['sections']) + ' 项，其余 ' + str(counts['metadata']) + ' 项保留为书目入口。没有声称逐篇读完全文，也未复现这些论文中的全部实验。', '',
        '30 个英文书目查询，每个取 Crossref 相关性前5项，共 ' + str(total) + ' 条候选记录、' + str(unique) + ' 个不同 DOI；另合并原研究地图书目、出版社和机构库来源，并人工补充经典与更新综述。这不是全数据库检索，不能由此计算领域覆盖率或宣称穷尽。中文4项为既有阅读入口，本轮尚未完成逐段核读。', '',
        '## 扩展覆盖检查', '', '在首轮检索之外，新增32组主题查询、每组前15项，共480条候选；人工补充了理论、景观、参数控制、大规模、离散适配和经典搜索框架等资料。文献增加不等于核读完成。完整性按42主题覆盖表逐项检查，尚不宣称较完整。', '', '[查看42主题覆盖与缺口](review-coverage-audit-2026-10-16.md)。', '', '## 检索与筛选', '',
        '检索主题包括历史与分类、PSO、ACO、DE、ABC、GA、CMA-ES、VNS、模因算法、约束、多目标/多目标高维、动态与不确定优化、代理模型、质量多样性、超启发式、算法选择/配置/设计、学习辅助、机器人及应用专题。检索式、请求地址和候选元数据均已保存。候选排序偏向相关性，可能遗漏不同措辞或不在 Crossref 的资料。', '',
        '人工筛除偏题、评审意见等非正文材料，并合并重复入口。未选中不等于质量不合格；目录保留历史评论、教程、方法学预印本与正式综述的类型差别。预印本不自动当作同行评审结果。', '',
        '交叉核对以具体主张为单位：先比较研究对象、时间和阅读位置，再检查作者重叠、引用延续、版本与日期。多篇重复同一句话不自动增加独立证据。不同综述的范围差别也不自动表示结论矛盾。', '',
        '## 主题分布', '', '|主题|资料数|', '|---|---:|']
    lines.extend('|' + c + '|' + str(n) + '|' for c,n in sorted(Counter(a['category'] for a in articles).items()))
    lines.extend(['', '## 12 个核对议题', ''])
    for c in checks['checks']:
        lines.extend(['### ' + c['title'], '', '**判断：' + c['status'] + '。** ' + c['conclusion'], '', '独立性与边界：' + c['independence'], ''])
        for e in c['evidence']:
            a = refs[e['source']]
            lines.append('- [' + a['title'] + '](' + a['url'] + ')；' + e['location'] + '；' + e['finding'])
        lines.append('')
    lines.extend(['## 尚不能下结论', ''])
    for q in checks['openQuestions']:
        a=refs[q['source']]
        lines.append('- ' + q['question'] + ' 入口：[' + a['title'] + '](' + a['url'] + ')。')
    lines.extend(['', '## 版本和元数据风险', '',
        'ABC 的2012在线日期与2014卷期均保存；跨平台的 published-online 字段不总能解释为首发时间，例如超启发式2013正式记录还出现2017平台在线字段。保留原始字段，按正式版本识别论文，不从 DOI 中猜年份。作者姓名缩写变体也需要人工识别，不单纯按字符串计算独立团队。', '',
        'Forrester/Keane 的2009综述此前检索候选 DOI 10.1016/j.paerosci.2008.10.001 不匹配目标题名；已改为 10.1016/j.paerosci.2008.11.001。错误候选的原始查询记录保留作审计，但不进入目录或下载库。', '',
        '书目收录与内容核读分开标记；无 DOI 的中文条目、教程和作者公开稿沿用原始入口。部分出版社页面抓取失败，不能因搜索命中就标作全文已读。引用位置优先使用作者公开稿、出版社摘要和机构记录。', '',
        '## 可复用成果', '',
        '- [完整文献清单 CSV](review-evidence/2026-10-16/review-catalog.csv)', '- [RIS 文献库](review-evidence/2026-10-16/reviews.ris)', '- [逐主张证据矩阵 CSV](review-evidence/2026-10-16/claim-matrix.csv)', '- [150条检索候选的筛选记录](review-evidence/2026-10-16/candidate-screening.csv)', '',
        '数据源：data/review_library.json；核读记录：data/review_reading_notes.json；核对议题：data/review_crosschecks.json。原始 Crossref 检索与单篇记录保存在 docs/review-evidence/2026-10-16/，部分继承来源见 docs/research-records/2026-10-16/。目录不包含论文全文副本。', '',
        '维护顺序：collect_review_evidence.py（需要网络）→ 人工修改 review_selection.json、review_reading_notes.json 与 review_crosschecks.json → build_review_library.py → export_review_evidence.py → audit_review_coverage.py → 构建网站。前5项截断是当前检索限制，未来增量检索应记录新协议，避免改写本轮覆盖范围。', '',
        '## 本地验证', '', '相关 Python 检查通过，覆盖书目去重、DOI题名修正、证据来源分级、人工标注再生成、输出转义及既有研究地图/引用/模型/i18n检查。目录筛选与界面控制器检查通过；生成页面的资料数与目录一致，12个议题及待决问题的来源可追溯；资源和下载路径均存在，RIS条目数与目录一致。', '', '研究地图增加“综述与交叉验证”入口，提供主题、作者/标题/DOI、阅读深度筛选和逐步显示。本轮完成内容与功能检查；未做实际浏览器视觉验收。', ''])
    (ROOT / 'docs/review-cross-validation-2026-10-16.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Exported',len(articles),'records;',dict(counts),';',len(checks['checks']),'checks')
if __name__ == '__main__': export()
