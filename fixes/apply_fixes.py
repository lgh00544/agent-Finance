"""P0/M 修复补丁应用器（dsh 修复包）

背景：本次修复目标的仓库位于 D:\\space\\self\\self，而 dsh 会话沙箱把文件写入限制在
会话工作区内（该目录属工作区之外，写入被沙箱拒绝且无审批通道），因此修复以「补丁包」
形式交付：本目录下 parts/*.py 保存逐项精确替换（old -> new），本脚本负责
  1) 校验每个锚点在原文件中**恰好出现一次**（或已应用），
  2) 对替换后的全文做 compile() 语法校验，
  3) 备份原文件为 <file>.bak-<YYYYMMDD>（二进制逐字节备份），
  4) 写入新内容，并**保持该文件原有的换行风格**（仓库里多为 CRLF，http_client.py 为 LF）。

用法（在项目根目录、用项目自带解释器执行）：
    D:\\space\\self\\self\\.venv\\Scripts\\python.exe fixes\\apply_fixes.py --check
    D:\\space\\self\\self\\.venv\\Scripts\\python.exe fixes\\apply_fixes.py --apply
    D:\\space\\self\\self\\.venv\\Scripts\\python.exe fixes\\apply_fixes.py --apply --backup-suffix .bak-20260928
    D:\\space\\self\\self\\.venv\\Scripts\\python.exe fixes\\apply_fixes.py --list

安全性：
    * --check 为纯只读演练（不写任何文件）。
    * **默认「全或无」**：任一文件的锚点缺失/多义/替换后语法错误 → 一个文件都不写。
      本补丁包的修复项彼此有跨文件依赖（如 session.py 依赖 config.py 新增的 db_pool_size、
      routes.py 依赖 config.py 的注册门槛开关与 auth.py 的 LoginGuard），半套补丁会让服务起不来，
      所以宁可整体不落。确需只写通过的文件时用 --force-partial。
    * 已应用的项（new 已在文中、old 已不在文中）记为 skipped，可重复执行。
    * 写入保持各文件原有换行风格（仓库里多为 CRLF，http_client.py 为 LF），diff 只含真正改动的行。
    * 锚点比较前统一把 CRLF 归一为 LF，因此 parts 文件自身的换行风格不影响匹配。
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from datetime import datetime
from pathlib import Path

BUNDLE_DIR = Path(__file__).resolve().parent
DEFAULT_PROJECT = Path(r"D:\space\self\self")


def _load_parts():
    parts = []
    for path in sorted((BUNDLE_DIR / "parts").glob("*.py")):
        spec = importlib.util.spec_from_file_location("fixpart_" + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 片段文件自身有问题必须显式报错，不能静默跳过
            raise SystemExit("!! 片段文件无法加载（语法/结构错误）: %s\n   %s: %s"
                             % (path.name, type(exc).__name__, exc))
        items = list(getattr(module, "ITEMS", []) or [])
        if not items:
            raise SystemExit("!! 片段文件缺少 ITEMS: %s" % path.name)
        parts.append((path.name, items))
    return parts


def _lf(text: str) -> str:
    """锚点比较用：CRLF / 单独 CR 一律归一为 LF。"""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _source_newline(path: Path) -> str:
    """探测原文件换行风格：有 CRLF 即 CRLF（仓库里绝大多数文件如此）。"""
    data = path.read_bytes()
    return "\r\n" if b"\r\n" in data else "\n"


def _plan_file(project: Path, rel: str, items: list[dict]):
    """返回 (状态, 文本 或 错误信息, 明细说明列表)"""
    target = project / rel
    if not target.exists():
        return "error", "文件不存在: %s" % target, []
    text = _lf(target.read_text(encoding="utf-8"))
    notes, errors = [], []
    for item in items:
        for index, (old, new) in enumerate(item["edits"], 1):
            old, new = _lf(old), _lf(new)
            if old == new:
                errors.append("%s#%d 替换前后相同（补丁自身有误）" % (item["id"], index))
                continue
            occurrences = text.count(old)
            if occurrences == 1:
                text = text.replace(old, new, 1)
                notes.append("%s#%d 应用 (%s)" % (item["id"], index, item.get("summary", "")))
            elif occurrences == 0 and new in text:
                notes.append("%s#%d 已应用，跳过" % (item["id"], index))
            elif occurrences == 0:
                errors.append("%s#%d 锚点未找到（文件已变动？）" % (item["id"], index))
            else:
                errors.append("%s#%d 锚点出现 %d 次，无法唯一定位" % (item["id"], index, occurrences))
    if errors:
        return "error", "; ".join(errors), notes
    try:
        compile(text, str(target), "exec")
    except SyntaxError as exc:
        return "error", "替换后语法错误: %s (line %s)" % (exc.msg, exc.lineno), notes
    return "ok", text, notes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="应用 dsh P0/M 修复补丁")
    parser.add_argument("--project", default=str(DEFAULT_PROJECT), help="项目根目录")
    parser.add_argument("--check", action="store_true", help="只校验不写入（默认行为）")
    parser.add_argument("--apply", action="store_true", help="备份并写入")
    parser.add_argument("--backup-suffix", default=None, help="备份后缀，默认 .bak-<今天 YYYYMMDD>")
    parser.add_argument("--list", action="store_true", help="只列出补丁项，不读项目文件")
    parser.add_argument("--force-partial", action="store_true",
                        help="即使有文件校验失败也写入通过的文件（默认全或无，见下）")
    args = parser.parse_args(argv)

    suffix = args.backup_suffix or (".bak-" + datetime.now().strftime("%Y%m%d"))
    parts = _load_parts()
    if not parts:
        print("!! 未找到 parts/*.py 补丁片段")
        return 2

    grouped: dict[str, list[dict]] = {}
    for _, items in parts:
        for item in items:
            grouped.setdefault(item["file"], []).append(item)

    if args.list:
        for rel in sorted(grouped):
            print(rel)
            for item in grouped[rel]:
                print("    %-10s %s (%d 处替换)"
                      % (item["id"], item.get("summary", ""), len(item["edits"])))
        return 0

    project = Path(args.project)
    if not (project / "backend" / "app").is_dir():
        print("!! 项目根目录无效（缺 backend/app）: %s" % project)
        return 2

    total_items = sum(len(items) for _, items in parts)
    print("补丁片段 %d 个 / 修复项 %d 个 / 涉及文件 %d 个"
          % (len(parts), total_items, len(grouped)))
    print("模式: %s\n" % ("APPLY（会写文件）" if args.apply else "CHECK（只读演练）"))

    # 阶段一：只做校验、不写任何东西（跨文件修复项彼此有依赖，例如 session.py 要用
    # config.py 新增的 db_pool_size、routes.py 要用 config.py 的注册门槛开关 ——
    # 因此默认「全或无」：只要有文件校验失败就一个都不写，避免写出半套补丁）。
    plan: list[tuple[str, str, list[str]]] = []
    failed = 0
    for rel in sorted(grouped):
        status, payload, notes = _plan_file(project, rel, grouped[rel])
        ids = ",".join(dict.fromkeys(item["id"] for item in grouped[rel]))
        if status == "error":
            failed += 1
            print("[FAIL] %s  (%s)\n        %s" % (rel, ids, payload))
            continue
        applied = [note for note in notes if "已应用" not in note]
        if not applied:
            print("[SKIP] %s  (%s) 全部已应用" % (rel, ids))
            continue
        plan.append((rel, payload, applied))
        print("[ OK ] %s  (%s) 待改动 %d 处" % (rel, ids, len(applied)))

    if failed and not (args.force_partial and args.apply):
        print("\n结果：%d 个文件校验失败 → 本次不写任何文件（全或无）。" % failed)
        print("请核对失败项的锚点（可能文件已被其他改动影响）；确需只写通过的文件时用 --force-partial。")
        return 1

    if not args.apply:
        print("\n结果：可改文件 %d，失败文件 %d" % (len(plan), failed))
        print("演练通过。执行 --apply 落地（会先生成 .bak- 备份）。")
        return 0

    # 阶段二：写入（备份为二进制逐字节副本，换行风格按各文件原样保留）
    for rel, payload, applied in plan:
        target = project / rel
        backup = target.with_name(target.name + suffix)
        if not backup.exists():
            backup.write_bytes(target.read_bytes())
        newline = _source_newline(target)
        with open(target, "w", encoding="utf-8", newline=newline) as handle:
            handle.write(payload)
        print("[DONE] %s 备份=%s 换行=%s  (%d 处改动)" % (rel, backup.name, repr(newline), len(applied)))
    print("\n结果：已写入 %d 个文件，校验失败 %d 个。" % (len(plan), failed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
