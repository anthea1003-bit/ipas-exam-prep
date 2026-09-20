"""Build two self-contained-content pages from the four read-only source notes.

Only the Markdown features used in these notes are supported. Existing Pillow
is used solely to read the local JPEG dimensions; the website has no dependencies.
Run from any directory: python3 scripts/build_site.py
"""
from pathlib import Path
from datetime import date, timedelta
import html
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'source'
PLAN = '讀書計畫-資安AI-2026.md'
LAW = 'I11102 資安法規體系總整理.md'
AUDIT = 'I11102 ISO 27001 內部稽核員 課堂演練.md'
PIMS = 'I11103 ISO 27701 PIMS 內部稽核員.md'
LINKS = {Path(LAW).stem: '#law', Path(AUDIT).stem: '#audit', Path(PIMS).stem: '#pims'}
WARN = re.compile(r'尚未驗證|待確認|尚未查證|尚未經三層追問驗證|未作外部法規查證')
e = html.escape


def expand_plan_rows(rows):
    """Expand date spans, evenly distributing verbatim semicolon-delimited concepts."""
    expanded = [rows[0]]
    for row in rows[1:]:
        endpoints = row[0].split('–')
        dates = [date(2026, *map(int, part.split('/'))) for part in endpoints]
        days = (dates[-1] - dates[0]).days + 1
        if days == 1:
            expanded.append(row)
            continue
        allocated = [['', ''] for _ in range(days)]
        if row[1] == '總複習':
            # The source assigns four calculation families, three questions each.
            match = re.fullmatch(r'還沒過清零；四大計算題（(.+)）各做 3 題', row[2])
            assert match and days == 4 and not row[3], row
            topics = match[1].split('／')
            assert len(topics) == days, row
            allocated = [[f'還沒過清零；四大計算題（{topic}）做 3 題', ''] for topic in topics]
        else:
            offset = 0
            for col, value in enumerate(row[2:]):
                concepts = value.split('；') if value else []
                for idx, concept in enumerate(concepts):
                    day = (offset + idx) % days
                    allocated[day][col] += ('；' if allocated[day][col] else '') + concept
                offset += len(concepts)
        for offset, concepts in enumerate(allocated):
            day = dates[0] + timedelta(days=offset)
            expanded.append([f'{day.month}/{day.day}', row[1], *concepts])
    return expanded


def inline(text):
    # Escape first, then render known inline constructs; source HTML never executes.
    text = e(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    def wiki(match):
        parts = match[1].split('|', 1)
        target, label = parts[0], parts[-1]
        if html.unescape(target) in LINKS:
            return f'<a href="{LINKS[html.unescape(target)]}">{label}</a>'
        return f'<span class="unlinked" title="{target}">{label}</span>'

    text = re.sub(r'\[\[([^\]]+)\]\]', wiki, text)

    def link(match):
        label, url = match[1], match[2]
        # Local scratchpad paths must not be exposed in the public page.
        if url.startswith('file:'):
            return f'{label}（本機暫存檔，未隨網頁公開）'
        return f'<a href="{url}">{label}</a>'

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, text)
    return WARN.sub(r'<mark class="warning-mark">\g<0></mark>', text)


