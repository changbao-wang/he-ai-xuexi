"""用已核验的 JSON 日报生成静态网页；仅依赖 Python 标准库。"""
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- DAILY:START -->", "<!-- DAILY:END -->"


def esc(value):
    return html.escape(str(value), quote=True)


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"日期必须为 YYYY-MM-DD：{value!r}")
    return date.fromisoformat(value)


def validate(report, filename):
    edition = valid_date(report["date"])
    if filename.stem != report["date"]:
        raise ValueError("文件名必须与日报日期一致")
    for key in ("title", "summary", "coverage"):
        if not isinstance(report.get(key), str) or not report[key].strip():
            raise ValueError(f"日报缺少 {key}")
    if not report.get("items"):
        raise ValueError("已发布日报至少需要一条已核验消息")
    for item in report["items"]:
        if item.get("verified") is not True or not item.get("sources"):
            raise ValueError("消息必须完成核验并附原始来源")
        if valid_date(item["event_date"]) > edition:
            raise ValueError("消息日期不能晚于日报日期")
        for key in ("title", "summary", "interpretation", "question"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"消息缺少 {key}")
        for source in item["sources"]:
            url = urlparse(source["url"])
            if url.scheme != "https" or not url.netloc or url.username or url.password:
                raise ValueError("来源必须为不含凭据的 HTTPS 链接")
            if valid_date(source["published_date"]) > edition:
                raise ValueError("来源发布时间不能晚于日报日期")
            if not source.get("name"):
                raise ValueError("来源需要名称")


EXTRA_CSS = """
.article-head{padding:70px 0 35px;border-top:0}.article-head h1{font-size:clamp(30px,5vw,48px);max-width:900px;line-height:1.4;text-wrap:balance}.article-head .intro{font-size:16px}.editor-note{padding:18px 22px;border-left:2px solid var(--accent);background:var(--panel);color:var(--muted);font-size:14px;margin:22px 0}.news-item{max-width:800px;padding:35px 0}.news-item h2{font-size:24px;line-height:1.6;margin-bottom:18px}.news-item p{color:#c1c9bd;line-height:1.9}.news-item h3{font-size:14px;color:var(--accent);margin:26px 0 8px}.news-date,.source-list{font-size:13px;color:var(--muted)}.source-list a{color:var(--accent);overflow-wrap:anywhere;display:inline-block;padding:10px 0}.question{background:var(--panel-soft);padding:16px 20px;border-radius:5px}.archive-card{display:block;text-decoration:none;padding:28px 0;border-bottom:1px solid var(--line)}.archive-card h2{font-size:23px;margin:8px 0 12px}.archive-card p{color:var(--muted);font-size:14px;max-width:760px}.archive-card:hover h2{color:var(--accent)}.topics{color:var(--accent);font:12px var(--mono)}.reading-nav{display:flex;justify-content:space-between;gap:20px;padding:26px 0}.reading-nav a{padding:10px 0;color:var(--accent);font-size:14px}.suggestions{padding-left:24px;line-height:2}.daily-teaser{padding:26px;border:1px solid var(--line);background:var(--panel);border-radius:6px}.daily-teaser h3{font-size:22px;margin:10px 0}.daily-teaser p{color:var(--muted);font-size:14px}.daily-teaser .meta{font-size:12px;color:var(--accent)}
@media(max-width:700px){nav{gap:12px}.topbar{flex-wrap:wrap;gap:4px;padding:10px 0}.brand{font-size:14px}.article-head{padding-top:44px}.news-item h2{font-size:21px}.daily-teaser{padding:20px}}
"""


