"""Evidence traceability, not assertions about algorithm performance."""
import json
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
def load(name):
    return json.loads((ROOT / 'data' / name).read_text(encoding='utf-8'))
def test_review_identity_and_metadata():
    articles = load('review_library.json')['articles']
    assert len({a['id'] for a in articles}) == len(articles)
    canonical = [a['doi'].lower() or a['url'] for a in articles]
    assert len(set(canonical)) == len(canonical)
    for a in articles:
        assert a['title'].strip() and a['url'].startswith('https://')
        assert a['readingLevel'] in {'metadata','abstract','sections'}
        if a['recordDOI']: assert a['recordDOI'].lower() == a['doi']
    target = next(a for a in articles if 'Forrester' in ' '.join(a['authors']))
    assert target['doi'] == '10.1016/j.paerosci.2008.11.001'
    assert 'surrogate-based' in target['title']
    assert '10.1016/j.paerosci.2008.10.001' not in canonical
def test_claims_trace_to_read_sources():
    lib = load('review_library.json')
    refs = {a['id']:a for a in lib['articles']}
    checks = load('review_crosschecks.json')['checks']
    assert lib['crossChecks'] == checks
    assert len({c['id'] for c in checks}) == len(checks)
    for c in checks:
        assert len({e['source'] for e in c['evidence']}) >= 2
        assert c['conclusion'] and c['independence']
        for e in c['evidence']:
            a = refs[e['source']]
            assert e['location'] and e['finding']
            if c['kind'] == 'content':
                assert a['readingLevel'] != 'metadata'
    for q in load('review_crosschecks.json')['openQuestions']: assert q['source'] in refs
def test_annotation_survives_build():
    refs={a['id']:a for a in load('review_library.json')['articles']}
    notes=load('review_reading_notes.json')
    for key,note in notes['notes'].items():
        assert key in refs
        for field,value in note.items(): assert refs[key][field] == value
    for key,value in notes['categoryOverrides'].items(): assert refs[key]['category'] == value
def test_panel_exports_and_escaping(monkeypatch):
    import pages_reviews
    original = pages_reviews.load
    def altered(name):
        obj=original(name)
        if name == 'review_library.json':
            obj['articles'][0]['title']='<img src=x onerror=alert(1)>'
        return obj
    monkeypatch.setattr(pages_reviews,'load',altered)
    panel=pages_reviews.render_review_panel()
    assert '<img src=x' not in panel
    assert '&lt;img src=x' in panel
    for filename in ['review-catalog.csv','reviews.ris','claim-matrix.csv','candidate-screening.csv']:
        assert (ROOT/'docs/review-evidence/2026-10-16'/filename).is_file()

def test_coverage_references_and_reading_counts():
    library=load('review_library.json')
    refs={a['id']:a for a in library['articles']}
    coverage=load('review_coverage.json')
    plan=load('review_coverage_plan.json')
    assert len(coverage['topics'])==len(plan['topics'])
    assert len({t['id']for t in coverage['topics']})==len(coverage['topics'])
    for t in coverage['topics']:
        assert t['remaining']
        assert all(s in refs for s in t['sourceIDs'])
        assert len(set(t['sourceIDs']))==len(t['sourceIDs'])
        assert t['readCount']==sum(refs[s]['readingLevel']!='metadata'for s in t['sourceIDs'])
        assert all(any(c['id']==key and c['kind']=='content'for c in library['crossChecks'])for key in t['crossCheckIDs'])
    gp=next(t for t in coverage['topics']if t['id']=='gp')
    assert gp['readCount']==0 and gp['status']=='已有资料，正文核读待补'
def test_discovery_stays_separate_from_curated_evidence():
    first=load('review_candidates.json')
    expanded=load('review_candidates_expanded.json')
    assert len(first['searches'])==30
    assert len(expanded['searches'])==len(load('review_expansion_queries.json')['queries'])
    assert not any(s.get('error')for s in expanded['searches'])
    assert sum(len(s['items'])for s in expanded['searches'])==480
    lib=load('review_library.json')
    assert len(lib['articles'])<sum(len(s['items'])for s in expanded['searches'])
    assert len(lib['crossChecks'])==12
def test_exported_catalogue_not_stale():
    import csv
    library=load('review_library.json')['articles']
    folder=ROOT/'docs/review-evidence/2026-10-16'
    with (folder/'review-catalog.csv').open(encoding='utf-8-sig',newline='')as f:rows=list(csv.DictReader(f))
    assert {a['id']for a in rows}=={a['id']for a in library}
    ris=(folder/'reviews.ris').read_text(encoding='utf-8')
    assert ris.count('TY  - ')==len(library)==ris.count('ER  - ')
    assert (folder/'expanded-candidate-screening.csv').is_file()
    assert (folder/'coverage-matrix.csv').is_file()
