#!/usr/bin/env python3
"""ai-coding-mines 정적 사이트 생성기.
mines/*.md 와 mines/en/*.md 의 각 ## 항목을 독립 HTML 페이지로 쪼갠다.
목적: 증상 문자열로 검색됐을 때 개별 페이지가 잡히게 하는 것.
사용: python3 build_site.py  →  site/ 생성
"""
import os, re, html, json, unicodedata

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "site")
BASE = "https://kohgane.github.io/ai-coding-mines"
REPO = "https://github.com/Kohgane/ai-coding-mines"

CATS = {
    "01-windows-powershell": ("Windows · PowerShell", "Windows and PowerShell"),
    "02-python-db":          ("Python · DB", "Python and databases"),
    "03-git-automation":     ("Git · 자동화", "Git and automation"),
    "04-claude-code-agent":  ("Claude Code · 에이전트", "Claude Code and agents"),
    "05-deploy-infra":       ("배포 · 인프라", "Deploy and infrastructure"),
    "06-write-api":          ("쓰기 API", "Write APIs"),
}

def slugify(text, seen=None):
    """URL은 ASCII만. 한글 제목은 안에 섞인 영문/코드 토큰을 우선 쓰고,
    없으면 안정적 해시로 대체한다 (퍼센트 인코딩 URL 회피)."""
    import hashlib
    t = unicodedata.normalize("NFKC", text).strip()
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_.\-]{1,}", t)
    stop = {"the","and","for","not","但","is","in","on","of","a","an","to"}
    tokens = [w for w in tokens if w.lower() not in stop][:5]
    base = re.sub(r"[^a-z0-9]+", "-", "-".join(tokens).lower()).strip("-")
    h = hashlib.sha1(t.encode("utf-8")).hexdigest()[:6]
    slug = f"{base}-{h}" if base else h
    return slug[:80]

def md_inline(s):
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s

def md_to_html(md):
    out, lines, i = [], md.split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            lang = ln[3:].strip()
            i += 1; buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(html.escape(lines[i])); i += 1
            out.append(f'<pre><code class="lang-{html.escape(lang)}">' + "\n".join(buf) + "</code></pre>")
        elif ln.startswith("|") and i + 1 < len(lines) and set(lines[i+1].replace("|","").strip()) <= set("-: "):
            hdr = [c.strip() for c in ln.strip("|").split("|")]
            i += 2; rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")]); i += 1
            th = "".join(f"<th>{md_inline(c)}</th>" for c in hdr)
            tb = "".join("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>")
            continue
        elif ln.startswith("> "):
            buf = []
            while i < len(lines) and lines[i].startswith("> "):
                buf.append(md_inline(lines[i][2:])); i += 1
            out.append("<blockquote>" + "<br>".join(buf) + "</blockquote>")
            continue
        elif ln.startswith("### "):
            out.append(f"<h3>{md_inline(ln[4:])}</h3>")
        elif re.match(r"^[-*] ", ln):
            buf = []
            while i < len(lines) and re.match(r"^[-*] ", lines[i]):
                buf.append(f"<li>{md_inline(lines[i][2:])}</li>"); i += 1
            out.append("<ul>" + "".join(buf) + "</ul>")
            continue
        elif re.match(r"^\d+\. ", ln):
            buf = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
                buf.append(f"<li>{md_inline(re.sub(r'^\d+\. ', '', lines[i]))}</li>"); i += 1
            out.append("<ol>" + "".join(buf) + "</ol>")
            continue
        elif ln.strip() == "---":
            out.append("<hr>")
        elif ln.strip():
            out.append(f"<p>{md_inline(ln)}</p>")
        i += 1
    return "\n".join(out)