def page(title, description, body, prefix, base_css):
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#101311"><meta name="description" content="{esc(description)}"><title>{esc(title)} · 常宝 · 和AI一起学习</title><style>{base_css}\n{EXTRA_CSS}</style></head><body><div class="shell">
<header class="topbar"><a class="brand" href="{prefix}index.html"><span>和AI一起学习</span></a><nav aria-label="主导航"><a href="{prefix}daily/" aria-current="page">日报</a><a href="{prefix}index.html#learning">学习中</a><a href="{prefix}index.html#notes">笔记</a><a href="{prefix}index.html#projects">实践</a></nav></header>
<main>{body}</main><footer><span>持续学习，把理解变成实践。</span><a href="{prefix}index.html">返回首页</a></footer></div></body></html>\n'''


def article(report, reports, base_css):
    day = report["date"]
    blocks = []
    for n, item in enumerate(report["items"], 1):
        sources = "".join(f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">{esc(s["name"])} ↗</a>（发布于 {esc(s["published_date"])}）</li>' for s in item["sources"])
        blocks.append(f'''<section class="news-item"><p class="kicker">{n:02d} / NEWS</p><h2>{esc(item['title'])}</h2><p class="news-date">消息 / 资料日期：{esc(item['event_date'])}</p><h3>发生了什么</h3><p>{esc(item['summary'])}</p><h3>为什么值得研究 · AI 整理</h3><p>{esc(item['interpretation'])}</p><h3>继续学习的问题</h3><p class="question">{esc(item['question'])}</p><h3>原文与来源</h3><ul class="source-list">{sources}</ul></section>''')
    suggestions = "".join(f"<li>{esc(s)}</li>" for s in report.get("learning_suggestions", []))
    idx = reports.index(report)
    older = f'<a href="../{reports[idx+1]["date"]}/">← 上一期</a>' if idx + 1 < len(reports) else '<span></span>'
    newer = f'<a href="../{reports[idx-1]["date"]}/">下一期 →</a>' if idx > 0 else '<a href="../">查看全部日报 →</a>'
    body = f'''<div class="article-head"><p class="eyebrow">AI DAILY / <time datetime="{day}">{day}</time></p><h1>{esc(report['title'])}</h1><p class="intro">{esc(report['summary'])}</p><p class="topics">{' / '.join(esc(t) for t in report.get('topics', []))}</p><p class="editor-note">{esc(report['coverage'])}<br>由 ChatGPT“每日重点简报”筛选整理，关键事实已核对来源。解读和练习为 AI 整理的学习建议，供继续探索。</p></div>{''.join(blocks)}<section class="news-item"><p class="kicker">LEARN / NEXT</p><h2>可以动手做的一个小练习</h2><ol class="suggestions">{suggestions}</ol><p class="news-date">这些是建议练习，尚未标记为个人已完成成果。</p></section><nav class="reading-nav" aria-label="日报翻页">{older}{newer}</nav>'''
    return page(f"AI 日报 · {day}", report["summary"], body, "../../", base_css)


def main():
    home = (ROOT / "index.html").read_text(encoding="utf-8-sig")
    home = "\n".join(line.rstrip() for line in home.splitlines()) + "\n"
    style = re.search(r"<style>(.*?)</style>", home, re.S)
    if not style or home.count(START) != 1 or home.count(END) != 1:
        raise ValueError("首页缺少唯一的样式区或日报更新标记")
    base_css = style.group(1)
    reports = []
    for filename in sorted((ROOT / "content/daily").glob("*.json")):
        report = json.loads(filename.read_text(encoding="utf-8-sig"))
        if report.get("status") == "draft":
            continue
        if report.get("status") != "published":
            raise ValueError(f"无效的日报状态：{filename.name}")
        validate(report, filename)
        reports.append(report)
    reports.sort(key=lambda r: r["date"], reverse=True)
    if not reports:
        raise ValueError("没有可发布的日报")
    outputs = {}
    for report in reports:
        outputs[ROOT / "daily" / report["date"] / "index.html"] = article(report, reports, base_css)
    cards = "".join(f'''<a class="archive-card" href="{r['date']}/"><span class="meta">{r['date']} · {len(r['items'])} 个主题</span><h2>{esc(r['title'])} →</h2><p>{esc(r['summary'])}</p><span class="topics">{' / '.join(esc(t) for t in r.get('topics', []))}</span></a>''' for r in reports)
    body = f'''<div class="article-head"><p class="eyebrow">DAILY / ARCHIVE</p><h1>AI 日报</h1><p class="intro">从每天读到的信息出发，留下来源、理解和下一步想弄懂的问题。</p><p class="news-date">已归档 {len(reports)} 期 · 最新整理 {reports[0]['date']}</p></div><div>{cards}</div>'''
    outputs[ROOT / "daily/index.html"] = page("AI 日报目录", "和AI一起学习：按日期回看 AI 日报、原始来源与学习问题。", body, "../", base_css)
    latest = reports[0]
    teaser = f'''{START}
      <section id="daily"><div class="section-head"><div><p class="kicker">DAILY / 最近整理</p><h2>每天读一点，再想深一点</h2></div><a class="button" href="daily/">全部日报 →</a></div><article class="daily-teaser"><p class="meta">{latest['date']} · AI 日报 · {len(latest['items'])} 个主题</p><h3>{esc(latest['title'])}</h3><p>{esc(latest['summary'])}</p><a class="button primary" href="daily/{latest['date']}/">阅读本期 →</a></article></section>
      {END}'''
    # 首页新增的组件使用相同配色；保持构建重复运行时输出不变。
    marker = "/* DAILY COMPONENTS */"
    extra_home_css = f"\n    {marker}\n    .daily-teaser{{padding:26px;border:1px solid var(--line);background:var(--panel);border-radius:6px}}.daily-teaser h3{{font-size:22px;margin:10px 0}}.daily-teaser p{{color:var(--muted);font-size:14px}}.daily-teaser .meta{{font-size:12px;color:var(--accent)}}@media(max-width:700px){{nav{{gap:12px}}.topbar{{flex-wrap:wrap;gap:4px;padding:10px 0}}.brand{{font-size:14px}}}}\n"
    if marker not in home:
        home = home.replace("</style>", extra_home_css + "  </style>", 1)
        # 文章同样继承首页最终样式，使首次和后续构建保持一致。
        return rebuild_after_style(home)
    home = home[:home.index(START)] + teaser + home[home.index(END) + len(END):]
    outputs[ROOT / "index.html"] = home
    for filename, content in outputs.items():
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text(content, encoding="utf-8", newline="\n")
    print(f"已生成 {len(reports)} 期日报、日报目录和首页入口。")


def rebuild_after_style(home):
    (ROOT / "index.html").write_text(home, encoding="utf-8", newline="\n")
    main()


if __name__ == "__main__":
    main()
