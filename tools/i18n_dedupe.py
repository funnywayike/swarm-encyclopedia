# -*- coding: utf-8 -*-
"""data/i18n/*.json 里同一个键出现在多个文件时，只保留文件名排在最后的那一份（运行时本来就是后面的覆盖前面的），
并打印被丢掉的译文与保留的译文不同的条目，方便人工确认。

    python tools/i18n_dedupe.py
"""
import glob
import json
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def main():
    files = sorted(glob.glob(os.path.join(ROOT, "data", "i18n", "*.json")))
    data = {f: json.load(open(f, encoding="utf-8")) for f in files}
    last = {}
    for f in files:
        for k, v in data[f].get("strings", {}).items():
            last[k] = (f, v)
    dropped = differing = 0
    for f in files:
        s = data[f].get("strings", {})
        for k in list(s):
            lf, lv = last[k]
            if lf != f:
                if s[k] != lv:
                    differing += 1
                    print(f"  {os.path.basename(f)} → {os.path.basename(lf)}: {k[:40]!r}\n    丢掉：{s[k][:60]}\n    保留：{lv[:60]}")
                del s[k]
                dropped += 1
        with open(f, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data[f], fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    print(f"去掉 {dropped} 个重复键（其中译文不同 {differing} 个）")


if __name__ == "__main__":
    main()
