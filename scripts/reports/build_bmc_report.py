#!/usr/bin/env python3
"""BMC 내부 보고서 md 를 HTML · A4 PDF 로 만든다 (BMC 보고서 작성 규정 · 생성 스크립트 원칙).

정본은 md 다. HTML · PDF 는 이 스크립트의 산출물이므로 직접 고치지 않는다 — md 를 고치고 다시 만든다.
md 는 이 저장소 보고서가 쓰는 부분 집합만 읽는다: ``#``–``###`` 제목, 표, 2 단 불릿 (2 칸 또는 탭 들여쓰기),
번호 목록, 코드 블록, ``---``, 굵게 · 인라인 코드. 첫 표 (항목 | 내용) 는 표지 정보로 쓴다.

색 · 표지 모티프는 bmc-report-style skill 의 ``build_report_ext.py`` 를 따랐다. 외부 15 면판과 달리
면을 손으로 나누지 않고 흐름 조판한다 (내부 보고서는 분량 제한 없음).

PDF 와 조판 점검에는 Playwright (Chromium) 가 필요하다. 저장소 venv 를 건드리지 않도록 일회용 환경으로 돈다:

Usage:
    uv run --no-project --with playwright==1.63.0 python scripts/reports/build_bmc_report.py \
        results/i1/reports/i1_report_2026-10-13.md --pdf --text-dump <scratch>/report_text.txt
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path
from typing import List, Tuple

ISSUER_KO = ("서울아산병원 아산생명과학연구원", "융합연구지원센터 바이오메디컬컴퓨팅코어")
CONTENT_WIDTH_MM = 210 - 20 - 16  # A4 폭 − 왼쪽 · 오른쪽 여백 (@page 와 같게)

CSS = """
:root{
  --brand:#14416E; --brand-soft:#E7EEF6; --accent:#1F8A8C; --accent-soft:#E2F1F1;
  --ink:#10151C; --ink-2:#3C4654; --ink-3:#6B7787; --line:#D3DBE4;
  --paper:#FFFFFF; --wash:#F2F5F8; --warn:#B37500;
  --disp:"Nanum Myeongjo","NanumMyeongjo","AppleMyungjo",serif;
  --body:"Pretendard","Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif;
  --data:"SF Mono","Menlo","D2Coding","Consolas",monospace;
}
*{box-sizing:border-box;}
html{background:var(--paper);}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--body);
     font-size:9.6pt;line-height:1.6;-webkit-font-smoothing:antialiased;word-break:keep-all;}
