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
:root{
--bg:#F6F4F1;--fg:#1A1A18;--fg2:#4F4E4A;--dim:#6B6A66;--faint:#9A9894;--hair:rgba(26,26,24,.08);
--glass:rgba(255,255,255,.82);--glass-strong:rgba(255,255,255,.70);--edge:rgba(255,255,255,.9);
--accent:#DC3F1B;--accent2:#F0653C;--accent3:#FFB03C;--ink:#B33418;--soft:#FDF1ED;
--sh-sm:0 2px 6px rgba(26,26,24,.05);--sh-md:0 14px 32px -26px rgba(26,26,24,.75);
--sh-lg:0 2px 6px rgba(26,26,24,.05),0 24px 60px -30px rgba(26,26,24,.38);
--mesh:radial-gradient(560px 380px at 8% -6%,rgba(232,85,47,.20),transparent 62%),radial-gradient(520px 400px at 98% 4%,rgba(255,176,60,.18),transparent 60%),radial-gradient(600px 460px at 72% 108%,rgba(94,132,255,.14),transparent 62%);
--code-bg:rgba(255,255,255,.72);--pre-bg:#FBFAF8;--th-bg:rgba(255,255,255,.6)}
@media (prefers-color-scheme: dark){:root{
--bg:#111114;--fg:#ECEBE8;--fg2:#B8B7B2;--dim:#94938E;--faint:#6E6D69;--hair:rgba(255,255,255,.09);
--glass:rgba(30,30,35,.72);--glass-strong:rgba(28,28,33,.68);--edge:rgba(255,255,255,.09);
--accent:#FF6B3D;--accent2:#FF8A5C;--accent3:#FFC062;--ink:#FF9068;--soft:rgba(255,107,61,.10);
--sh-sm:0 2px 6px rgba(0,0,0,.4);--sh-md:0 14px 32px -24px rgba(0,0,0,.9);
--sh-lg:0 2px 6px rgba(0,0,0,.4),0 24px 60px -28px rgba(0,0,0,.95);
--mesh:radial-gradient(560px 380px at 8% -6%,rgba(255,107,61,.16),transparent 62%),radial-gradient(520px 400px at 98% 4%,rgba(255,176,60,.12),transparent 60%),radial-gradient(600px 460px at 72% 108%,rgba(94,132,255,.14),transparent 62%);
--code-bg:rgba(255,255,255,.07);--pre-bg:#17171B;--th-bg:rgba(255,255,255,.05)}}
body{background:var(--bg);color:var(--fg);font-family:'Inter','Helvetica Neue',-apple-system,BlinkMacSystemFont,'Pretendard','Noto Sans KR',sans-serif;line-height:1.72;margin:0;font-size:16px;-webkit-font-smoothing:antialiased;position:relative;min-height:100vh}
body::before{content:"";position:fixed;inset:0;background:var(--mesh);pointer-events:none;z-index:0}
.wrap{max-width:880px;margin:0 auto;padding:20px 22px 96px;position:relative;z-index:1}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
h1{font-size:44px;font-weight:600;line-height:1.11;margin:0 0 18px;letter-spacing:-.038em}
h2{font-size:20px;margin:44px 0 14px;letter-spacing:-.015em;font-weight:600}
h3{font-size:16px;margin:26px 0 8px;color:var(--fg);font-weight:600}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:16px 4px;margin-bottom:12px}
.topbar .brand{font-size:12.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--fg)}
.topbar a{font-size:12px;color:var(--dim);background:var(--glass);backdrop-filter:blur(12px);border:1px solid var(--edge);border-radius:999px;padding:6px 14px;margin-left:7px;box-shadow:var(--sh-sm)}
.topbar a:hover{text-decoration:none;color:var(--fg)}
.hero{position:relative;background:var(--glass-strong);backdrop-filter:blur(24px);border:1px solid var(--edge);border-radius:26px;padding:36px 32px;margin-bottom:12px;box-shadow:var(--sh-lg);overflow:hidden}
.hero .orb{position:absolute;top:-90px;right:-60px;width:280px;height:280px;border-radius:50%;background:conic-gradient(from 200deg,rgba(232,85,47,.22),rgba(255,176,60,.20),rgba(94,132,255,.16),rgba(232,85,47,.22));filter:blur(38px)}
.hero .in{position:relative}
.pill{display:inline-flex;align-items:center;gap:9px;background:var(--glass);border:1px solid rgba(232,85,47,.22);border-radius:999px;padding:6px 14px 6px 10px;margin-bottom:22px}
.pill .dot{width:10px;height:10px;border-radius:50%;background:linear-gradient(145deg,var(--accent2),var(--accent));box-shadow:0 0 0 4px rgba(232,85,47,.14),0 0 14px rgba(232,85,47,.5)}
.pill span{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--ink);font-weight:500}
.grad{background:linear-gradient(120deg,var(--accent2),var(--accent) 55%,var(--accent3));-webkit-background-clip:text;background-clip:text;color:transparent}
.lead{font-size:15.5px;line-height:1.72;color:var(--fg2);margin:0;max-width:46ch}
.ev{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:0 0 12px}
.ev>div{position:relative;background:linear-gradient(150deg,var(--glass),var(--soft));backdrop-filter:blur(14px);border:1px solid var(--edge);border-radius:18px;padding:16px 18px 16px 21px;box-shadow:0 10px 26px -22px rgba(179,52,24,.8);overflow:hidden}
.ev>div::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:linear-gradient(180deg,var(--accent2),var(--accent))}
.ev .m{font-family:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;color:var(--ink);margin-bottom:6px;font-weight:500}
.ev .s{font-size:13px;color:var(--fg2);line-height:1.5}
.panel{background:var(--glass-strong);backdrop-filter:blur(20px);border:1px solid var(--edge);border-radius:24px;padding:26px;margin-bottom:12px;box-shadow:var(--sh-lg)}
.label{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);margin-bottom:14px;font-weight:500}
#q{width:100%;background:var(--glass);border:1px solid rgba(232,85,47,.22);border-radius:999px;color:var(--fg);padding:14px 20px;font-size:15px;font-family:inherit;box-shadow:0 0 0 4px rgba(232,85,47,.07)}
#q:focus{outline:none;border-color:var(--accent)}
#q::placeholder{color:var(--faint)}
.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}
.chip{font-size:12.5px;color:var(--fg2);background:var(--glass);border:1px solid var(--hair);border-radius:999px;padding:7px 15px;cursor:pointer;font-family:inherit}
.chip:hover{color:#fff;background:linear-gradient(140deg,var(--accent2),var(--accent));border-color:transparent;box-shadow:0 6px 16px -10px rgba(220,63,27,.9)}
.hint{color:var(--faint);font-size:12.5px;margin:12px 0 0}
.cats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin:20px 0}
.cat{position:relative;background:var(--glass);backdrop-filter:blur(14px);border:1px solid var(--edge);border-radius:20px;padding:18px 20px;box-shadow:var(--sh-md);overflow:hidden;transition:transform .15s}
.cat:hover{transform:translateY(-2px)}
.cat::before{content:"";position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--c,#5E84FF),transparent)}
.cat .hd{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px}
.cat .no{font-size:11px;letter-spacing:.1em;color:var(--faint)}
.cat .n{font-size:20px;font-weight:600;background:linear-gradient(140deg,var(--c,#5E84FF),var(--c2,#3B5BDB));-webkit-background-clip:text;background-clip:text;color:transparent}
.cat a{font-size:14.5px;font-weight:600;display:block;margin-bottom:5px;color:var(--fg)}
.cat p{margin:0;color:var(--dim);font-size:12.5px;line-height:1.55}
.cat.hot{background:linear-gradient(150deg,var(--accent2),var(--accent) 60%,#B32B10);border-color:transparent;box-shadow:0 3px 8px rgba(220,63,27,.25),0 22px 44px -28px rgba(220,63,27,.95)}
.cat.hot::before{display:none}
.cat.hot .glow{position:absolute;top:-40px;right:-30px;width:130px;height:130px;border-radius:50%;background:radial-gradient(circle at 40% 40%,rgba(255,255,255,.32),transparent 66%)}
.cat.hot .no{color:#F9CDBF;position:relative}.cat.hot .n{color:#fff;background:none;-webkit-text-fill-color:#fff;position:relative}
.cat.hot a{color:#fff;position:relative}.cat.hot p{color:#FBDFD6;position:relative}
.cards{display:grid;gap:10px;margin:18px 0}
.card{background:var(--glass);backdrop-filter:blur(14px);border:1px solid var(--edge);border-radius:16px;padding:15px 18px;box-shadow:var(--sh-md)}
.card a{font-weight:600;font-size:15px;color:var(--fg)}
.card p{margin:5px 0 0;color:var(--dim);font-size:13px;line-height:1.55}
.nav{font-size:13px;color:var(--dim);margin-bottom:20px}
.meta{color:var(--faint);font-size:13px;margin-bottom:22px}
.tag{display:inline-block;background:var(--soft);color:var(--ink);font-size:11.5px;padding:4px 11px;border-radius:999px;margin-right:6px;border:1px solid rgba(232,85,47,.18)}
.article{background:var(--glass-strong);backdrop-filter:blur(20px);border:1px solid var(--edge);border-radius:24px;padding:32px 30px;box-shadow:var(--sh-lg)}
code{background:var(--code-bg);padding:2px 7px;border-radius:6px;font-family:'IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13.5px;border:1px solid var(--hair)}
pre{background:var(--pre-bg);border:1px solid var(--hair);border-radius:14px;padding:16px;overflow-x:auto}
pre code{background:none;padding:0;font-size:13px;line-height:1.65;border:0}
blockquote{border-left:3px solid var(--accent);margin:20px 0;padding:2px 0 2px 18px;color:var(--fg2)}
table{border-collapse:collapse;width:100%;margin:20px 0;font-size:14.5px}
th,td{border:1px solid var(--hair);padding:10px 12px;text-align:left;vertical-align:top}
th{background:var(--th-bg)}
hr{border:0;border-top:1px solid var(--hair);margin:32px 0}
ul,ol{padding-left:22px}li{margin:7px 0}
footer{margin-top:56px;padding:22px 4px 0;border-top:1px solid var(--hair);color:var(--faint);font-size:13px;line-height:1.8}
@media(max-width:600px){.wrap{padding:14px 16px 72px}h1{font-size:31px}body{font-size:15.5px}.hero,.article{padding:26px 22px;border-radius:22px}.panel{padding:22px 20px}}"""

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
            body = (f'<div class="topbar"><span class="brand">ai-coding-mines</span>'
                    f'<span><a href="{BASE}/{prefix if prefix else ""}">{"목차" if lang=="ko" else "Index"}</a>'
                    f'<a href="{REPO}">GitHub</a></span></div>'
                    f'<div class="hero"><span class="orb"></span><div class="in">'
                    f'<h1 style="font-size:34px">{html.escape(ftitle)}</h1>'
                    f'<div class="meta">{len(items)} {"개 항목" if lang=="ko" else "entries"}</div>'
                    f'{md_to_html(intro)}</div></div>'
                    f'<div class="cards">{cards}</div>')
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
                body = (f'<div class="topbar"><span class="brand">ai-coding-mines</span>'
                        f'<span><a href="{BASE}/{prefix if prefix else ""}">{"목차" if lang=="ko" else "Index"}</a>'
                        f'<a href="{REPO}">GitHub</a></span></div>'
                        f'<div class="article">'
                        f'<div class="nav"><a href="{cat_url}">{html.escape(cat)}</a></div>'
                        f'<h1 style="font-size:31px">{html.escape(it["title"])}</h1>'
                        f'<div class="meta"><span class="tag">{html.escape(cat)}</span></div>'
                        f'{md_to_html(it["body"])}'
                        f'<hr><div class="nav">{" · ".join(prev_next)}</div></div>')
                open(os.path.join(idir, "index.html"), "w", encoding="utf-8").write(
                    page(f'{it["title"]} — ai-coding-mines', it["desc"] or it["title"], body, url, lang,
                         f'<script type="application/ld+json">{ld}</script>'))
                urls.append(url)
                all_items.append({"lang":lang,"cat":cat,"catkey":key,"title":it["title"],"url":url,"desc":it["desc"]})
    # 루트 인덱스 (ko / en)
    CATMETA = {
        "01-windows-powershell": ("#5E84FF", "#3B5BDB", "셸이 조용히 값을 바꾸는 자리",
                                  "Where the shell quietly changes your values"),
        "02-python-db":          ("#22A06B", "#137A4E", "데이터는 맞는데 결과가 틀릴 때",
                                  "When the data is right but the result isn't"),
        "03-git-automation":     ("#A855F7", "#7E22CE", "무인으로 도는 것이 멈추는 법",
                                  "How unattended things stop without telling you"),
        "04-claude-code-agent":  ("#0EA5E9", "#0369A1", "완료라고 말할 때 실제로 일어난 일",
                                  "What actually happened when it said done"),
        "05-deploy-infra":       ("#FFB03C", "#D97706", "크론과 외부 서비스의 보이지 않는 벽",
                                  "Invisible walls in crons and external services"),
        "06-write-api":          ("#F0653C", "#DC3F1B", "성공 응답이 거짓말하는 방식",
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
        for n_, key in enumerate(sorted(bycat), 1):
            its = bycat[key]
            name = CATS.get(key, (key,key))[0 if lang=="ko" else 1]
            c1, c2, dko, den = CATMETA.get(key, ("#5E84FF","#3B5BDB","",""))
            d = dko if lang=="ko" else den
            hot = key == "06-write-api"
            cards += ('<div class="cat' + (' hot' if hot else '') + '" style="--c:' + c1 + ';--c2:' + c2 + '">'
                      + ('<span class="glow"></span>' if hot else '')
                      + '<div class="hd"><span class="no">' + ("0"+str(n_) if n_ < 10 else str(n_))
                      + '</span><span class="n">' + str(len(its)) + '</span></div>'
                      + '<a href="' + BASE + '/' + prefix + key + '/">' + html.escape(name) + '</a>'
                      + '<p>' + html.escape(d) + '</p></div>')
        idx = json.dumps([{"t":i["title"],"u":i["url"],
                           "c":CATS.get(i["catkey"],("",""))[0 if lang=="ko" else 1],
                           "d":i["desc"][:110]} for i in items], ensure_ascii=False)
        chips = "".join('<button class="chip" data-q="' + html.escape(c) + '">' + html.escape(c) + '</button>'
                        for c in (CHIPS_KO if lang=="ko" else CHIPS_EN))
        if lang == "ko":
            top = ('<div class="topbar"><span class="brand">ai-coding-mines</span>'
                   '<span><a href="' + BASE + '/en/">EN</a><a href="' + REPO + '">GitHub</a></span></div>'
                   '<div class="hero"><span class="orb"></span><div class="in">'
                   '<div class="pill"><span class="dot"></span><span>Field guide &middot; ' + str(len(items)) + '</span></div>'
                   '<h1>에이전트는<br>완료라고 <span class="grad">말했다</span></h1>'
                   '<p class="lead">AI 코딩 에이전트로 개발하며 실제로 밟은 함정 ' + str(len(items)) + '건. '
                   '절반 이상은 에러를 내지 않습니다. 성공했다고 말하고, 아무 일도 일어나지 않습니다.</p>'
                   '</div></div>'
                   '<div class="ev">'
                   '<div><div class="m">200 SUCCESS</div><div class="s">6주 동안 아무것도 바뀌지 않음</div></div>'
                   '<div><div class="m">exit code 0</div><div class="s">크론이 한 번도 실행되지 않음</div></div>'
                   '<div><div class="m">47 registered</div><div class="s">전부 이미지 0장으로</div></div></div>'
                   '<div class="panel"><div class="label">증상으로 찾기</div>'
                   '<input id="q" placeholder="겪고 있는 증상을 입력하세요">'
                   '<div class="chips">' + chips + '</div>'
                   '<div id="hits"></div>'
                   '<p class="hint">밟는 순간엔 증상밖에 안 보이니까요.</p></div>'
                   '<h2>분류로 보기</h2><div class="cats">' + cards + '</div>')
            desc = "AI 코딩 에이전트로 개발하며 실제로 밟은 함정 기록. 증상으로 검색하세요."
            title = "에이전트는 완료라고 말했다 — AI 코딩 지뢰 도감"
        else:
            top = ('<div class="topbar"><span class="brand">ai-coding-mines</span>'
                   '<span><a href="' + BASE + '/">KO</a><a href="' + REPO + '">GitHub</a></span></div>'
                   '<div class="hero"><span class="orb"></span><div class="in">'
                   '<div class="pill"><span class="dot"></span><span>Field guide &middot; ' + str(len(items)) + '</span></div>'
                   '<h1>The agent said<br>it was <span class="grad">done</span></h1>'
                   '<p class="lead">' + str(len(items)) + ' traps actually stepped on while building with AI coding agents. '
                   'More than half never throw. They report success, and nothing happened.</p>'
                   '</div></div>'
                   '<div class="ev">'
                   '<div><div class="m">200 SUCCESS</div><div class="s">six weeks, nothing changed</div></div>'
                   '<div><div class="m">exit code 0</div><div class="s">the cron never ran once</div></div>'
                   '<div><div class="m">47 registered</div><div class="s">all with zero images</div></div></div>'
                   '<div class="panel"><div class="label">Search by symptom</div>'
                   '<input id="q" placeholder="Type what you are seeing">'
                   '<div class="chips">' + chips + '</div>'
                   '<div id="hits"></div>'
                   '<p class="hint">When you are standing on the mine, the symptom is all you can see.</p></div>'
                   '<h2>Browse by category</h2><div class="cats">' + cards + '</div>')
            desc = "Traps actually stepped on while building with AI coding agents. Search by symptom."
            title = "The agent said it was done — AI coding landmines"
        nores = ("해당 증상은 아직 도감에 없습니다." if lang == "ko" else "No entry matches yet.")
        script = ('<script>var IDX=' + idx + ';'
                  'var q=document.getElementById("q"),h=document.getElementById("hits");'
                  'function run(){var v=q.value.trim().toLowerCase();'
                  'if(v.length<2){h.innerHTML="";return}'
                  'var r=IDX.filter(function(i){return (i.t+" "+i.d+" "+i.c).toLowerCase().indexOf(v)>-1}).slice(0,12);'
                  'h.innerHTML=r.length?"<div class=\\"cards\\">"+r.map(function(i){'
                  'return "<div class=\\"card\\"><a href=\\""+i.u+"\\">"+i.t+"</a><p>"+i.c+" &middot; "+i.d+"</p></div>"'
                  '}).join("")+"</div>":"<p class=\\"hint\\">' + nores + '</p>"}'
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
