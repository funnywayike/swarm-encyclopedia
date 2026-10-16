"""Editorial distinctions and source attribution must survive both views."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def load(name):return json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
def test_every_trunk_event_has_an_explanatory_dossier():
 from pages_milestones import milestone_data
 d=milestone_data();c=load('science_timeline.json');m=load('research_map.json')
 assert len(d['profiles'])==len(c['trunk'])==16
 assert {x['node'] for x in d['profiles']}==set(c['trunk'])
 refs={r['id'] for r in m['references']};routes={r['id'] for r in load('research_reading_views.json')['methods']}
 for p in d['profiles']:
  assert p['refs'] and set(p['refs'])<=refs
  assert set(p['routes'])<=routes
  for key in ['problem','change','consequence','dateMeaning','selectionReason']:
   assert len(p[key])>10,(p['node'],key)
  assert p['layer'] in ['mechanism','infrastructure','application','synthesis','frontier']
  assert all(x['name'] and x['id'] in routes for x in p['routeLinks'])
def test_representative_dates_and_frontier_status_are_not_conflated():
 from pages_milestones import milestone_data
 d={x['node']:x for x in milestone_data()['profiles']}
 assert d['alpha25']['layer']=='frontier'
 assert d['robotics13']['layer']=='synthesis'
 assert d['coco21']['layer']==d['tsplib91']['layer']=='infrastructure'
 assert d['calypso10']['layer']=='application'
 assert '1996' in d['cma01']['dateMeaning'] and '2001' in d['cma01']['dateMeaning']
 assert d['smac11']['authors']==['Frank Hutter','Holger H. Hoos','Kevin Leyton-Brown']
 assert d['pso95']['authors']==['J. Kennedy','R. Eberhart']
def test_both_views_publish_dossiers_and_readable_connections():
 from pages_milestones import render_milestones_panel
 panel=render_milestones_panel()
 assert panel.count('class="md-card"')==16
 assert '主干怎样选取' in panel and '外部专家评审' in panel
 assert '#route-configuration' in panel and 'CONFIGURATION 研究路线' not in panel
 timeline=(ROOT/'meta/timeline/index.html').read_text(encoding='utf-8')
 assert 'id="vine-layers"' in timeline
 payload=json.loads(timeline.split('id="science-vine-data">')[1].split('</script>')[0])
 assert len(payload['config']['milestones']['profiles'])==16
 assert payload['config']['milestones']['extraSources'][0]['url']=='https://cma-es.github.io/'
 page=(ROOT/'meta/research-map/index.html').read_text(encoding='utf-8')
 assert 'data-view="milestones"' in page and 'data-dossier=' in page
 assert '__MILESTONES_PANEL__' not in page
