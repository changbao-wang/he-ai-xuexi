"""将核验后的日报生成为静态阅读站；只依赖 Python 标准库。"""
import html
import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- DAILY:START -->", "<!-- DAILY:END -->"
ASSET_VERSION = "4"


def esc(value):
    return html.escape(str(value), quote=True)


def title_html(value):
    return re.sub(r"\bAI (?:办公|应用|视频|短剧|漫剧|教育|工具|内容|工作流)",
                  lambda match: f'<span class="title-phrase">{match.group()}</span>', esc(value))


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
    topics = report.get("topics", [])
    if not isinstance(topics, list) or not all(isinstance(t, str) and t.strip() for t in topics):
        raise ValueError("主题必须为非空文字组成的列表")
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


def tags(report):
    return '<div class="tag-list">' + "".join(f'<span class="tag">{esc(t)}</span>' for t in report.get("topics", [])) + "</div>"


def searchable(report):
    fields = [report["date"], report["date"].replace("-", "."), report["title"], report["summary"], report["coverage"], *report.get("topics", []), *report.get("learning_suggestions", [])]
    for item in report["items"]:
        fields.extend(item[k] for k in ("title", "summary", "interpretation", "question", "event_date"))
        for source in item["sources"]:
            fields.extend((source["name"], source["published_date"]))
    return " ".join(fields)


def reading_minutes(report):
    return max(1, math.ceil(len(searchable(report)) / 350))


def bookmark(day):
    return f'''<button class="bookmark-button js-only" type="button" data-bookmark="{day}" aria-pressed="false" aria-label="收藏 {day} 日报"><svg width="16" height="18" viewBox="0 0 16 18" fill="none" aria-hidden="true"><path d="M3 2h10v14l-5-3-5 3V2Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg><span data-bookmark-label>收藏</span></button>'''


def page(title, description, body, prefix, reading=False):
    progress = '<div class="reading-progress js-only" data-reading-progress aria-hidden="true"></div>' if reading else ""
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f7f6f2"><meta name="description" content="{esc(description)}">
<title>{esc(title)} · 常宝 · 和AI一起学习</title>
<link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{prefix}assets/site.css?v={ASSET_VERSION}">
<link rel="stylesheet" href="{prefix}assets/refinement.css?v=1">
<script src="{prefix}assets/site.js?v={ASSET_VERSION}" defer></script>
</head>
<body id="top">{progress}
<a class="skip-link" href="#main-content">跳到正文</a>
<header class="site-header"><div class="shell header-inner">
<a class="brand" href="{prefix}index.html"><span class="brand-mark" aria-hidden="true">和</span><span>和AI一起学习</span></a>
<button class="menu-toggle js-only" type="button" data-menu-toggle aria-controls="main-nav" aria-expanded="false" aria-label="展开导航">菜单 <span aria-hidden="true">☰</span></button>
<nav class="main-nav" id="main-nav" aria-label="主导航"><a href="{prefix}index.html">首页</a><a href="{prefix}daily/" aria-current="page">AI 日报</a><a href="{prefix}index.html#projects">实践手记</a><a href="{prefix}index.html#learning">学习方向</a><a href="{prefix}about/">关于常宝</a></nav>
</div></header>
<main class="shell" id="main-content">{body}</main>
<footer class="site-footer"><div class="shell footer-inner"><a class="footer-brand" href="{prefix}index.html">和AI一起学习<span> / 常宝的学习手记</span></a><span>慢慢理解，持续实践。</span><a class="back-top" href="#top">回到顶部 ↑</a></div></footer>
</body></html>
'''


def article(report, reports):
    day = report["date"]
    source_note = "" if "ChatGPT" in report["coverage"] else "由 ChatGPT“每日重点简报”筛选整理。"
    blocks, toc = [], []
    for n, item in enumerate(report["items"], 1):
        anchor = f"news-{n}"
        sources = "".join(f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">{esc(s["name"])} <span aria-hidden="true">↗</span></a><span>发布于 {esc(s["published_date"])}</span></li>' for s in item["sources"])
        toc.append(f'<li><a href="#{anchor}"><span>{n:02d}</span>{esc(item["title"])}</a></li>')
        blocks.append(f'''<section class="news-item" id="{anchor}">
