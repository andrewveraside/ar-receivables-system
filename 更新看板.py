#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键：合同库 → 看板数据 → 重新生成看板 HTML（双击或命令行均可）"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def run(script, *args):
    r = subprocess.run([sys.executable, str(BASE / script), *args],
                       capture_output=True, text=True, encoding="utf-8", cwd=str(BASE))
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if out:
        print(out)
    if r.returncode != 0:
        print(f"[失败] {script}: {err}", file=sys.stderr)
        return False
    return True


print("=" * 52)
print("  1/2  同步合同库 → 应收数据")
print("=" * 52)
if not run("bridge.py", "--rebuild"):
    sys.exit(1)

print()
print("=" * 52)
print("  2/2  重新生成看板 HTML")
print("=" * 52)
if not run("build_dashboard.py", "--source=bridge"):
    sys.exit(1)

out = BASE / "应收账款看板_合同库版_离线版.html"
print()
print(f"✅ 完成：{out.name}  双击即可打开")