CSS = """*{box-sizing:border-box}body{background:#0d0d0f;color:#e6e6e6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',sans-serif;line-height:1.75;margin:0;padding:0}
.wrap{max-width:760px;margin:0 auto;padding:48px 20px 96px}
a{color:#7aa2ff;text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:30px;line-height:1.35;margin:0 0 8px}h2{font-size:20px;margin:40px 0 12px}h3{font-size:16px;margin:28px 0 8px;color:#cfcfcf}
.meta{color:#8a8a92;font-size:13px;margin-bottom:32px}
.nav{font-size:13px;color:#8a8a92;margin-bottom:28px}
code{background:#1c1c21;padding:2px 6px;border-radius:4px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}
pre{background:#151519;border:1px solid #26262c;border-radius:8px;padding:14px;overflow-x:auto}pre code{background:none;padding:0;font-size:12.5px;line-height:1.6}
blockquote{border-left:3px solid #7aa2ff;margin:18px 0;padding:2px 0 2px 16px;color:#c8c8d0}
table{border-collapse:collapse;width:100%;margin:18px 0;font-size:14px}th,td{border:1px solid #26262c;padding:8px 10px;text-align:left;vertical-align:top}th{background:#17171c}
hr{border:0;border-top:1px solid #26262c;margin:32px 0}
ul,ol{padding-left:22px}li{margin:6px 0}
.cards{display:grid;gap:12px;margin:24px 0}
.card{border:1px solid #26262c;border-radius:10px;padding:14px 16px;background:#141418}
.card a{font-weight:600;font-size:15px}.card p{margin:6px 0 0;color:#9a9aa2;font-size:13.5px}
.tag{display:inline-block;background:#1c1c21;color:#9a9aa2;font-size:11.5px;padding:2px 8px;border-radius:99px;margin-right:6px}
footer{margin-top:64px;padding-top:24px;border-top:1px solid #26262c;color:#7a7a82;font-size:13px}
.hero{border-left:3px solid #ff453a;padding-left:16px;margin:24px 0;color:#c8c8d0}"""

def page(title, desc, body, canonical, lang="ko", extra_head=""):
    return f"""<!doctype html><html lang="{lang}"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc[:180])}">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc[:180])}">
<meta property="og:type" content="article">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary">
{extra_head}<style>{CSS}</style></head><body><div class="wrap">{body}
<footer>ai-coding-mines · <a href="{REPO}">GitHub</a> · CC BY 4.0<br>
AI 코딩 에이전트로 개발하며 실제로 밟은 함정들.</footer></div></body></html>"""

def parse(path):
    """파일을 ## 단위 항목으로 쪼갠다."""
    raw = open(path, encoding="utf-8").read()
    m = re.search(r"^# (.+)$", raw, re.M)
    file_title = m.group(1).strip() if m else os.path.basename(path)
    parts = re.split(r"^## ", raw, flags=re.M)
    intro = parts[0]
    intro = re.sub(r"^# .+$", "", intro, count=1, flags=re.M).strip()
    items = []
    for p in parts[1:]:
        lines = p.split("\n")
        t = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        first = next((l for l in body.split("\n") if l.strip() and not l.startswith(("|","```",">","#"))), "")
        desc = re.sub(r"[*`\[\]]", "", first)[:180]
        items.append({"title": t, "slug": slugify(t), "body": body, "desc": desc})
    return file_title, intro, items

def en_slug_map():
    """영어판에서 파일별 항목 슬러그를 뽑아둔다. 한국어판이 같은 순번에 재사용해
    ko/en 양쪽 URL이 모두 의미 있는 ASCII가 되게 한다."""
    m = {}
    d = os.path.join(ROOT, "mines", "en")
    if not os.path.isdir(d): return m
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".md"): continue
        _, _, items = parse(os.path.join(d, fn))
        m[fn[:-3]] = [slugify(i["title"]) for i in items]
    return m

