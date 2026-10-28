# -*- coding: utf-8 -*-
"""One-click: contract DB -> bridge -> rebuild dashboard HTML.

为什么要这样写：DSH 沙箱/部分安全软件会拦截 subprocess 的管道（WinError 5），
所以不用 subprocess，改为在**同一进程**里 exec 目标脚本的源码，输出直接打到当前控制台。
"""
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent


def run_script(filename, argv):
    """同进程执行另一个脚本，argv 传给它的 sys.argv（[0] 为脚本名）。"""
    path = BASE / filename
    if not path.exists():
        print("[FAIL] 找不到 %s" % filename, file=sys.stderr)
        return False
    src = path.read_text(encoding="utf-8")
    old_argv = sys.argv[:]
    old_path = sys.path[:]
    sys.argv = [str(path)] + list(argv)
    if str(BASE) not in sys.path:
        sys.path.insert(0, str(BASE))
    g = {"__name__": "__main__", "__file__": str(path), "__builtins__": __builtins__}
    try:
        exec(compile(src, str(path), "exec"), g)
        return True
    except SystemExit as e:
        return e.code in (0, None)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("[FAIL] %s: %s" % (filename, e), file=sys.stderr)
        return False
    finally:
        sys.argv = old_argv
        sys.path = old_path


def main():
    print("=" * 52)
    print("  Step 1/2  contract DB -> receivable data")
    print("=" * 52)
    if not run_script("bridge.py", ["--rebuild"]):
        sys.exit(1)

    print()
    print("=" * 52)
    print("  Step 2/2  rebuild dashboard HTML")
    print("=" * 52)
    if not run_script("build_dashboard.py", ["--source=bridge"]):
        sys.exit(1)

    print()
    print("DONE. Open this file by double-click:")
    print("  " + str(BASE / "应收账款看板_合同库版_离线版.html"))


if __name__ == "__main__":
    main()
