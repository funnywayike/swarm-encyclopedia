# -*- coding: utf-8 -*-
"""黄金快照回归：重构（拆文件/改注册表/换分类）不得改变任何「域×变体×算法」的固定种子结果。
故意改变行为时：python tools/golden.py --update，并在提交说明里写清楚为什么变。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

import golden  # noqa: E402


def test_golden_snapshot_matches():
    with open(golden.SNAPSHOT, encoding="utf-8") as f:
        old = json.load(f)
    new, errors = golden.run_all()
    assert not errors, f"{len(errors)} 个组合报错：{dict(list(errors.items())[:5])}"
    added, removed, changed = golden.diff(old, new)
    msg = []
    if changed:
        msg.append(f"{len(changed)} 项数值变化，如 " + "; ".join(f"{k}: {old[k]}→{new[k]}" for k in changed[:5]))
    if removed:
        msg.append(f"{len(removed)} 项消失，如 {removed[:5]}")
    if added:
        msg.append(f"{len(added)} 项新增，如 {added[:5]}")
    assert not msg, "；".join(msg) + "。若是有意为之，运行 python tools/golden.py --update"
    assert len(new) > 2000


def test_snapshot_has_no_degenerate_entries():
    """快照里不应出现全 None / 含 NaN 的条目（那说明算法根本没产出）。"""
    with open(golden.SNAPSHOT, encoding="utf-8") as f:
        snap = json.load(f)
    bad = [k for k, v in snap.items() if v is None or any(x != x for x in v)]
    assert not bad, bad[:10]
