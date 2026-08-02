#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 data/index.json：抽取每期日报正文纯文本，供 SPA 搜索「右侧内容关键词」。

读取 data/manifest.json 拿到元数据（date/issue_no/title/tags），
再逐期 issues/<date>.html 抽正文文本（去掉 <style>/<script>，去标签），
输出 data/index.json：{ issues: [{date,issue_no,title,tags,text}] }
"""
import json
import re
from html.parser import HTMLParser
from pathlib import Path

BASE = Path(__file__).resolve().parent
MANIFEST = BASE / "data" / "manifest.json"
ISSUES = BASE / "issues"
OUT = BASE / "data" / "index.json"


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip = 0          # 嵌套计数，用于跳过 style/script
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._skip += 1
        elif tag in ("br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4", "td", "th"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            t = data.strip()
            if t:
                self.parts.append(t)


def extract_text(html: str) -> str:
    p = TextExtractor()
    try:
        p.feed(html)
    except Exception:
        # 兜底：去标签
        txt = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", txt).strip()
    text = " ".join(p.parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def main():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    issues = data.get("issues", [])
    out = []
    for it in issues:
        date = it.get("date")
        f = ISSUES / f"{date}.html"
        text = ""
        if f.exists():
            text = extract_text(f.read_text(encoding="utf-8", errors="ignore"))
        out.append({
            "date": date,
            "issue_no": it.get("issue_no"),
            "title": it.get("title", ""),
            "tags": it.get("tags", []),
            "text": text,
        })
    OUT.write_text(json.dumps({"issues": out}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total_chars = sum(len(x["text"]) for x in out)
    print(f"已生成 {OUT.name}：{len(out)} 期，正文总计 {total_chars} 字符。")


if __name__ == "__main__":
    main()
