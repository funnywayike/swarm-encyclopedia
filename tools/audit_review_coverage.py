"""Report coverage without equating discovery, reading and independent verification."""
import csv
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name):return json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
def audit():
    library=load('review_library.json')
    plan=load('review_coverage_plan.json')
    expanded=load('review_candidates_expanded.json')
    byid={a['id']:a for a in library['articles']}
    bydoi={a['doi'].lower():a for a in library['articles']if a['doi']}
    checks={c['id']:c for c in library['crossChecks']}
    mapping={'history':['counts'],'pso':['pso'],'abc':['dates'],'de':['de-lineage'],'theory':[],'dynamic':['uncertainty'],'surrogates':['surrogates','bib-correction'],'multimodal':['qd'],'hyper':['automation'],'learning':['ml'],'nas':['counts'],'robotics':['robotics'],'medical':['application'],'manufacturing':['application'],'transport':['application']}
    rows=[]
    for t in plan['topics']:
        sources=[]
        for key in t['sources']:
            a=bydoi.get(key.lower()) if key.lower().startswith('10.') else byid.get(key)
            if not a:raise ValueError('Unresolved coverage source: '+key)
            if a['id']not in sources:sources.append(a['id'])
        read=[s for s in sources if byid[s]['readingLevel']!='metadata']
        cross=[c for c in mapping.get(t['id'],[])if checks[c]['kind']=='content']
        status='仍缺代表资料'if not sources else'已有资料，正文核读待补'if not read else'已有核读，逐议题核对待补'if not cross else'已核对部分议题，仍有缺口'
        rows.append(dict(**t,sourceIDs=sources,readCount=len(read),crossCheckIDs=cross,status=status))
    result=dict(updated=plan['updated'],scope=plan['scope'],completionRule=plan['completionRule'],topics=rows,searches=len(expanded['searches']),candidateRows=sum(len(s['items'])for s in expanded['searches']),searchFailures=[s['topic']for s in expanded['searches']if s.get('error')])
    (ROOT/'data/review_coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    out=ROOT/'docs/review-evidence/2026-10-16'
    with(out/'coverage-matrix.csv').open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=['topic','ring','status','sourceCount','readCount','sources','remaining']);w.writeheader()
        for t in rows:w.writerow(dict(topic=t['title'],ring=t['ring'],status=t['status'],sourceCount=len(t['sourceIDs']),readCount=t['readCount'],sources=';'.join(t['sourceIDs']),remaining=t['remaining']))
    with(out/'expanded-candidate-screening.csv').open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=['topic','query','doi','title','type','decision']);w.writeheader()
        for q in expanded['searches']:
            for a in q['items']:
                d=a.get('DOI','').lower()
                decision='目录已收录'if d in bydoi else'非正文评审意见'if a.get('type')=='peer-review'else'未纳入本轮目录；未选中不代表质量否定'
                w.writerow(dict(topic=q['topic'],query=q['query'],doi=d,title=' '.join(a.get('title',[])),type=a.get('type',''),decision=decision))
    lines=['# 综述覆盖检查与扩展检索','',plan['updated']+'；研究资料，不宣称覆盖穷尽。','',
        '## 当前判断','','现有目录不能称为完整综述。收录文献、读过内容、验证了某个结论是三个不同状态；本表不计算伪精确的“完成百分比”。',
        '',plan['scope'],'',plan['completionRule'],'',
        '## 本轮扩展','','在首轮30组、每组前5项检索之外，新增32组、每组前15项检索，保存480条候选。另通过出版社和作者机构页面补充确定题名；按题名、体裁、作者与出版记录人工选取。所有候选都不是默认合格综述，尤其检索中的 review 可能指评审意见，标题还可能是勘误或无关领域。','',
        '当前目录共'+str(len(library['articles']))+'项资料，阅读状态为：'+ '，'.join(k+' '+str(v) for k,v in sorted(Counter(a['readingLabel']for a in library['articles']).items()))+'。新增书目不自动继承已有交叉核对结果。','',
        '## 达到“比较完整”还需要什么','','- 主题：主要机制、理论、实验方法、复杂问题与代表性应用都有明确入口，缺失可见。','- 时间：经典框架与有意义的后续更新并列，不机械要求每个稳定分支都有今年综述。','- 内容：核读关键章节，提取研究对象、贡献、基准、局限及分歧，不能止于摘要。','- 独立性：核对共同作者、相同实验、相互引用与版本延续；不同作者也不保证底层证据独立。','- 查漏：沿关键综述参考文献向后追溯，再检查后续更新；对其他数据库、中文与机构资料的遗漏另作记录。','',
        '## 42 个主题的可追踪状态','','“已核对部分议题”只表示本轮确有对应内容核对，不代表该主题已经完整。相邻进化计算和元启发式用于解释群智能的上下文，不全部归为群智能。','',
        '|主题|范围|资料数 / 已核读数|状态|仍需补充|','|---|---|---:|---|---|']
    for t in rows:lines.append('|'+t['title']+'|'+t['ring']+'|'+str(len(t['sourceIDs']))+' / '+str(t['readCount'])+'|'+t['status']+'|'+t['remaining']+'|')
    lines.extend(['','## 各主题来源入口',''])
    for t in rows:
        lines.extend(['### '+t['title'],''])
        for sid in t['sourceIDs']:
            a=byid[sid];lines.append('- ['+a['title']+']('+a['url']+') · '+str(a['year'])+' · '+a['readingLabel'])
        if not t['sourceIDs']:lines.append('- 暂缺。')
        lines.append('')
    lines.extend(['## 下载与记录','','- [覆盖矩阵 CSV](review-evidence/2026-10-16/coverage-matrix.csv)','- [扩展候选筛选记录 CSV](review-evidence/2026-10-16/expanded-candidate-screening.csv)','- [全部目录 CSV](review-evidence/2026-10-16/review-catalog.csv)','- [逐主张核对报告](review-cross-validation-2026-10-16.md)','','原始响应：docs/review-evidence/2026-10-16/expanded-*.json；补检配置：data/review_expansion_queries.json；覆盖配置：data/review_coverage_plan.json。原始记录中的元数据和参考文献不等于已经核读其全文。',''])
    (ROOT/'docs/review-coverage-audit-2026-10-16.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Coverage topics',len(rows),'articles',len(library['articles']),'candidate rows',result['candidateRows'],'failures',result['searchFailures'])
if __name__=='__main__':audit()