p,li{overflow-wrap:anywhere;}
td{overflow-wrap:break-word;}
main{max-width:174mm;margin:0 auto;padding:0 0 12mm;}
@media screen{
  body{background:#E9EDF1;}
  .sheet{background:var(--paper);max-width:210mm;margin:16px auto;padding:18mm 16mm 14mm 20mm;
         box-shadow:0 2px 24px rgba(16,21,28,.12);}
  @media (max-width:820px){ .sheet{padding:16px;margin:0;} table{display:block;overflow-x:auto;} pre{font-size:7pt;} }
}
h2{font-family:var(--disp);font-size:15.5pt;font-weight:700;color:var(--brand);margin:10mm 0 3mm;
   padding-bottom:2mm;border-bottom:1.6px solid var(--brand);break-after:avoid;}
h3{font-size:10.8pt;font-weight:700;color:var(--brand);margin:6mm 0 2mm;padding-left:3mm;
   border-left:3px solid var(--accent);break-after:avoid;}
p{margin:0 0 2.4mm;}
ul,ol{margin:0 0 3mm;padding-left:5.5mm;}
li{margin:0 0 1mm;}
li::marker{color:var(--accent);}
ul ul{margin:1mm 0 1.4mm;padding-left:5mm;}
ul ul li::marker{color:var(--ink-3);content:"– ";}
b,strong{font-weight:700;color:var(--ink);}
code{font-family:var(--data);font-size:.86em;background:var(--wash);padding:0 .8mm;border-radius:2px;}
pre{font-family:var(--data);font-size:7.4pt;line-height:1.5;background:var(--wash);border:.6px solid var(--line);
    border-left:3px solid var(--accent);padding:3mm;white-space:pre-wrap;overflow-wrap:anywhere;break-inside:avoid;}
pre code{background:none;padding:0;font-size:inherit;}
th code{background:rgba(255,255,255,.16);color:#fff;}
table{width:100%;border-collapse:collapse;font-size:8.3pt;margin:2mm 0 4mm;}
thead{display:table-header-group;}
tr{break-inside:avoid;}
th{background:var(--brand);color:#fff;font-weight:600;text-align:left;padding:1.6mm 2mm;font-size:8pt;}
td{padding:1.4mm 2mm;border-bottom:.6px solid var(--line);vertical-align:top;}
tbody tr:nth-child(even) td{background:var(--wash);}
th.n{text-align:right;}
td.c,th.c{white-space:nowrap;}
td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap;}
.ci{font-family:var(--data);font-size:7.6pt;white-space:nowrap;}
.ci small{display:block;color:var(--ink-3);font-size:7pt;}
table.wide{font-size:7.6pt;}
table.wide td,table.wide th{padding:1.2mm 1.4mm;}
hr{border:0;border-top:.6px solid var(--line);margin:6mm 0;}

/* 표지 */
.cover{position:relative;height:297mm;width:210mm;margin:0 auto;background:var(--wash);overflow:hidden;
       break-after:page;}
.cover .bar{height:9mm;background:var(--brand);}
.cover .inner{padding:20mm 20mm 0;}
.cover .kicker{font-size:8.4pt;letter-spacing:.3em;color:var(--accent);font-weight:700;}
.cover .issuer-top{font-size:8.6pt;color:var(--ink-3);margin-top:1.5mm;}
.cover h1{font-family:var(--disp);font-size:27pt;font-weight:700;line-height:1.36;color:var(--brand);
          margin:10mm 0 0;letter-spacing:-.02em;max-width:128mm;word-break:keep-all;}
.cover .sub{font-size:11pt;color:var(--ink-2);margin-top:5mm;max-width:118mm;line-height:1.6;}
.cover .meta{position:absolute;left:20mm;bottom:42mm;font-size:9pt;color:var(--ink-2);}
.cover .meta div{margin-bottom:1.4mm;}
.cover .meta span{display:inline-block;width:26mm;color:var(--ink-3);}
.cover .issuer{position:absolute;left:20mm;right:20mm;bottom:14mm;padding-top:4mm;border-top:2px solid var(--brand);
               display:flex;justify-content:space-between;align-items:flex-end;gap:6mm;}
.cover .issuer .org{font-family:var(--disp);font-size:12pt;color:var(--brand);font-weight:700;}
.cover .issuer .org small{display:block;font-family:var(--body);font-size:8.2pt;font-weight:400;color:var(--ink-3);margin-top:1mm;}
.cover .issuer .en{font-size:7.4pt;color:var(--ink-3);text-align:right;max-width:80mm;line-height:1.45;}
.cover .motif{position:absolute;right:-22mm;top:92mm;width:150mm;height:150mm;}
@media screen{ .cover{box-shadow:0 2px 24px rgba(16,21,28,.12);margin:16px auto;}
  @media (max-width:820px){ .cover{width:100%;height:auto;min-height:100vh;} .cover .meta,.cover .issuer{position:static;margin:8mm 20mm 0;} .cover .motif{display:none;} } }

/* 목차 */
.toc{break-after:page;}
.toc ol{list-style:none;padding:0;margin:4mm 0 0;}
.toc li{display:flex;gap:3mm;padding:2.2mm 0;border-bottom:.6px solid var(--line);font-size:10pt;}
.toc .no{font-family:var(--disp);color:var(--accent);width:14mm;flex:none;}
.toc a{color:var(--ink);text-decoration:none;}

@page{size:A4;margin:18mm 16mm 18mm 20mm;
  @bottom-left{content:"__FOOT_LEFT__";font-family:"Pretendard","Apple SD Gothic Neo",sans-serif;font-size:7.4pt;color:#6B7787;}
  @bottom-right{content:"바이오메디컬컴퓨팅코어 · " counter(page) " / " counter(pages);
    font-family:"Pretendard","Apple SD Gothic Neo",sans-serif;font-size:7.4pt;color:#6B7787;}}
@page :first{margin:0; @bottom-left{content:none;} @bottom-right{content:none;}}
@media print{
  html,body{background:#fff;}
  .sheet{padding:0;margin:0;box-shadow:none;max-width:none;}
  .cover{margin:0;box-shadow:none;}
  h2.appendix{break-before:page;}
  a{color:inherit;text-decoration:none;}
}
"""

MOTIF = """<svg class="motif" viewBox="0 0 400 400" aria-hidden="true">
  <defs><radialGradient id="g1" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#1F8A8C" stop-opacity=".16"/><stop offset="100%" stop-color="#1F8A8C" stop-opacity="0"/>
  </radialGradient></defs>
  <circle cx="200" cy="200" r="185" fill="url(#g1)"/>
  <g fill="none" stroke="#14416E" stroke-opacity=".22"><circle cx="200" cy="200" r="72"/><circle cx="200" cy="200" r="118"/><circle cx="200" cy="200" r="164"/></g>
  <g stroke="#1F8A8C" stroke-opacity=".55" stroke-width="1.1" fill="none">
    <path d="M200 200 C 150 130, 90 140, 66 176"/><path d="M200 200 C 262 152, 316 178, 330 224"/>
    <path d="M200 200 C 178 268, 118 292, 78 268"/><path d="M200 200 C 246 262, 236 320, 200 348"/>
    <path d="M200 200 C 150 176, 118 104, 146 52"/></g>
  <g fill="#14416E"><circle cx="200" cy="200" r="8.5"/><circle cx="66" cy="176" r="5"/><circle cx="330" cy="224" r="5"/>
    <circle cx="78" cy="268" r="4.2"/><circle cx="200" cy="348" r="4.2"/><circle cx="146" cy="52" r="4.2"/></g>
  <g fill="#1F8A8C" fill-opacity=".85"><circle cx="284" cy="112" r="3"/><circle cx="112" cy="118" r="3"/>
    <circle cx="300" cy="300" r="3"/><circle cx="104" cy="316" r="2.4"/><circle cx="356" cy="164" r="2.4"/><circle cx="44" cy="222" r="2.4"/></g>
</svg>"""

# Δ [CI] — 점추정 밑에 CI 를 한 줄로 내린다 (좁은 열에서 숫자가 쪼개지지 않게)
CI_RE = re.compile(r"([+\-−]\d+\.\d+) (\[[+\-−]\d+\.\d+, [+\-−]\d+\.\d+\])")
NUM_RE = re.compile(r"^[+\-−]?[\d,]+(\.\d+)?$")


def inline(s: str) -> str:
    """인라인 표기 (코드 · 굵게) 를 HTML 로 바꾼다. 코드 안은 굵게로 해석하지 않는다."""
    parts = re.split(r"(`[^`]+`)", s)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append(f"<code>{html.escape(p[1:-1])}</code>")
        else:
            e = html.escape(p, quote=False)
            out.append(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", e))
    return "".join(out)


def cell(s: str) -> Tuple[str, str]:
    """표 칸 하나를 (class, HTML) 로 만든다."""
    s = s.strip()
    if NUM_RE.match(s):
        return "n", inline(s)
    body = inline(s)
    body = CI_RE.sub(r'<span class="ci">\1<small>\2</small></span>', body)
    return "", body


def split_row(line: str) -> List[str]:
    """``| a | b |`` 를 칸 목록으로 나눈다."""
    return [c for c in line.strip().strip("|").split("|")]


def slug(i: int) -> str:
    return f"s{i}"


def render(md: str) -> Tuple[str, str, List[Tuple[str, str]], List[Tuple[str, str]], str]:
    """md 본문을 HTML 로 바꾼다.

    Returns:
        (제목, 본문 HTML, 표지 정보 [(항목, 내용)], 목차 [(id, 제목)], 꼬리말 왼쪽 문구).
    """
    lines = md.splitlines()
    title = ""
    meta: List[Tuple[str, str]] = []
    toc: List[Tuple[str, str]] = []
    out: List[str] = []
    i = 0
    list_stack: List[str] = []  # 열린 목록 태그 ("ul"/"ol") 의 깊이별 목록

    def close_lists(depth: int = 0) -> None:
        while len(list_stack) > depth:
            out.append(f"</li></{list_stack.pop()}>")

    n_h2 = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# ") and not title:
            title = ln[2:].strip()
            i += 1
            continue
        if ln.startswith("```"):
            close_lists()
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            out.append(f"<pre><code>{html.escape(chr(10).join(buf))}</code></pre>")
            i += 1
            continue
        if ln.startswith("|"):
            close_lists()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            head, body = rows[0], [r for r in rows[2:]]
            if not meta and [h.strip() for h in head] == ["항목", "내용"] and not toc:
                meta = [(r[0].strip(), r[1].strip()) for r in body]
                continue
            wide = " class=\"wide\"" if len(head) >= 6 else ""
            # 열 단위 표기: 전부 숫자면 오른쪽 정렬, 짧은 열 (12 자 이하) 은 줄바꿈 금지
            ncol = len(head)
            col_num = [all(NUM_RE.match(r[j].strip()) or r[j].strip() in ("", "—") for r in body if j < len(r))
                       and any(NUM_RE.match(r[j].strip()) for r in body if j < len(r)) for j in range(ncol)]
            col_short = [max([len(h.strip()) for h in [head[j]]] + [len(r[j].strip()) for r in body if j < len(r)]) <= 12
                         for j in range(ncol)]
            th_cls = ["n" if col_num[j] else ("c" if col_short[j] else "") for j in range(ncol)]
            t = [f"<table{wide}><thead><tr>" + "".join(
                (f'<th class="{th_cls[j]}">' if th_cls[j] else "<th>") + f"{inline(h.strip())}</th>"
                for j, h in enumerate(head)) + "</tr></thead><tbody>"]
            for r in body:
                tds = []
                for j, c in enumerate(r):
                    cls, h = cell(c)
                    if not cls and j < ncol and col_short[j]:
                        cls = "c"
                    tds.append(f'<td class="{cls}">{h}</td>' if cls else f"<td>{h}</td>")
                t.append("<tr>" + "".join(tds) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.) (.*)$", ln)
        if m:
            indent = len(m.group(1).replace("\t", "  "))
            depth = 1 if indent == 0 else 2
            tag = "ol" if m.group(2)[0].isdigit() else "ul"
            if len(list_stack) < depth:
                out.append(f"<{tag}><li>")
                list_stack.append(tag)
            else:
                close_lists(depth)
                if list_stack[-1] != tag:
                    close_lists(depth - 1)
                    out.append(f"<{tag}><li>")
                    list_stack.append(tag)
                else:
                    out.append("</li><li>")
            out.append(inline(m.group(3)))
            i += 1
            continue
        if list_stack and ln.startswith("  ") and ln.strip():
            out.append(" " + inline(ln.strip()))  # 목록 항목의 이어지는 줄
            i += 1
            continue
        close_lists()
        if ln.startswith("## "):
            n_h2 += 1
            txt = ln[3:].strip()
            cls = ' class="appendix"' if txt.startswith("첨부") else ""
            toc.append((slug(n_h2), txt))
            out.append(f'<h2 id="{slug(n_h2)}"{cls}>{inline(txt)}</h2>')
        elif ln.startswith("### "):
            out.append(f"<h3>{inline(ln[4:].strip())}</h3>")
        elif ln.strip() == "---":
            pass  # 장 구분은 h2 가 맡는다
        elif ln.strip():
            out.append(f"<p>{inline(ln.strip())}</p>")
        i += 1
    close_lists()
    foot = title.split(" — ")[0] if " — " in title else title
    return title, "\n".join(out), meta, toc, foot


def build_html(md_path: Path) -> str:
    """md 파일 하나로 완결된 HTML 문서를 만든다."""
    title, body, meta, toc, foot = render(md_path.read_text(encoding="utf-8"))
    md = dict(meta)
    date_ver = md.get("보고일자 · 판", "")
    head, _, rest = title.partition(" — ")
    kicker = "내 부 보 고"
    meta_rows = "".join(f"<div><span>{html.escape(k)}</span>{inline(v)}</div>"
                        for k, v in meta if k in ("연구책임자", "보고일자 · 판", "보고 성격"))
    en = next((v for k, v in meta if k == "" and "Asan" in v), "")
    cover = f"""<section class="cover"><div class="bar"></div><div class="inner">{MOTIF}
<div class="kicker">{kicker}</div>
<div class="issuer-top">{inline(head)}</div>
<h1>{inline(rest or title)}</h1>
<p class="sub">{inline(md.get('과제명', ''))}</p></div>
<div class="meta">{meta_rows}</div>
<div class="issuer"><div class="org">{ISSUER_KO[0]}<small>{ISSUER_KO[1]}</small></div>
<div class="en">{html.escape(en)}</div></div></section>"""
    toc_html = '<nav class="toc"><h2>목차</h2><ol>' + "".join(
        f'<li><span class="no">{html.escape(t.split(".")[0] if t[0].isdigit() else "")}</span>'
        f'<a href="#{sid}">{inline(t.split(". ", 1)[1] if t[0].isdigit() and ". " in t else t)}</a></li>'
        for sid, t in toc) + "</ol></nav>"
    foot_text = f"{foot} · {date_ver}".replace('"', "'")
    css = CSS.replace("__FOOT_LEFT__", foot_text)
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="scripts/reports/build_bmc_report.py — 원본 {html.escape(md_path.name)}">
<title>{html.escape(head or title)}</title>
<style>{css}</style></head>
<body>{cover}<div class="sheet"><main>{toc_html}
{body}
</main></div></body></html>
"""


def check_and_print(html_path: Path, pdf_path: Path | None, text_dump: Path | None) -> int:
    """Chromium 으로 조판을 점검하고 (넘치는 표 · 코드 · 글꼴) 필요하면 PDF 와 본문 텍스트를 만든다.

    Returns:
        넘친 요소 수 + 빠진 글꼴 수. 0 이면 통과.
    """
    from playwright.sync_api import sync_playwright

    px = round(CONTENT_WIDTH_MM / 25.4 * 96)
    bad = 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": px, "height": 1200})
        pg.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        pg.emulate_media(media="print")
        pg.evaluate("document.fonts.ready")
        over = pg.evaluate("""(w) => Array.from(document.querySelectorAll('main table, main pre, main p, main li'))
          .filter(e => e.scrollWidth > e.clientWidth + 1 || e.getBoundingClientRect().right > w + 1)
          .map(e => e.tagName + ': ' + e.innerText.slice(0, 60).replace(/\\s+/g,' '))""", px)
        for o in over:
            print("OVERFLOW", o)
        bad += len(over)
        fonts = pg.evaluate("""() => ['Pretendard','Nanum Myeongjo'].map(f => [f, document.fonts.check('12px "'+f+'"')])""")
        for f, ok in fonts:
            print(f"글꼴 {f}: {'있음' if ok else '없음 (대체 글꼴로 나옴)'}")
        if text_dump:
            txt = pg.evaluate("document.body.innerText")
            text_dump.write_text(re.sub(r"\s+", " ", txt), encoding="utf-8")
            print("text dump", text_dump)
        if pdf_path:
            pg.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True,
                   display_header_footer=False)
            print("wrote", pdf_path, f"{pdf_path.stat().st_size / 1e6:.2f} MB")
        b.close()
    print("넘친 요소", len(over))
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("md", type=Path)
    ap.add_argument("--pdf", action="store_true", help="같은 이름의 .pdf 도 만든다")
    ap.add_argument("--no-check", action="store_true", help="Chromium 점검을 건너뛴다 (HTML 만)")
    ap.add_argument("--text-dump", type=Path, help="렌더된 본문 텍스트 (공백 정규화) 를 쓸 경로 — 인용 대조용")
    a = ap.parse_args()
    out_html = a.md.with_suffix(".html")
    out_html.write_text(build_html(a.md), encoding="utf-8")
    print("wrote", out_html)
    if a.no_check:
        return 0
    return 1 if check_and_print(out_html, a.md.with_suffix(".pdf") if a.pdf else None, a.text_dump) else 0


if __name__ == "__main__":
    sys.exit(main())