class Renderer:
    def __init__(self, prefix, plan=False):
        self.prefix, self.plan = prefix, plan
        self.headings = []
        self.table_index = 0
        self.lesson_count = 0

    def render(self, lines):
        out, i = [], 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line == '---':
                out.append('<hr>')
            elif line.startswith('#'):
                match = re.match(r'(#{1,6}) (.+)', line)
                assert match, line
                level = min(len(match[1]) + 1, 6)
                anchor = f'{self.prefix}-s{len(self.headings)+1}'
                self.headings.append((level, anchor, match[2]))
                out.append(f'<h{level} id="{anchor}">{inline(match[2])}</h{level}>')
            elif line.startswith('>'):
                quoted = []
                while i < len(lines) and lines[i].strip().startswith('>'):
                    quoted.append(re.sub(r'^> ?', '', lines[i].strip()))
                    i += 1
                if quoted and quoted[0].startswith('[!tip]'):
                    quoted[0] = '**' + quoted[0].replace('[!tip] ', '') + '**'
                out.append('<blockquote>\n' + self.render(quoted) + '\n</blockquote>')
                continue
            elif line.startswith('|'):
                rows = []
                while i < len(lines) and lines[i].strip().startswith('|'):
                    cells = [cell.strip() for cell in lines[i].strip().strip('|').split('|')]
                    if not all(re.fullmatch(r':?-+:?', cell) for cell in cells):
                        rows.append(cells)
                    i += 1
                out.append(self.table(rows))
                continue
            elif re.match(r'!\[\[.+\]\]', line):
                filename = line[3:-2]
                web = str(Path(filename).with_suffix('')).strip() + '-web.jpg'
                from PIL import Image
                with Image.open(ROOT / 'assets' / web) as img:
                    width, height = img.size
                out.append(f'<figure><a href="assets/{e(filename)}" class="image-link" aria-label="放大：{e(Path(filename).stem)}">'
                           f'<img src="assets/{e(web)}" width="{width}" height="{height}" loading="lazy" decoding="async" alt="{e(Path(filename).stem)}">'
                           '</a><figcaption>點擊圖卡，開啟原尺寸圖片</figcaption></figure>')
            elif re.match(r'(?:- |\d+\. )', line):
                # Preserve indented child lists instead of flattening the eight bylaws.
                ordered = bool(re.match(r'\d+\. ', line))
                kind = 'ol' if ordered else 'ul'
                items = []
                pattern = r'^\d+\. (.*)' if ordered else r'^- (.*)'
                while i < len(lines):
                    match = re.match(pattern, lines[i].strip())
                    if not match or lines[i].startswith(' '):
                        break
                    value = match[1]
                    if re.match(r'\[[ x]\] ', value):
                        checked = value[1] == 'x'
                        value = ('☑ ' if checked else '☐ ') + value[4:]
                    item = inline(value)
                    i += 1
                    children = []
                    while i < len(lines) and lines[i].startswith('   '):
                        children.append(lines[i][3:])
                        i += 1
                    if children:
                        item += '\n' + self.render(children)
                    items.append('<li>' + item + '</li>')
                out.append(f'<{kind}>\n' + '\n'.join(items) + f'\n</{kind}>')
                continue
            else:
                out.append('<p>' + inline(line) + '</p>')
            i += 1
        return '\n'.join(out)

    def table(self, rows):
        self.table_index += 1
        learning = self.plan and self.table_index <= 2
        drill = self.plan and self.table_index > 2
        if learning:
            rows = expand_plan_rows(rows)
        cls = 'lesson-table' if learning else 'data-table'
        out = [f'<div class="table-scroll" role="region" tabindex="0" aria-label="{e(self.headings[-1][2])}">',
               f'<table class="{cls}">', '<thead><tr>']
        out.extend(f'<th scope="col">{inline(c)}</th>' for c in rows[0])
        if learning or drill:
            out.append('<th scope="col">日期狀態</th>')
        out.extend(['</tr></thead>', '<tbody>'])
        for row in rows[1:]:
            attrs = ''
            if learning or drill:
                month, day = map(int, row[0].split('/'))
                scheduled = date(2026, month, day)
                subject = 'security' if self.table_index == 1 else 'ai'
                cutoff = date(2026, 10, 17) if subject == 'security' else date(2026, 10, 31)
                kind = 'lesson' if learning and scheduled < cutoff else 'drill'
                if '考試' in row[1] and '休息' not in row[1]:
                    kind = 'exam'
                elif '休息' in row[1] or (drill and '休息' in row[2]):
                    kind = 'rest'
                self.lesson_count += kind == 'lesson'
                attrs = f' data-date="{scheduled.isoformat()}" data-kind="{kind}"'
                attrs += f' data-schedule="{subject if learning else "drill-summary"}"'
            out.append(f'<tr{attrs}>')
            for idx, cell in enumerate(row):
                out.append(f'<td data-label="{e(rows[0][idx])}">{inline(cell)}</td>')
            if learning or drill:
                out.append('<td class="date-status" data-label="日期狀態">已排定</td>')
            out.append('</tr>')
        out.extend(['</tbody></table>', '</div>'])
        return '\n'.join(out)


