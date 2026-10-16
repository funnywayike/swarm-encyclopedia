# -*- coding: utf-8 -*-
"""问题分类（抽象类 Ⅰ-Ⅺ + 开放登记）的单一来源：data/problem_groups.json。

站点里有四处要列出这些类（问题板块导航、问题总览页、元层概览页、抽象类型页的面包屑），
此前每处各抄一份标签和顺序。现在统一从这里取，顺序即 JSON 里的顺序。
每个问题条目属于哪一类，由 data/problems.json 里它的 group 字段决定。
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

with io.open(os.path.join(ROOT, "data", "problem_groups.json"), encoding="utf-8") as _f:
    GROUPS = json.load(_f)

ORDER = tuple(g["id"] for g in GROUPS)           # 展示顺序
LABEL = {g["id"]: g["label"] for g in GROUPS}     # 长标签（带编码方式），用于小节标题
NAV = {g["id"]: g["nav"] for g in GROUPS}         # 导航里的短标签
SHORT = {g["id"]: g["short"] for g in GROUPS}     # 概览表里的中等长度标签
