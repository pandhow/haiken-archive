#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海垦日报 · 历史归档 —— 自动同步脚本
=====================================

用途
----
每天「海垦日报」自动化在 D:\\Harry的文件\\ 生成 海垦日报_YYYY-MM-DD.html，
本脚本自动把新一期搬进 haiken-archive/issues/ 并重生成 data/manifest.json，
归档全程免手动。

设计原则
--------
1. 非破坏（non-destructive）：manifest 里已存在的期次，其 title/tags 永远保留，
   重跑不会用「兜底标题」覆盖人工精修过的标题。
2. 幂等（idempotent）：同一文件重复跑只比较哈希，内容一致就跳过，绝不重复复制。
3. 零依赖：仅用 Python 标准库，云电脑 / 任意环境直接 `python archive_sync.py` 即可。

标题 / 标签 解析优先级（从高到低）
----------------------------------
  A. 同目录 sidecar JSON：海垦日报_YYYY-MM-DD.json 里写 {"title":..,"tags":[..]}
  B. HTML <head> 里的 <meta name="archive-title"> / <meta name="archive-tags">
     （推荐让自动化在生成 HTML 时顺手吐这两个 meta，标题就全自动了）
  C. 兜底：标题取 4 个板块 <h2> 拼接；标签取各板块 <span class="tag"> 分词

用法
----
  python archive_sync.py                 # 用默认路径跑
  python archive_sync.py --dry-run       # 只打印将要做什么，不写任何文件
  python archive_sync.py --source D:/x   # 指定日报源目录
  python archive_sync.py --archive D:/y  # 指定归档站目录（默认=本脚本所在目录）
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# ── 默认路径 ──────────────────────────────────────────────
# 归档站根目录 = 本脚本所在目录（haiken-archive/）
ARCHIVE_DIR = Path(__file__).resolve().parent
# 日报源目录（自动化产物落盘处）
SOURCE_DIR = Path(r"D:\Harry的文件")
ISSUES_DIR = ARCHIVE_DIR / "issues"
MANIFEST = ARCHIVE_DIR / "data" / "manifest.json"

# 源文件名匹配：海垦日报_2026-07-23.html
SRC_RE = re.compile(r"海垦日报_(\d{4}-\d{2}-\d{2})\.html$", re.IGNORECASE)

# HTML 解析正则
RE_SECTION_H2 = re.compile(r'<span class="no">板块\w+</span>\s*<h2>(.*?)</h2>', re.I | re.S)
RE_SECTION_TAG = re.compile(r'<span class="tag">(.*?)</span>', re.I | re.S)
RE_HTML_TITLE = re.compile(r"<title>(.*?)</title>", re.I | re.S)


def meta_content(html: str, name: str):
    """从 HTML 里取 <meta name="X" content="...">，属性顺序无关。"""
    tag_re = re.compile(r'<meta\b[^>]*\bname=["\']' + re.escape(name) + r'["\'][^>]*>', re.I)
    m = tag_re.search(html)
    if not m:
        return None
    cm = re.search(r'content=["\'](.*?)["\']', m.group(0), re.S)
    return cm.group(1).strip() if cm else None

TAG_SPLIT = re.compile(r"[/·、，,；;]+")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def split_tags(raw: str):
    if not raw:
        return []
    out, seen = [], set()
    for part in TAG_SPLIT.split(raw):
        p = part.strip()
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def derive_meta(html: str, sidecar: dict | None):
    """按 A→B→C 优先级拿到 (title, tags)。"""
    # A. sidecar JSON
    if isinstance(sidecar, dict):
        st = (sidecar.get("title") or "").strip()
        sg = sidecar.get("tags") or []
        if st or sg:
            return st or "海垦日报", list(sg) if isinstance(sg, list) else split_tags(str(sg))

    # B. HTML <meta>
    mt = meta_content(html, "archive-title")
    mg = meta_content(html, "archive-tags")
    if mt or mg:
        title = mt.strip() if mt else ""
        tags = split_tags(mg) if mg else []
        if title or tags:
            return title or "海垦日报", tags

    # C. 兜底：板块 h2 拼标题 + 板块 tag 分词
    h2s = [m.group(1).strip() for m in RE_SECTION_H2.finditer(html)]
    title = " · ".join(h2s) if h2s else "海垦日报"
    tags = []
    seen = set()
    for m in RE_SECTION_TAG.finditer(html):
        for t in split_tags(m.group(1)):
            if t not in seen:
                seen.add(t)
                tags.append(t)
    return title, tags[:6]


