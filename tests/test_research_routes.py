"""Research narrative integrity and public rendering contracts."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def load(name):return json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
def test_routes_cover_every_reading_branch_and_resolve_sources():
 d=load('research_routes.json');v=load('research_reading_views.json');m=load('research_map.json')
 assert len(d['routes'])==20
 assert {r['id'] for r in d['routes']}=={r['id'] for r in v['methods']}
 nodes={n['id']:n for n in m['nodes']}
 for r in d['routes']:
  assert [s['id'] for s in r['stages']]==['origin','turn','recent','limits']
  assert r['question'] and r['crossReading'] and r['related']
  assert set(r['related'])<={x['id'] for x in d['routes']}
  for s in r['stages']:
   assert s['body'] and s['refs']
   assert set(s['refs'])<=set(d['sources'])
  recent=[d['sources'][x] for x in r['stages'][2]['refs']]
  assert any(2023<=s['year']<=2026 for s in recent),r['id']
  assert any(s.get('readingLevel') in ['abstract','sections'] for s in recent),r['id']
  assert len({x for s in r['stages'] for x in s['refs']})>=2
  for n in r['mapNodes']:
   assert nodes[n]['refs'] and nodes[n]['year']>=2022
   assert n in next(x for x in v['methods'] if x['id']==r['id'])['nodes']
def test_versions_and_evidence_types_remain_distinct():
 s=load('research_routes.json')['sources']
 assert s['r26-ga-brkga']['year']==2025
 assert s['r26-pso2026']['readingLevel']=='metadata'
 assert s['r26-cma-margin']['year']==2022 and s['r26-cma-extended']['year']==2024
 for key in ['r26-deepaco','r26-gfacs','r26-les','r26-aco-gp','r26-aco-pheromone']:
  assert s[key]['kind']=='原始研究'
 assert len(load('science_timeline.json')['trunk'])==16
def test_rendered_routes_are_accessible_and_defaults_match():
 from pages_research_routes import render_routes_panel,esc
 s=render_routes_panel()
 assert s.count('class="rr-card"')==20
 assert s.count('class="rr-stage"')==80
 assert s.count('class="rr-sources"')==80
 assert esc('<script>"&')=='&lt;script&gt;&quot;&amp;'
 assert 'aria-live="polite"' in s
 page=(ROOT/'meta/research-map/index.html').read_text(encoding='utf-8')
 assert 'aria-selected="true" data-view="routes"' in page
 assert 'id="rm-view-history" role="tabpanel" hidden' in page
 assert '__ROUTES_PANEL__' not in page
 assert '../../js/research_routes.js' in page
 assert '149' in page


def test_reader_layout_keeps_controls_outside_closed_scope_drawer():
 from pages_research_routes import render_routes_panel
 s=render_routes_panel()
 assert s.count('<details')==s.count('</details>')
 scope=s.index('<details class="rr-lead">')
 controls=s.index('<div class="rr-controls">')
 assert s.index('</details>',scope)<controls
 assert 'id="rr-route-nav"' in s and 'id="rr-grid"' in s
 assert '研究现场 / UFLP' not in s
 assert s.count('class="rr-investigation"')==20
 assert s.count('class="rr-evidence-papers"')==20


def test_each_route_has_distinct_problem_level_investigation():
 d=load('research_investigation.json')['routes']
 assert set(d)=={r['id'] for r in load('research_routes.json')['routes']}
 assert len({r['question'] for r in d.values()})==20
 assert len({r['comparison'] for r in d.values()})==20
 assert len({r['metrics'] for r in d.values()})==20
 from pages_research_routes import render_routes_panel
 from selfcheck import _tags_balanced
 assert _tags_balanced(render_routes_panel())