<p class="eyebrow">观察 {n:02d}</p><h2>{esc(item["title"])}</h2>
<p class="news-date">消息 / 资料日期：<time datetime="{esc(item["event_date"])}">{esc(item["event_date"])}</time></p>
<h3>发生了什么</h3><p>{esc(item["summary"])}</p>
<h3>为什么值得研究 <span class="ai-label">AI 整理</span></h3><p>{esc(item["interpretation"])}</p>
<div class="question"><span class="eyebrow">留一个问题</span><p>{esc(item["question"])}</p></div>
<details class="source-list"><summary>核验来源 · {len(item["sources"])} 篇原文 <span aria-hidden="true">↗</span></summary><ul>{sources}</ul></details>
</section>''')
    suggestions = "".join(f"<li>{esc(s)}</li>" for s in report.get("learning_suggestions", []))
    idx = reports.index(report)
    older = f'<a href="../{reports[idx+1]["date"]}/"><span>← 上一期</span><strong>{esc(reports[idx+1]["title"])}</strong></a>' if idx + 1 < len(reports) else '<a href="../"><span>← 回到目录</span><strong>翻阅全部学习日报</strong></a>'
    newer = f'<a href="../{reports[idx-1]["date"]}/"><span>下一期 →</span><strong>{esc(reports[idx-1]["title"])}</strong></a>' if idx > 0 else '<a href="../"><span>继续阅读 →</span><strong>浏览日报归档</strong></a>'
    body = f'''<div class="breadcrumb"><a href="../../index.html">首页</a><span>/</span><a href="../">学习日报</a><span>/</span><span>{day}</span></div>
<header class="article-head"><p class="eyebrow">THE DAILY NOTE / 学习日报</p>{tags(report)}<h1>{title_html(report["title"])}</h1><p class="intro">{esc(report["summary"])}</p>
<div class="article-meta"><span>常宝的学习手记</span><time datetime="{day}">{day}</time><span>约 {reading_minutes(report)} 分钟阅读</span>{bookmark(day)}<button type="button" class="button quiet js-only" data-copy-link>复制链接</button></div>
<p class="feedback" data-storage-status role="status"></p><p class="feedback" data-share-status role="status"></p>
</header>
<div class="article-layout"><article class="article-body" data-reading-body>
<div class="editor-note"><span class="eyebrow">本期说明</span><p>{esc(report["coverage"])}</p><p>{source_note}关键事实已核对来源。解读和练习为 AI 整理的学习建议，供继续探索。</p></div>
{"".join(blocks)}
<section class="practice-block" id="practice"><p class="eyebrow">FROM READING TO DOING</p><h2>把一个问题，变成一次尝试。</h2><ol>{suggestions}</ol><p class="news-date">以上为建议练习，尚未标记为个人已完成成果。</p></section>
</article><aside class="article-toc" aria-label="本期阅读目录"><details class="toc-panel" data-toc-panel open><summary><span>本期目录</span><span class="toc-count">{len(report["items"])} 条观察</span><span class="disclosure-icon" aria-hidden="true">⌄</span></summary><div class="toc-content"><ol class="toc-list">{"".join(toc)}<li><a href="#practice"><span>→</span>动手做一个小练习</a></li></ol><a class="text-link" href="../">查看全部日报 →</a></div></details></aside></div>
<nav class="reading-nav" aria-label="日报翻页">{older}{newer}</nav>'''
    return page(f"AI 日报 · {day}", report["summary"], body, "../../", reading=True)


def archive(reports):
    cards = []
    topic_counts = Counter(t for report in reports for t in set(report.get("topics", [])))
    topics = sorted(topic_counts, key=lambda t: (-topic_counts[t], t))
    for n, r in enumerate(reports):
        day = r["date"]
        cards.append(f'''<article class="archive-card" data-report data-date="{day}" data-search="{esc(searchable(r))}" data-topics="{esc(json.dumps(r.get("topics", []), ensure_ascii=False))}">
<div class="archive-meta"><time datetime="{day}">{day.replace("-", ".")}</time><span>第 {len(reports)-n:02d} 期</span></div>
<div class="archive-content">{tags(r)}<h2 class="archive-title"><a href="{day}/">{esc(r["title"])}</a></h2><p class="archive-summary">{esc(r["summary"])}</p><div class="archive-footer"><span>{len(r["items"])} 则观察 · 约 {reading_minutes(r)} 分钟</span><a class="text-link" href="{day}/">阅读这期 <span aria-hidden="true">↗</span></a></div></div>{bookmark(day)}</article>''')
    def topic_button(topic):
        return f'<button type="button" class="filter-chip" data-topic="{esc(topic)}" aria-pressed="false">{esc(topic)} <span class="topic-count">{topic_counts[topic]}</span></button>'

    filters = '<button type="button" class="filter-chip" data-topic="" aria-pressed="true">全部主题</button>' + "".join(topic_button(t) for t in topics[:4])
    more_topics = f'<details class="more-topics" data-more-topics><summary>更多主题 <span class="topic-count">{len(topics) - 4}</span><span class="disclosure-icon" aria-hidden="true">⌄</span></summary><div class="filter-list">{"".join(topic_button(t) for t in topics[4:])}</div></details>' if len(topics) > 4 else ""
    body = f'''<header class="page-hero"><p class="eyebrow">THE DAILY NOTES / 日常积累</p><h1>每天读一点，<br><em>再想深一点。</em></h1><p class="intro">把值得留意的 AI 进展，整理成可以回看的学习线索。<br>每一期，都留下来源、问题和下一次实践的起点。</p><div class="archive-overview"><span><strong>{len(reports):02d}</strong> 期学习日报</span><span>最近更新 <time datetime="{reports[0]["date"]}">{reports[0]["date"].replace("-", ".")}</time></span></div></header>
