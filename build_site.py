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

CSS = """*{box-sizing:border-box}
:root{--bg:#0f1013;--fg:#eaeaef;--dim:#9a9aa6;--faint:#6d6e79;--line:#26272e;--card:#16171b;--accent:#7aa2ff;--red:#ff6b60;--redbg:#241416}
body{background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',sans-serif;line-height:1.7;margin:0;font-size:16px;-webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding:36px 20px 96px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:33px;line-height:1.24;margin:0 0 14px;letter-spacing:-.025em;font-weight:650}
h2{font-size:19px;margin:46px 0 14px;letter-spacing:-.01em;font-weight:600}
h3{font-size:16px;margin:28px 0 8px;color:#cfcfd8}
.meta{color:var(--dim);font-size:13.5px}
.nav{font-size:13.5px;color:var(--dim);margin-bottom:24px}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:34px;font-size:13px;color:var(--faint)}
.topbar .brand{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.topbar span a{color:var(--dim);margin-left:14px}
.kicker{font-size:13px;color:var(--red);margin-bottom:9px;letter-spacing:.01em}
.lead{font-size:17px;color:#c3c3ce;margin:0 0 26px;line-height:1.65;max-width:56ch}
.ev{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:0 0 30px}
.ev div{background:var(--redbg);border-radius:10px;padding:13px 15px}
.ev .m{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;color:var(--red);margin-bottom:4px}
.ev .s{font-size:13px;color:#c8a5a2}
.searchbox{position:relative;margin-bottom:9px}
#q{width:100%;background:var(--card);border:1px solid var(--line);border-radius:10px;color:var(--fg);padding:13px 15px;font-size:15px;font-family:inherit}
#q:focus{outline:none;border-color:var(--accent)}
.chips{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:8px}
.chip{font-size:12.5px;color:var(--dim);border:1px solid var(--line);border-radius:99px;padding:5px 12px;cursor:pointer;background:none;font-family:inherit}
.chip:hover{border-color:#3d3f4a;color:var(--fg)}
.hint{color:var(--faint);font-size:12.5px;margin:0 0 26px}
code{background:#1d1e24;padding:2px 6px;border-radius:5px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13.5px}
pre{background:#131418;border:1px solid var(--line);border-radius:10px;padding:16px;overflow-x:auto}
pre code{background:none;padding:0;font-size:13px;line-height:1.65}
blockquote{border-left:3px solid var(--accent);margin:20px 0;padding:2px 0 2px 18px;color:#c9c9d4}
table{border-collapse:collapse;width:100%;margin:20px 0;font-size:14.5px}
th,td{border:1px solid var(--line);padding:9px 12px;text-align:left;vertical-align:top}
th{background:#1a1b21}
hr{border:0;border-top:1px solid var(--line);margin:34px 0}
ul,ol{padding-left:22px}li{margin:7px 0}
.cats{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;margin:22px 0}
.cat{border:1px solid var(--line);border-radius:12px;padding:16px 18px;background:var(--card);transition:border-color .15s}
.cat:hover{border-color:#3d3f4a}
.cat .ic{font-size:19px;color:var(--faint);line-height:1}
.cat a{font-weight:600;font-size:15.5px;display:block;margin:9px 0 3px}
.cat p{margin:0;color:var(--dim);font-size:13px;line-height:1.55}
.cat .n{color:var(--faint);font-size:12px;margin-top:9px;display:block}
.cat.hot{border:1px solid #2f4a7a}
.badge{float:right;background:#16233d;color:#8fb4ff;font-size:11px;padding:3px 9px;border-radius:6px}
.cards{display:grid;gap:11px;margin:18px 0}
.card{border:1px solid var(--line);border-radius:10px;padding:14px 16px;background:var(--card)}
.card a{font-weight:600;font-size:15.5px}
.card p{margin:5px 0 0;color:var(--dim);font-size:13.5px}
.tag{display:inline-block;background:#1d1e24;color:var(--dim);font-size:11.5px;padding:3px 9px;border-radius:99px;margin-right:6px}
#hits{margin:0 0 8px}#hits .card{margin-bottom:9px}
footer{margin-top:76px;padding-top:26px;border-top:1px solid var(--line);color:#75767f;font-size:13px;line-height:1.8}
@media(max-width:600px){.wrap{padding:26px 16px 72px}h1{font-size:26px}body{font-size:15.5px}}"""

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
                all_items.append({"lang":lang,"cat":cat,"catkey":key,"title":it["title"],"url":url,"desc":it["desc"]})
    # 루트 인덱스 (ko / en)
    CATMETA = {
        "01-windows-powershell": ("&#9632;", "셸이 조용히 값을 바꾸는 자리",
                                  "Where the shell quietly changes your values"),
        "02-python-db":          ("&#9670;", "데이터는 맞는데 결과가 틀릴 때",
                                  "When the data is right but the result isn't"),
        "03-git-automation":     ("&#9679;", "무인으로 도는 것이 멈추는 법",
                                  "How unattended things stop without telling you"),
        "04-claude-code-agent":  ("&#9650;", "완료라고 말할 때 실제로 일어난 일",
                                  "What actually happened when it said done"),
        "05-deploy-infra":       ("&#9724;", "크론과 외부 서비스의 보이지 않는 벽",
                                  "Invisible walls in crons and external services"),
        "06-write-api":          ("&#9673;", "성공 응답이 거짓말하는 방식",
                                  "The ways a success response lies"),
    }
    CHIPS_KO = ["한글 깨짐", "exit 0", "200", "훅", "크론", "인코딩"]
    CHIPS_EN = ["exit 0", "200 but", "hook", "cron", "encoding", "silent"]
    for lang, prefix in [("ko",""), ("en","en/")]:
        items = [i for i in all_items if i["lang"]==lang]
        if not items: continue
        bycat = {}
        for i in items: bycat.setdefault(i["catkey"], []).append(i)
        cards = ""
        for key in sorted(bycat):
            its = bycat[key]
            name = CATS.get(key, (key,key))[0 if lang=="ko" else 1]
            ic, dko, den = CATMETA.get(key, ("&#9632;","",""))
            d = dko if lang=="ko" else den
            unit = "개 항목" if lang=="ko" else "entries"
            hot = key == "06-write-api"
            badge = ('<span class="badge">' + ("많이 읽힘" if lang=="ko" else "most read") + '</span>') if hot else ""
            cards += ('<div class="cat' + (' hot' if hot else '') + '">' + badge
                      + '<span class="ic">' + ic + '</span>'
                      + '<a href="' + BASE + '/' + prefix + key + '/">' + html.escape(name) + '</a>'
                      + '<p>' + html.escape(d) + '</p>'
                      + '<span class="n">' + str(len(its)) + ' ' + unit + '</span></div>')
        idx = json.dumps([{"t":i["title"],"u":i["url"],
                           "c":CATS.get(i["catkey"],("",""))[0 if lang=="ko" else 1],
                           "d":i["desc"][:110]} for i in items], ensure_ascii=False)
        chips = "".join('<button class="chip" data-q="' + html.escape(c) + '">' + html.escape(c) + '</button>'
                        for c in (CHIPS_KO if lang=="ko" else CHIPS_EN))
        if lang == "ko":
            top = ('<div class="topbar"><span class="brand">ai-coding-mines</span>'
                   '<span><a href="' + BASE + '/en/">English</a><a href="' + REPO + '">GitHub</a></span></div>'
                   '<div class="kicker">밟아서 배운 것만</div>'
                   '<h1>에이전트는 완료라고 말했다</h1>'
                   '<p class="lead">AI 코딩 에이전트로 개발하며 실제로 밟은 함정 ' + str(len(items)) + '건. '
                   '절반 이상이 에러 없이 지나가는 <strong>조용한 실패</strong>입니다.</p>'
                   '<div class="ev">'
                   '<div><div class="m">200 SUCCESS</div><div class="s">6주간 아무것도 안 바뀜</div></div>'
                   '<div><div class="m">exit code 0</div><div class="s">크론이 한 번도 안 돎</div></div>'
                   '<div><div class="m">47 registered</div><div class="s">이미지 0장으로</div></div></div>'
                   '<h2>증상으로 찾기</h2>'
                   '<div class="searchbox"><input id="q" placeholder="겪고 있는 증상을 입력하세요"></div>'
                   '<div class="chips">' + chips + '</div>'
                   '<div id="hits"></div>'
                   '<p class="hint">밟는 순간엔 증상밖에 안 보이니까요.</p>'
                   '<h2>분류로 보기</h2><div class="cats">' + cards + '</div>')
            desc = "AI 코딩 에이전트로 개발하며 실제로 밟은 함정 기록. 증상으로 검색하세요."
            title = "에이전트는 완료라고 말했다 — AI 코딩 지뢰 도감"
        else:
            top = ('<div class="topbar"><span class="brand">ai-coding-mines</span>'
                   '<span><a href="' + BASE + '/">한국어</a><a href="' + REPO + '">GitHub</a></span></div>'
                   '<div class="kicker">nothing here was learned by reading</div>'
                   '<h1>The agent said it was done</h1>'
                   '<p class="lead">' + str(len(items)) + ' traps actually stepped on while building with AI coding agents. '
                   'More than half are <strong>silent failures</strong> — nothing throws.</p>'
                   '<div class="ev">'
                   '<div><div class="m">200 SUCCESS</div><div class="s">six weeks, nothing changed</div></div>'
                   '<div><div class="m">exit code 0</div><div class="s">the cron never ran once</div></div>'
                   '<div><div class="m">47 registered</div><div class="s">all with zero images</div></div></div>'
                   '<h2>Search by symptom</h2>'
                   '<div class="searchbox"><input id="q" placeholder="Type what you are seeing"></div>'
                   '<div class="chips">' + chips + '</div>'
                   '<div id="hits"></div>'
                   '<p class="hint">When you are standing on the mine, the symptom is all you can see.</p>'
                   '<h2>Browse by category</h2><div class="cats">' + cards + '</div>')
            desc = "Traps actually stepped on while building with AI coding agents. Search by symptom."
            title = "The agent said it was done — AI coding landmines"
        nores = ("해당 증상은 아직 도감에 없습니다." if lang == "ko" else "No entry matches yet.")
        script = ('<script>var IDX=' + idx + ';'
                  'var q=document.getElementById("q"),h=document.getElementById("hits");'
                  'function run(){var v=q.value.trim().toLowerCase();'
                  'if(v.length<2){h.innerHTML="";return}'
                  'var r=IDX.filter(function(i){return (i.t+" "+i.d+" "+i.c).toLowerCase().indexOf(v)>-1}).slice(0,12);'
                  'h.innerHTML=r.length?r.map(function(i){'
                  'return "<div class=\\"card\\"><a href=\\""+i.u+"\\">"+i.t+"</a><p>"+i.c+" &middot; "+i.d+"</p></div>"'
                  '}).join(""):"<p class=\\"hint\\">' + nores + '</p>"}'
                  'q.addEventListener("input",run);'
                  'var cs=document.querySelectorAll(".chip");'
                  'for(var k=0;k<cs.length;k++){cs[k].addEventListener("click",function(){'
                  'q.value=this.getAttribute("data-q");run();q.focus()})}</script>')
        url = BASE + "/" + prefix
        out_path = os.path.join(OUT, prefix, "index.html") if prefix else os.path.join(OUT, "index.html")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        open(out_path, "w", encoding="utf-8").write(page(title, desc, top + script, url, lang))
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
