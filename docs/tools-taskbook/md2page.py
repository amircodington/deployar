"""Tiny md -> card-page HTML for the two Hamkar docs. Handles only what those docs use."""
import html, re, sys

CSS = r"""
:root{--bg:#111014;--card:#1A181D;--raised:#232027;--line:#2E2A33;--fg:#F3F0EB;--muted:#A09AA8;
--amber:#FFB547;--peach:#F7D9B5;--mint:#7EE0C3;--violet:#8E8AF2;--red:#F26B6B;color-scheme:dark;
--f-ui:"Vazirmatn",system-ui,sans-serif;--f-mono:"JetBrains Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:light){:root:not([data-theme="dark"]){--bg:#F4F2EE;--card:#FFFFFF;--raised:#EEEBE6;--line:#DEDAD3;
--fg:#17151A;--muted:#625C68;--amber:#B86E00;--peach:#8A5A1E;--mint:#127A5C;--violet:#5550C8;--red:#C23B3B;color-scheme:light}}
:root[data-theme="light"]{--bg:#F4F2EE;--card:#FFFFFF;--raised:#EEEBE6;--line:#DEDAD3;
--fg:#17151A;--muted:#625C68;--amber:#B86E00;--peach:#8A5A1E;--mint:#127A5C;--violet:#5550C8;--red:#C23B3B;color-scheme:light}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--f-ui);font-size:15px;line-height:1.7;
padding:32px max(16px,env(safe-area-inset-right,0px)) 64px max(16px,env(safe-area-inset-left,0px));overflow-x:hidden}
.page{max-width:1240px;margin:0 auto;display:grid;gap:20px;grid-template-columns:minmax(0,1fr)}
header.hero{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:clamp(20px,4vw,40px);display:grid;gap:12px}
.eyebrow{display:flex;flex-wrap:wrap;gap:8px;align-items:center;color:var(--muted);font-size:13px}
.eyebrow b{color:var(--peach);font-weight:700}
.pill{border:1px solid var(--line);background:var(--raised);border-radius:999px;padding:2px 10px;font-size:12px}
h1{margin:0;font-size:clamp(30px,5vw,52px);font-weight:800;letter-spacing:-.02em;line-height:1.1}
.lede{color:var(--muted);max-width:75ch;margin:0}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.legend span{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
.legend i{width:10px;height:10px;border-radius:50%;display:inline-block}
nav.toc{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:18px 20px}
nav.toc h2{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin:0 0 8px}
nav.toc ol{margin:0;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:6px}
nav.toc a{display:block;color:var(--fg);text-decoration:none;font-size:13px;padding:4px 10px;border-radius:10px;background:var(--raised)}
nav.toc a:hover{color:var(--peach)}
main{display:grid;gap:20px;min-width:0}
section.card{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:clamp(18px,3vw,32px);min-width:0;scroll-margin-top:16px}
section.card>h2{margin:0 0 12px;font-size:clamp(20px,2.4vw,26px);font-weight:800;letter-spacing:-.01em;display:flex;gap:10px;align-items:baseline}
section.card>h2 .n{color:var(--peach);font-family:var(--f-mono);font-size:.7em;font-weight:500}
h3{font-size:17px;margin:22px 0 8px;font-weight:700}
p{margin:0 0 12px;overflow-wrap:anywhere}
ul,ol.md{margin:0 0 12px;padding-inline-start:22px}
li{margin:4px 0;overflow-wrap:anywhere}
li::marker{color:var(--muted)}
strong{font-weight:700;color:var(--fg)}
code{font-family:var(--f-mono);font-size:.84em;background:var(--raised);border:1px solid var(--line);border-radius:6px;padding:1px 5px;overflow-wrap:anywhere}
.tbl{overflow-x:auto;margin:6px 0 16px;border:1px solid var(--line);border-radius:16px;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:13.5px;min-width:560px}
th,td{text-align:left;vertical-align:top;padding:9px 12px;border-bottom:1px solid var(--line)}
th{background:var(--raised);font-weight:700;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}
tr:last-child td{border-bottom:0}
td code{overflow-wrap:normal;white-space:nowrap}
.diagram{overflow-x:auto;background:var(--raised);border:1px solid var(--line);border-radius:20px;padding:16px;margin:6px 0 16px}
.diagram pre.mermaid{margin:0;min-width:min-content;background:transparent}
pre.code{overflow-x:auto;background:var(--raised);border:1px solid var(--line);border-radius:16px;padding:14px 16px;margin:6px 0 16px;
font-family:var(--f-mono);font-size:12.5px;line-height:1.6;direction:ltr}
pre.code code{background:none;border:0;padding:0;font-size:inherit;overflow-wrap:normal}
.r-read{color:var(--mint);font-weight:700}
.r-sensitive{color:var(--amber);font-weight:700}
.r-human{color:var(--violet);font-weight:700}
footer{color:var(--muted);font-size:12px;text-align:center;padding-top:8px}
@media (min-width:1000px){
 .page{grid-template-columns:250px minmax(0,1fr)}
 header.hero{grid-column:1/-1}
 nav.toc{position:sticky;top:16px;align-self:start;max-height:calc(100vh - 32px);overflow:auto}
 nav.toc ol{display:block}
 nav.toc li{margin:2px 0}
 nav.toc a{background:none;padding:5px 8px}
 nav.toc a:hover{background:var(--raised)}
 footer{grid-column:1/-1}
}
"""