def next_issue_no(existing: list) -> str:
    max_n = 0
    for it in existing:
        try:
            max_n = max(max_n, int(str(it.get("issue_no", "0"))))
        except ValueError:
            pass
    return f"{max_n + 1:03d}"


def main():
    ap = argparse.ArgumentParser(description="海垦日报历史归档自动同步")
    ap.add_argument("--source", default=str(SOURCE_DIR), help="日报源目录")
    ap.add_argument("--archive", default=str(ARCHIVE_DIR), help="归档站根目录")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    args = ap.parse_args()

    src = Path(args.source)
    arc = Path(args.archive)
    issues = arc / "issues"
    manifest = arc / "data" / "manifest.json"

    if not src.exists():
        print(f"[ERROR] 源目录不存在：{src}")
        return 1
    issues.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)

    # 读现有 manifest（保留顶层字段 + 已归档期次）
    existing = []
    top = {}
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            existing = data.get("issues", []) or []
            top = {k: v for k, v in data.items() if k != "issues"}
        except Exception as e:
            print(f"[WARN] manifest 解析失败，将从头重建：{e}")

    existing_by_date = {it.get("date"): it for it in existing}

    # 扫源目录
    candidates = []
    for f in sorted(src.glob("海垦日报_*.html")):
        m = SRC_RE.search(f.name)
        if m:
            candidates.append((m.group(1), f))

    if not candidates:
        print(f"[INFO] 源目录 {src} 下未找到 海垦日报_YYYY-MM-DD.html")
        return 0

    added, updated, skipped = [], [], []
    merged = dict(existing_by_date)  # date -> entry（最终版）

    for date, f in candidates:
        html = load_text(f)
        sidecar_path = f.with_suffix(".json")
        sidecar = None
        if sidecar_path.exists():
            try:
                sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            except Exception:
                sidecar = None

        target = issues / f"{date}.html"
        cur_hash = sha256(f)

        if target.exists():
            if sha256(target) == cur_hash:
                skipped.append(date)
                # 保留已有条目（含人工标题）
                if date in merged:
                    pass
                continue
            else:
                # 内容有变 → 覆盖，但标题仍保留人工版（除非原本是兜底）
                updated.append(date)

        # 新一期 or 更新：解析元信息
        if date in existing_by_date:
            # 已存在：沿用旧 title/tags（非破坏），仅刷新文件
            entry = dict(existing_by_date[date])
        else:
            title, tags = derive_meta(html, sidecar)
            entry = {
                "date": date,
                "issue_no": next_issue_no(list(merged.values())),
                "title": title,
                "tags": tags,
                "file": f"issues/{date}.html",
            }

        if not args.dry_run:
            target.write_bytes(f.read_bytes())
        merged[date] = entry
        (added if date not in existing_by_date else updated).append(date)

    # 组装最终 manifest（日期降序）
    final_issues = sorted(merged.values(), key=lambda x: x.get("date", ""), reverse=True)
    out = dict(top)
    out["issues"] = final_issues
    if "_add_issue_help" not in out:
        out["_add_issue_help"] = (
            "新增一期：① 把日报HTML丢进 issues/（命名 YYYY-MM-DD.html）"
            "② 在 issues 数组顶部加一条 {date,issue_no,title,tags,file} ③ 刷新页面"
        )

    if not args.dry_run:
        manifest.write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # 汇报
    print(f"源目录   : {src}")
    print(f"归档站   : {arc}")
    print(f"新增     : {', '.join(added) if added else '无'}")
    print(f"更新     : {', '.join(updated) if updated else '无'}")
    print(f"跳过(一致): {', '.join(skipped) if skipped else '无'}")
    print(f"总计     : {len(final_issues)} 期")
    if args.dry_run:
        print("[DRY-RUN] 未写入任何文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