def note(filename, prefix):
    lines = (SOURCE / filename).read_text().splitlines()
    metadata = ''
    if lines[0] == '---':
        end = lines.index('---', 1)
        metadata = ('<details class="metadata"><summary>筆記資料與原始來源</summary>'
                    f'<pre>{inline(chr(10).join(lines[:end+1]))}</pre>'
                    f'<p><a href="source/{e(filename)}">開啟完整 Markdown 原稿</a></p></details>')
        lines = lines[end+1:]
    renderer = Renderer(prefix, prefix == 'plan')
    content = renderer.render(lines)
    return metadata + '\n' + content, renderer


def shell(title, page, hero, content, toc):
    return f'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<meta name="description" content="{e(title)}；完整保留 Obsidian 學習筆記與待確認紀錄。">
<title>{e(title)}</title>
<link rel="icon" href="data:,">
<link rel="stylesheet" href="styles.css">
<script src="app.js" defer></script>
</head>
<body class="{page}">
<a class="skip-link" href="#main">跳至主要內容</a>
<header class="site-header"><div class="header-inner">
<a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true">A.</span> Anthea<span class="brand-note">備考手帳 / 2026</span></a>
<nav aria-label="主要導覽"><a href="index.html" {'aria-current="page"' if page == 'plan' else ''}>讀書計畫</a><a href="regulations.html" {'aria-current="page"' if page == 'regulations' else ''}>法規與 ISO</a></nav>
</div></header>
<main id="main">
<section class="hero"><p class="eyebrow">2026 STUDY NOTES <span aria-hidden="true">/</span> {'01 — PLAN' if page == 'plan' else '02 — REFERENCE'}</p>
<h1>{title}</h1>{hero}</section>
<div class="reading-layout"><aside class="page-toc"><nav aria-label="頁內目錄"><p class="toc-label">本頁目錄</p>{toc}</nav></aside>
<div class="reading-content">{content}</div></div>
</main>
<footer><p>來源：Obsidian 學習筆記；最後更新 {'2026-09-20' if page == 'plan' else '2026-09-15'}</p><a href="#main">回到頁首 ↑</a></footer>
</body>
</html>
'''


def toc_for(renderer, max_level=3):
    return '\n'.join(f'<a href="#{anchor}" class="toc-level-{level}">{inline(label)}</a>'
                     for level, anchor, label in renderer.headings if level <= max_level)


def build():
    content, plan = note(PLAN, 'plan')
    hero = '''<p class="hero-intro">每天 2 小時：資安 1 小時＋AI 科目三 1 小時，使用 <code>/coach</code> 費曼學習法</p>