RISK = {"read": "r-read", "sensitive": "r-sensitive", "human_only": "r-human"}


def inline(s):
    out, parts = [], re.split(r"(`[^`]+`)", s)
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append("<code>" + html.escape(p[1:-1].replace("\\|", "|")) + "</code>")
        else:
            t = html.escape(p.replace("\\|", "|"))
            t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
            t = re.sub(r"«[^»]*»", lambda m: "<bdi>" + m.group(0) + "</bdi>", t)
            out.append(t)
    return "".join(out)


def cells(row):
    row = row.strip().strip("|")
    return [c.strip() for c in re.split(r"(?<!\\)\|", row)]


def cell_html(c):
    if c in RISK:
        return f'<span class="{RISK[c]}">{c}</span>'
    return inline(c)


def convert(md):
    lines = md.split("\n")
    title, lede, sections, cur = "", [], [], None
    i = 0
    buf = []  # html chunks of current target

    def target():
        return cur["body"] if cur else lede

    para = []

    def flush():
        if para:
            target().append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("# "):
            title = ln[2:].strip(); i += 1; continue
        if ln.startswith("## "):
            flush()
            m = re.match(r"(\d+)\.\s+(.*)", ln[3:].strip())
            num, name = (m.group(1), m.group(2)) if m else ("", ln[3:].strip())
            cur = {"num": num, "name": name, "id": f"s{len(sections)+1}", "body": []}
            sections.append(cur); i += 1; continue
        if ln.startswith("### "):
            flush(); target().append(f"<h3>{inline(ln[4:].strip())}</h3>"); i += 1; continue
        if ln.startswith("```"):
            flush(); lang = ln[3:].strip(); j = i + 1; code = []
            while not lines[j].startswith("```"):
                code.append(lines[j]); j += 1
            body = html.escape("\n".join(code))
            if lang == "mermaid":
                target().append(f'<div class="diagram"><pre class="mermaid">{body}</pre></div>')
            else:
                target().append(f'<pre class="code"><code>{body}</code></pre>')
            i = j + 1; continue
        if ln.startswith("|"):
            flush(); rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i]); i += 1
            head, body = cells(rows[0]), [cells(r) for r in rows[2:]]
            t = "<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
            t += "".join("<tr>" + "".join(f"<td>{cell_html(c)}</td>" for c in r) + "</tr>" for r in body)
            target().append(f'<div class="tbl"><table>{t}</tbody></table></div>'); continue
        m = re.match(r"^(\s*)(- |\d+\. )(.*)", ln)
        if m:
            flush(); ordered = m.group(2)[0].isdigit(); items = []
            while i < len(lines):
                m2 = re.match(r"^(- |\d+\. )(.*)", lines[i])
                if m2:
                    items.append(m2.group(2))
                elif lines[i].startswith("  ") and lines[i].strip() and items:
                    items[-1] += " " + lines[i].strip()
                else:
                    break
                i += 1
            tag = 'ol class="md"' if ordered else "ul"
            target().append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag.split()[0]}>")
            continue
        if not ln.strip():
            flush(); i += 1; continue
        para.append(ln.strip()); i += 1
    flush()
    return title, lede, sections


def page(md_path, out_path, page_title, sub):
    title, lede, sections = convert(open(md_path, encoding="utf-8").read())
    assert sections and all("```" not in "".join(s["body"]) for s in sections), "unconverted fence"
    toc = "".join(f'<li><a href="#{s["id"]}">{s["num"] + ". " if s["num"] else ""}{inline(s["name"])}</a></li>' for s in sections)
    secs = "".join(
        f'<section class="card" id="{s["id"]}"><h2>{f"<span class=n>{s["num"]}</span>" if s["num"] else ""}{inline(s["name"])}</h2>{"".join(s["body"])}</section>'
        for s in sections)
    out = f"""<title>همکار فنی · {page_title}</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700;800&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
<div class="page" lang="en" dir="ltr">
<header class="hero">
  <div class="eyebrow"><b lang="fa" dir="rtl">همکار فنی</b><span>Hamkar</span><span class="pill">Starcoach hackathon · Liara challenge</span><span class="pill">{sub}</span></div>
  <h1>{page_title}</h1>
  {"".join(lede).replace("<p>", '<p class="lede">')}
  <div class="legend"><span><i style="background:var(--mint)"></i>read / healthy / automatic</span><span><i style="background:var(--amber)"></i>sensitive / needs approval</span><span><i style="background:var(--violet)"></i>human_only / info</span><span><i style="background:var(--red)"></i>error</span></div>
</header>
<nav class="toc" aria-label="Contents"><h2>Contents</h2><ol>{toc}</ol></nav>
<main>{secs}</main>
<footer>Source: docs/{md_path.split('/')[-1]} · English docs, Persian product strings · endpoints marked "to verify" are confirmed in task T-01</footer>
</div>
"""
    open(out_path, "w", encoding="utf-8").write(out)
    print(out_path, len(out), "bytes,", len(sections), "sections")


if __name__ == "__main__":
    d = sys.argv[1]
    page(f"{d}/SYSTEM-DESIGN.md", f"{d}/artifacts/system-design.html", "System Design", "what and why")
    page(f"{d}/ARCHITECTURE.md", f"{d}/artifacts/architecture.html", "Software Architecture", "how")