def build():
    os.makedirs(OUT, exist_ok=True)
    ENSLUG = en_slug_map()
    all_items, urls = [], []
    for lang, src_dir, prefix in [("ko", "mines", ""), ("en", "mines/en", "en/")]:
        d = os.path.join(ROOT, src_dir)
        if not os.path.isdir(d): continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".md"): continue
            key = fn[:-3]
            cat_ko, cat_en = CATS.get(key, (key, key))
            cat = cat_ko if lang == "ko" else cat_en
            ftitle, intro, items = parse(os.path.join(d, fn))
            if lang == "ko" and key in ENSLUG and len(ENSLUG[key]) == len(items):
                for idx, it in enumerate(items):
                    it["slug"] = ENSLUG[key][idx]
            used = set()
            for it in items:
                s, n2 = it["slug"], 2
                while s in used:
                    s = f"{it['slug']}-{n2}"; n2 += 1
                it["slug"] = s; used.add(s)
            catdir = os.path.join(OUT, prefix + key)
            os.makedirs(catdir, exist_ok=True)
            # 카테고리 인덱스
            cards = "".join(
                f'<div class="card"><a href="{i["slug"]}/">{html.escape(i["title"])}</a>'
                f'<p>{html.escape(i["desc"])}</p></div>' for i in items)
            cat_url = f"{BASE}/{prefix}{key}/"
            body = (f'<div class="nav"><a href="{BASE}/{prefix if prefix else ""}">← {"전체 목록" if lang=="ko" else "All categories"}</a></div>'
                    f'<h1>{html.escape(ftitle)}</h1>'
                    f'<div class="meta">{len(items)} {"개 항목" if lang=="ko" else "entries"}</div>'
                    f'{md_to_html(intro)}<div class="cards">{cards}</div>')
            open(os.path.join(catdir, "index.html"), "w", encoding="utf-8").write(
                page(f"{ftitle} — ai-coding-mines", intro[:180] or ftitle, body, cat_url, lang))
            urls.append(cat_url)
            # 개별 항목 페이지 — 검색 유입의 본체
            for n, it in enumerate(items):
                idir = os.path.join(catdir, it["slug"]); os.makedirs(idir, exist_ok=True)
                url = f"{cat_url}{it['slug']}/"
                prev_next = []
                if n > 0: prev_next.append(f'<a href="../{items[n-1]["slug"]}/">← {html.escape(items[n-1]["title"][:40])}</a>')
                if n < len(items)-1: prev_next.append(f'<a href="../{items[n+1]["slug"]}/">{html.escape(items[n+1]["title"][:40])} →</a>')
                ld = json.dumps({"@context":"https://schema.org","@type":"TechArticle",
                                 "headline":it["title"],"description":it["desc"],
                                 "articleSection":cat,"url":url,
                                 "author":{"@type":"Person","name":"Kohgane"},
                                 "license":"https://creativecommons.org/licenses/by/4.0/"}, ensure_ascii=False)
                body = (f'<div class="nav"><a href="{BASE}/{prefix if prefix else ""}">ai-coding-mines</a> / '
                        f'<a href="{cat_url}">{html.escape(cat)}</a></div>'
                        f'<h1>{html.escape(it["title"])}</h1>'
                        f'<div class="meta"><span class="tag">{html.escape(cat)}</span></div>'
                        f'{md_to_html(it["body"])}'
                        f'<hr><div class="nav">{" · ".join(prev_next)}</div>')
                open(os.path.join(idir, "index.html"), "w", encoding="utf-8").write(
                    page(f'{it["title"]} — ai-coding-mines', it["desc"] or it["title"], body, url, lang,
                         f'<script type="application/ld+json">{ld}</script>'))
                urls.append(url)
                all_items.append({"lang":lang,"cat":cat,"title":it["title"],"url":url,"desc":it["desc"]})
    # 루트 인덱스 (ko / en)
    for lang, prefix in [("ko",""), ("en","en/")]:
        items = [i for i in all_items if i["lang"]==lang]
        if not items: continue
        bycat = {}
        for i in items: bycat.setdefault(i["cat"], []).append(i)
        secs = ""
        for cat, its in bycat.items():
            links = "".join(f'<li><a href="{it["url"]}">{html.escape(it["title"])}</a></li>' for it in its)
            secs += f"<h2>{html.escape(cat)}</h2><ul>{links}</ul>"
        if lang == "ko":
            hero = ("<h1>AI 코딩 지뢰 도감</h1>"
                    '<div class="hero">AI 코딩 에이전트로 개발하며 <strong>실제로 밟은</strong> 함정 기록. '
                    "절반 이상이 조용한 실패 — 200이 오고, 종료 코드는 0이고, 에이전트는 완료했다고 하는데 아무 일도 없었던 것들.</div>"
                    f'<p><a href="{BASE}/en/">English</a> · <a href="{REPO}">GitHub</a></p>')
            desc = "AI 코딩 에이전트로 개발하며 실제로 밟은 함정 기록. 증상 → 원인 → 해법."
        else:
            hero = ("<h1>AI Coding Landmines</h1>"
                    '<div class="hero">Traps I <strong>actually stepped on</strong> while building with AI coding agents. '
                    "More than half are silent failures — 200 OK, exit code 0, agent says done, nothing happened.</div>"
                    f'<p><a href="{BASE}/">한국어</a> · <a href="{REPO}">GitHub</a></p>')
            desc = "Traps actually stepped on while building with AI coding agents. Symptom, cause, fix."
        url = f"{BASE}/{prefix}"
        open(os.path.join(OUT, prefix, "index.html") if prefix else os.path.join(OUT, "index.html"),
             "w", encoding="utf-8").write(page(
            "AI 코딩 지뢰 도감" if lang=="ko" else "AI Coding Landmines — a field guide",
            desc, hero + f'<div class="meta">{len(items)} entries</div>' + secs, url, lang))
        urls.append(url)
    # sitemap / robots
    sm = "".join(f"<url><loc>{u}</loc></url>" for u in sorted(set(urls)))
    open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8").write(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>')
    open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8").write(
        f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    open(os.path.join(OUT, ".nojekyll"), "w").write("")
    print(f"pages: {len(set(urls))}  items: {len(all_items)}")

if __name__ == "__main__":
    build()