<section data-archive aria-label="日报归档">
<div class="archive-tools js-only"><label class="search-field" for="daily-search"><svg viewBox="0 0 24 24" width="21" height="21" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="6.5" stroke="currentColor" stroke-width="1.5"/><path d="m16 16 5 5" stroke="currentColor" stroke-width="1.5"/></svg><span class="sr-only">搜索日报全文</span><input id="daily-search" type="search" placeholder="搜索一个话题、关键词或日期…" autocomplete="off"></label><button class="button quiet" type="button" data-saved-filter aria-pressed="false">只看收藏</button></div>
<div class="topic-filters js-only" aria-label="按主题筛选"><div class="filter-list">{filters}</div>{more_topics}<p class="active-topic" data-active-topic hidden></p></div>
<div class="archive-caption"><p id="result-count" role="status" aria-live="polite">{len(reports)} 篇日报</p><span>按时间倒序排列</span></div>
<p class="feedback" data-storage-status role="status"></p>
<div class="archive-list">{"".join(cards)}</div>
<div id="archive-empty" class="empty-state" hidden><span aria-hidden="true">⌕</span><h2>还没有找到这条学习线索</h2><p>换一个关键词，或调整主题与收藏筛选。</p><button class="button" type="button" id="clear-filters">显示全部日报</button></div>
<p class="local-note js-only">收藏保存在当前浏览器中，方便下次接着读。</p>
<noscript><p class="local-note">所有日报均可直接阅读。启用 JavaScript 后可使用搜索、筛选和本机收藏。</p></noscript>
</section>'''
    return page("学习日报", "和AI一起学习：搜索、按主题筛选和收藏 AI 日报，回看原始来源与学习问题。", body, "../")


def teaser(reports):
    latest = reports[0]
    recent = '<ol class="recent-notes">' + "".join(f'<li><time datetime="{r["date"]}">{r["date"].replace("-", ".")}</time><a href="daily/{r["date"]}/">{esc(r["title"])}</a></li>' for r in reports[1:4]) + '</ol>' if len(reports) > 1 else '<p class="section-note">从第一期开始，一点点积累。</p>'
    return f'''{START}
<section id="daily" class="home-daily"><div class="section-head"><div><p class="eyebrow">学习日报</p><h2>最近的学习记录</h2></div><a class="text-link" href="daily/">查看全部 <span aria-hidden="true">→</span></a></div>
<div class="daily-layout"><article class="daily-feature"><div class="daily-date"><span class="eyebrow">最新一期</span><time datetime="{latest["date"]}">{latest["date"].replace("-", ".")}</time></div>{tags(latest)}<h3><a href="daily/{latest["date"]}/">{esc(latest["title"])}</a></h3><p>{esc(latest["summary"])}</p><div class="daily-feature-footer"><a class="button primary" href="daily/{latest["date"]}/">阅读这期日报 <span aria-hidden="true">↗</span></a><span>{len(latest["items"])} 则观察 · 约 {reading_minutes(latest)} 分钟</span></div></article>
<aside class="daily-side" aria-labelledby="recent-notes-title"><h3 id="recent-notes-title">前几期，也值得回看</h3>{recent}<div class="daily-side-footer"><p>{len(reports)} 期日报 · {sum(len(r["items"]) for r in reports)} 则观察</p><a class="text-link js-only" href="daily/?saved=1">我的收藏 →</a></div></aside></div></section>
{END}'''


def main():
    home = (ROOT / "index.html").read_text(encoding="utf-8-sig")
    if home.count(START) != 1 or home.count(END) != 1 or home.index(START) > home.index(END):
        raise ValueError("首页缺少唯一且顺序正确的日报更新标记")
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
    outputs = {ROOT / "daily" / r["date"] / "index.html": article(r, reports) for r in reports}
    outputs[ROOT / "daily/index.html"] = archive(reports)
    outputs[ROOT / "index.html"] = home[:home.index(START)] + teaser(reports) + home[home.index(END) + len(END):]
    for filename, content in outputs.items():
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text("\n".join(line.rstrip() for line in content.splitlines()) + "\n", encoding="utf-8", newline="\n")
    print(f"已生成 {len(reports)} 期日报、可搜索归档和首页最新入口。")


if __name__ == "__main__":
    main()
