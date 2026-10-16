"""Research evidence must stay connected to real source records and model declarations."""
import json
import re
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"py"))
import registry
def load(name):return json.loads((ROOT/"data"/name).read_text(encoding="utf-8"))

def test_every_map_relationship_and_application_resolves_to_evidence():
    m=load("research_map.json");r={x["id"]:x for x in m["references"]}
    assert len(r)==len(m["references"])
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k in ("refs","researchRefs","evidence") and isinstance(v,list):
                    assert all(z in r for z in v),v
                walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(m)
    nodes={x["id"] for x in m["nodes"]}
    for e in m["relations"]:
        assert e["source"] in nodes and e["target"] in nodes and e["refs"]
    apps=load("apps.json")["entries"]
    assert len(apps)==96
    assert all(e.get("researchRefs") for e in apps)
    for e in apps:
        assert all(z in r for z in e["researchRefs"])
        for z in e["researchRefs"]:
            assert r[z].get("metadata",{}).get("type")!="peer-review"
    for ind in m["industryEvidence"]:
        assert ind["count"]==len(ind["entries"])
        for e in ind["entries"]:
            original=next(a for a in apps if a["title"]==e["title"])
            assert e["summary"]==original["oneliner"] and e["refs"]==original["researchRefs"]

def test_model_ledger_matches_actual_page_options_and_engine():
    a=load("research_consistency_audit.json")
    assert len(a["problems"])==96 and len(a["algorithms"])==45
    assert all(p["sourceCount"]>0 and p["sources"] for p in a["problems"])
    for p in a["problems"]:
        f=ROOT/p["url"].strip("/")/"index.html"
        assert f.is_file(),p["id"]
        t=f.read_text(encoding="utf-8")
        dm=re.search(r'window\.PAGE_DOMAIN = "([^"]+)"',t)
        pm=re.search(r'window\.PAGE_PRESETS = (\{.*?\});\n',t)
        if dm:
            opts=next(iter(json.loads(pm.group(1)).values()),{}) or {}
            expected=registry.fidelity(dm.group(1),opts.get("variant"))
            assert p["fidelity"]==expected["level"],p["id"]
            if expected["note"]:assert p["note"]==expected["note"]
        else:
            assert p["fidelity"]=="reference"
    for e in a["algorithms"]:
        assert (ROOT/e["url"].strip("/")/"index.html").is_file(),e["key"]
        assert e["line"] and e["note"]
        assert (ROOT/e["code"]).is_file()

def test_formal_versions_and_local_source_records_are_preserved():
    m=load("research_map.json");r={x["id"]:x for x in m["references"]}
    assert "00662-2" in r["cryptoBooleanSurvey2023"]["url"]
    assert r["automatedMhDesignSurvey2023"]["year"]==2024
    assert "qhtHsvF5zj" in r["automatedMhDesignSurvey2023"]["url"]
    c=load("research_catalog_candidates.json")
    assert len(c["applications"])==96 and len(c["fields"])==13 and not c["errors"]
    root=ROOT/"docs"/"research-records"/"2026-10-16"
    assert len(list(root.glob("app-*.json")))==96
    assert len(list(root.glob("field-*.json")))==13
    json.loads((root/"web-search-records.json").read_text(encoding="utf-8"))
    assert "报告 10." not in (ROOT/"applications"/"index.html").read_text(encoding="utf-8")