<div class="countdown-grid">
<section class="countdown security"><p class="card-label">🔐 資安初級</p><p class="countdown-value"><strong data-countdown="2026-10-31">—</strong><span data-countdown-label>天後考試</span></p><p class="exam-date">2026 / 10 / 31・週六</p></section>
<section class="countdown ai"><p class="card-label">🤖 AI 中級科三</p><p class="countdown-value"><strong data-countdown="2026-11-14">—</strong><span data-countdown-label>天後考試</span></p><p class="exam-date">2026 / 11 / 14・週六</p></section>
</div>
<section class="progress-panel" aria-labelledby="progress-title"><div class="progress-heading"><h2 id="progress-title">學習期・日期進度</h2><span id="progress-count">— / LESSON_COUNT 堂</span></div>
<progress id="schedule-progress" max="LESSON_COUNT" value="0" aria-labelledby="progress-title"></progress>
<div class="progress-caption"><p>依排定日期計算，不代表已完成學習。</p><p id="today-label">日期狀態於啟用 JavaScript 後顯示</p></div></section>
<noscript><p class="notice">JavaScript 未啟用：倒數、日期狀態與進度不計算；完整課表仍可閱讀。</p></noscript>'''
    hero = hero.replace('LESSON_COUNT', str(plan.lesson_count))
    (ROOT / 'index.html').write_text(shell('iPAS 資安初級＋AI 中級科三 讀書計畫', 'plan', hero, content, toc_for(plan)))

    law_content, law = note(LAW, 'law')
    audit_content, audit = note(AUDIT, 'audit')
    pims_content, pims = note(PIMS, 'pims')
    raw_law = (SOURCE / LAW).read_text()
    numbers = raw_law.split('### 關鍵數字\n')[1].split('\n### ')[0].strip().splitlines()
    quick = ['<section id="quick-numbers" class="quick-reference"><h2>關鍵數字速查</h2>',
             '<p class="notice"><strong>尚未驗證</strong> · 以下逐項摘錄來源；時限數字與法源仍待驗證。</p>', '<dl class="number-grid">']
    for line in numbers:
        text = line.removeprefix('- ')
        if '：' in text:
            label, value = text.split('：', 1)
        else:
            label, value = '責任等級／委外／日誌', text
        quick.append(f'<div><dt>{inline(label)}</dt><dd>{inline(value)}</dd></div>')
    quick.append('</dl></section>')
    # Each comparison cell is an exact source excerpt; conflicting claims remain flagged.
    iso_rows = [
        ('27001', '管理制度要求→27001；控制措施怎麼做→27002'),
        ('27002', '管理制度要求→27001；控制措施怎麼做→27002'),
        ('27017', '雲端一般控制、供應商＋客戶→27017；公有雲＋個資＋處理者→27018'),
        ('27018', '雲端一般控制、供應商＋客戶→27017；公有雲＋個資＋處理者→27018'),
        ('27005', '27005 只管資安風險；31000 管組織整體風險、不可驗證發證'),
        ('31000', '27005 只管資安風險；31000 管組織整體風險、不可驗證發證'),
        ('27701', '27701:2025 可獨立驗證（2019 舊版須先有 27001）'),
        ('42001', '42001 AI 管理系統'), ('22301', '22301 營運持續'),
        ('20000', '20000 IT 服務管理'), ('17025', '17025 實驗室認證（數位鑑識）')]
    quick.extend(['<section id="iso-lookup"><h2>ISO 判題口訣對照表</h2>',
                  '<p class="notice"><strong>尚未驗證／待確認</strong> · ISO 是「標準」不是法規。版本年份與驗證適用範圍請連同<a href="#law-s10">卡點紀錄</a>閱讀。</p>',
                  '<div class="table-scroll" role="region" tabindex="0" aria-label="ISO 判題口訣對照表"><table class="data-table iso-table"><thead><tr><th scope="col">ISO</th><th scope="col">來源判題口訣</th></tr></thead><tbody>'])
    for code, quote in iso_rows:
        assert quote in raw_law, quote
        quick.append(f'<tr><th scope="row">{code}</th><td>{inline(quote)}</td></tr>')
    quick.extend(['</tbody></table></div>',
                  '<p class="notice">原稿並列「27701:2025 可獨立驗證」與「27001 是唯一可第三方驗證取證的 27000 系列標準」，本次保留來源說法，適用範圍待確認。</p></section>'])
    hero = '<p class="hero-intro">法規層級、關鍵數字與 ISO 判題線索，以及兩份內部稽核員課堂筆記。</p><p class="notice"><strong>學習筆記・尚未驗證</strong><br>本次依指定素材整理，未作外部法規查證。來源中的待確認事項完整保留。</p>'
    content = '\n'.join(quick) + f'\n<article id="law">{law_content}</article>'
    content += f'\n<details id="audit" class="chapter"><summary><span class="chapter-kicker">課堂筆記 01</span>ISO 27001 內部稽核員 課堂演練</summary><div class="chapter-body">{audit_content}</div></details>'
    content += f'\n<details id="pims" class="chapter"><summary><span class="chapter-kicker">課堂筆記 02</span>ISO 27701 PIMS 內部稽核員</summary><div class="chapter-body">{pims_content}</div></details>'
    toc = '<a href="#quick-numbers">關鍵數字速查</a><a href="#iso-lookup">ISO 判題口訣對照表</a>' + toc_for(law)
    toc += '<a href="#audit">課堂演練 · ISO 27001</a><a href="#pims">隱私管理 · ISO 27701</a>'
    # Resolve by heading text instead of assuming a heading number.
    warning_id = next(anchor for _, anchor, label in law.headings if '卡點紀錄' in label)
    content = content.replace('href="#law-s10"', f'href="#{warning_id}"')
    (ROOT / 'regulations.html').write_text(shell('資安考試 法規與 ISO 規範總整理', 'regulations', hero, content, toc))


if __name__ == '__main__':
    build()
    print('Built index.html and regulations.html from 4 source notes.')
