"""Read-only acceptance checks; output is deliberately compact, 1–6 in order."""
from pathlib import Path
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import hashlib
import json
import re
import sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PLAN_SHA256 = 'd9ebd791f1a3956fdda2396ae2e0a0132d1d39302f272b193e3172403e8f13b5'
SECURITY_SOURCE_SHA256 = 'ca9117691269ecc5400c07e70d3e49dffa3b2d8b0aaa678a4d91be5739f4f08d'
SECURITY_CONTROLS_SHA256 = 'db25a32e81d4922ee17dbf41a63d383694d23f1d238066f1073fe68e9e821abd'
REGULATIONS_SHA256 = '0934ccbedc2b77bbab11f966a2f6744ee0c1a9bdc648cfe9f718dbd2330d5d69'
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.refs, self.ids, self.text = [], [], [], set(), []
        self.sections, self.scopes = {}, []
        self.schedule_rows, self.cell = [], None
        self.checkboxes = []
        self.table_headers, self.header_cell = [], None
        self.feed(text)
        self.close()
        assert not self.errors and not self.stack, (self.errors, self.stack)

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if tag == 'table':
            self.table_headers.append([])
        if tag == 'th' and attrs.get('scope') == 'col':
            self.header_cell = []
        if tag == 'input' and attrs.get('type') == 'checkbox':
            self.checkboxes.append(attrs)
            assert self.stack[-1] == 'th' and self.schedule_rows[-1]['cells'] == []
            self.schedule_rows[-1].setdefault('checkboxes', []).append(attrs)
        if tag == 'tr' and 'data-schedule' in attrs:
            self.schedule_rows.append({'attrs': attrs, 'cells': []})
        if tag == 'td' and self.schedule_rows:
            self.cell = []
            self.schedule_rows[-1].setdefault('labels', []).append(attrs.get('data-label'))
        if tag not in VOID:
            self.stack.append(tag)
        section = attrs.get('id')
        if section in {'law', 'audit', 'pims'} or attrs.get('class') == 'reading-content':
            section = section or 'plan'
            self.sections[section] = []
            self.scopes.append((len(self.stack), section))
        if 'id' in attrs:
            assert attrs['id'] not in self.ids, 'duplicate id: ' + attrs['id']
            self.ids.add(attrs['id'])
        self.refs += [(tag, key, attrs[key]) for key in ('src', 'href') if key in attrs]

    def handle_endtag(self, tag):
        if tag == 'th' and self.header_cell is not None:
            self.table_headers[-1].append(''.join(self.header_cell))
            self.header_cell = None
        if tag == 'td' and self.cell is not None:
            self.schedule_rows[-1]['cells'].append(''.join(self.cell))
            self.cell = None
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f'unexpected closing {tag}; stack={self.stack}')
        else:
            if self.scopes and self.scopes[-1][0] == len(self.stack):
                self.scopes.pop()
            self.stack.pop()

    def handle_data(self, text):
        if self.header_cell is not None:
            self.header_cell.append(text)
        if self.cell is not None:
            self.cell.append(text)
        self.text.append(text)
        if self.scopes:
            self.sections[self.scopes[-1][1]].append(text)


def normalize(text):
    return re.sub(r'\s+', '', text)


def plain_source(line):
    line = line.strip()
    if not line or line == '---' or re.fullmatch(r'\|[\s:|\-]+\|', line):
        return []
    if line.startswith('![['):
        return []  # Image mapping is checked separately.
    line = re.sub(r'^> ?', '', line)
    line = re.sub(r'^\[!tip\] ?', '', line)
    line = re.sub(r'^#{1,6} ', '', line)
    line = re.sub(r'^(?:- |\d+\. )', '', line)
    line = re.sub(r'^\[[ x]\] ', '', line)
    line = re.sub(r'\[\[([^\]]+)\]\]', lambda m: m[1].split('|')[-1], line)
    line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
                  lambda m: m[1] + '（本機暫存檔，未隨網頁公開）'
                  if m[2].startswith('file:') else f'{m[1]} {m[2]}', line)
    line = line.replace('**', '').replace('`', '')
    return [cell.strip() for cell in line.strip('|').split('|')] if line.startswith('|') else [line]


pages = {name: Page((ROOT / name).read_text()) for name in ('index.html', 'regulations.html')}
raw = {name: (ROOT / name).read_text() for name in pages}


def check1():
    required = ['index.html', 'regulations.html', '.nojekyll', 'README.md']
    assert all((ROOT / name).is_file() for name in required)
    images = list((ROOT / 'assets').glob('*-web.jpg'))
    assert len(images) == 3
    assert (ROOT / '.nojekyll').stat().st_size == 0
    assert len((ROOT / 'README.md').read_text().splitlines()) == 3
    print('1 PASS: 4 required files + 3 web JPEGs; .nojekyll empty; README 3 lines')


def check2():
    index, regulations = raw.values()
    tables, headers, table = [], [], None
    plan_source = (ROOT / 'source/讀書計畫-資安AI-2026.md').read_text()
    for line in plan_source.splitlines():
        if line.startswith('| 日期 |'):
            headers.append([cell.strip() for cell in line.strip('|').split('|')])
            table = []
            tables.append(table)
        elif re.match(r'\| \d', line):
            assert table is not None
            table.append(plain_source(line))
    expected_headers = [
        ['日期', '範圍', '核心費曼（20 分）', '快速比較（10 分）', '學習分鐘', '模考分鐘（另計）'],
        ['日期', '區塊', '核心費曼（20 分）', '快速比較（10 分）', '程式題型', '併入／安排內容', '替換與減量（不另加時）', '學習分鐘', '模考分鐘（另計）'],
        ['日期', '複習', '核心費曼（20 分）', '快速（10 分）', '程式題型', '併入／安排內容', '替換與減量（不另加時）', '學習分鐘', '模考分鐘（另計）'],
        ['日期', '科目', '階段', '內容'],
    ]
    assert headers == expected_headers, headers
    assert [len(table) for table in tables] == [41, 14, 41, 28]
    for i, (header, rows) in enumerate(zip(headers, tables)):
        assert all(len(row) == len(header) for row in rows), i
    assert pages['index.html'].table_headers == [
        (['完成'] if i < 3 else []) + header + ['日期狀態']
        for i, header in enumerate(headers)]
    schedules = [tables[0], tables[1] + tables[2], tables[3]]
    labels = [[headers[0]] * 41,
              [headers[1]] * 14 + [headers[2]] * 41,
              [headers[3]] * 28]
    for subject, source_rows, row_labels, count in zip(
            ('security', 'ai', 'drill-summary'), schedules, labels, (41, 55, 28)):
        actual = [row for row in pages['index.html'].schedule_rows if row['attrs']['data-schedule'] == subject]
        assert len(actual) == len(source_rows) == count, (subject, len(actual))
        expected_dates = []
        for rendered, cells, header in zip(actual, source_rows, row_labels):
            day = date(2026, *map(int, cells[0].split('/')))
            expected_dates.append(day.isoformat())
            kind = 'drill'
            if subject != 'drill-summary':
                cutoff = date(2026, 10, 17) if subject == 'security' else date(2026, 10, 31)
                if day < cutoff:
                    kind = 'lesson'
                if '休息' in cells[1]:
                    kind = 'rest'
                elif '考試' in cells[1]:
                    kind = 'exam'
            elif '休息' in cells[2]:
                kind = 'rest'
            assert rendered['attrs']['data-date'] == day.isoformat(), (subject, day)
            assert rendered['attrs']['data-kind'] == kind, (subject, day, kind)
            assert rendered['cells'] == cells + ['已排定'], (subject, day, rendered['cells'], cells)
            assert rendered['labels'] == header + ['日期狀態'], (subject, day, rendered['labels'])
        if subject != 'drill-summary':
            assert expected_dates == [(date(2026, 9, 21) + timedelta(days=i)).isoformat() for i in range(count)]
    assert len(re.findall(r'data-kind="lesson"', index)) == 66
    # Explicit duration/rest acceptance guards complement the full cell comparison.
    for subject, dates, minutes in (
            ('security', ('10-17', '10-19', '10-21', '10-23', '10-25', '10-28', '10-29'), '75'),
            ('ai', ('11-01', '11-03', '11-07', '11-10', '11-12'), '90')):
        for day in dates:
            row = next(r for r in pages['index.html'].schedule_rows
                       if r['attrs']['data-schedule'] == subject and r['attrs']['data-date'] == '2026-' + day)
            assert row['cells'][-3:-1] == ['0', minutes], (subject, day)
            assert ('計時另計' if subject == 'security' else '模考另計') in ''.join(row['cells']), (subject, day)
            assert row['labels'][-2] == '模考分鐘（另計）', (subject, day)
    ai_rows = [row for row in pages['index.html'].schedule_rows if row['attrs']['data-schedule'] == 'ai']
    current_ai = '\n'.join(' '.join(row['cells']) for row in ai_rows if row['attrs']['data-date'] >= '2026-10-05')
    assert 'AutoML' in current_ai and '114-2 Q42–44' in current_ai
    assert '形狀鏈' not in current_ai and '第 49 題注意力專練' not in current_ai
    assert '正式卷程式錯題只選最多兩個弱點群' in next(row['cells'][2] for row in ai_rows if row['attrs']['data-date'] == '2026-11-06')
    assert '2026-10-05' in index
    assert 'id="schedule-progress" max="66"' in index and '一般學習日每科 60 分鐘是學習時間' in index
    assert normalize(plain_source(plan_source.splitlines()[14])[0]) in normalize(''.join(pages['index.html'].text))
    for day, topic in (('2026-10-28', '混淆矩陣手算 P/R/F1 類 3 題'),
                       ('2026-10-29', 'Grid 組合數類 3 題')):
        row = next(r for r in ai_rows if r['attrs']['data-date'] == day)
        assert row['attrs']['data-kind'] == 'lesson' and row['cells'][1] == '總複習'
        assert row['cells'][2] == topic, day
        assert row['cells'][-3:-1] == ['20', '0'], day
    assert '不排（資安計時重做日' not in index
    assert '114-2 Q32' in next(r['cells'][2] for r in ai_rows if r['attrs']['data-date'] == '2026-10-06')
    assert '每週二、六晚上各 1 小時' not in index
    words = ['1 小時內', '72 小時', '36 小時', '30 萬', '1,000 萬', '27017', '27018', '42001', '17025', '27701:2025', '尚未驗證', '待確認']
    assert all(word in regulations for word in words)
    checked = 0
    scopes = {'讀書計畫': 'plan', 'I11102 資安法規': 'law', 'I11102 ISO': 'audit', 'I11103 ISO': 'pims'}
    for source in sorted((ROOT / 'source').glob('*.md')):
        page = pages['index.html' if source.name.startswith('讀書計畫') else 'regulations.html']
        section = next(scope for prefix, scope in scopes.items() if source.name.startswith(prefix))
        rendered = normalize(''.join(page.sections[section]))
        cursor = 0
        for line_no, line in enumerate(source.read_text().splitlines(), 1):
            if section == 'plan' and line.startswith('|') and not line.startswith('| 日期 |'):
                # All dated cells and display labels are compared independently above.
                continue
            for fragment in plain_source(line):
                fragment = normalize(fragment)
                position = rendered.find(fragment, cursor)
                assert position >= 0, f'{source.name}:{line_no}: missing or out of order: {fragment}'
                cursor = position + len(fragment)
                checked += 1
        for filename in re.findall(r'!\[\[([^\]]+)\]\]', source.read_text()):
            assert ('a', 'href', 'assets/' + filename) in page.refs
            assert ('img', 'src', 'assets/' + Path(filename).stem + '-web.jpg') in page.refs
    print(f'2 PASS: security 41/41 + AI 55/55 days; drill summary 28/28; lessons 66; columns 6/9/9/4; mock durations 12/12; keywords 12/12; source fragments {checked}/{checked}')


def check3():
    checked = 0
    for name, page in pages.items():
        for tag, attr, ref in page.refs:
            url = urlsplit(ref)
            if url.scheme:
                assert url.scheme == 'data', ref
                continue
            path = ROOT / unquote(url.path) if url.path else ROOT / name
            assert path.is_file(), ref
            if url.fragment:
                target = pages.get(path.name)
                assert target and unquote(url.fragment) in target.ids, ref
            checked += 1
    print(f'3 PASS: HTMLParser strict tag stacks 2/2; duplicate IDs 0; local files/anchors {checked}/{checked}')


def check4():
    security_rows = re.findall(r'<tr data-date="[^"]+" data-kind="[^"]+" data-schedule="security">.*?</tr>',
                               raw['index.html'], re.S)
    assert len(security_rows) == 41
    # Pin the approved revised security section, including its minute columns;
    # check2 independently compares every rendered cell.
    plan_source = (ROOT / 'source/讀書計畫-資安AI-2026.md').read_text()
    security_source = plan_source.split('### 🔐 資安初級', 1)[1].split('### 🤖 AI 中級科三', 1)[0]
    assert hashlib.sha256(security_source.encode()).hexdigest() == SECURITY_SOURCE_SHA256
    # Scheduling attributes and completion controls also retain the old site keys.
    security_controls = re.sub(r'<td\b[^>]*>.*?</td>', '', '\n'.join(security_rows), flags=re.S)
    # Ignore inter-tag whitespace left by removed data cells; adding minute
    # columns must not change the pinned original control markup/attributes.
    security_controls = re.sub(r'>\s+<', '><', security_controls)
    assert hashlib.sha256(security_controls.encode()).hexdigest() == SECURITY_CONTROLS_SHA256
    assert hashlib.sha256((ROOT / 'regulations.html').read_bytes()).hexdigest() == REGULATIONS_SHA256
    baseline = json.loads((ROOT / 'evidence/originals.json').read_text())
    for name, expected in baseline.items():
        p = ROOT / name
        if name == 'source/讀書計畫-資安AI-2026.md':
            # This is the sole authorized source replacement; pin its reviewed version.
            assert hashlib.sha256(p.read_bytes()).hexdigest() == PLAN_SHA256, name
            continue
        assert p.stat().st_size == expected['bytes'], name
        assert hashlib.sha256(p.read_bytes()).hexdigest() == expected['sha256'], name
    sizes = []
    for path in sorted((ROOT / 'assets').glob('*-web.jpg')):
        with Image.open(path) as im:
            assert im.width == 1600
            im.verify()
        size = path.stat().st_size
        assert size < 500000
        sizes.append(str(size))
    print(f'4 PASS: 3 JPEGs width=1600; bytes={"/".join(sizes)} (<500000); original PNGs 3/3 + reference sources 3/3 unchanged; revised plan SHA256 pinned; revised security content pinned + site controls 41/41 + regulations.html unchanged')


def check5():
    assert not re.search(r'/Users/|file://|/private/(?:tmp|var)/', raw['index.html'])
    for page in pages.values():
        for tag, attr, ref in page.refs:
            if attr == 'src' or tag == 'link':
                assert not re.match(r'(?:https?:)?//', ref), ref
    css = (ROOT / 'styles.css').read_text()
    js = (ROOT / 'app.js').read_text()
    assert '@import' not in css and 'url(' not in css
    assert not re.search(r'\b(fetch|XMLHttpRequest|WebSocket|import)\s*\(', js)
    print('5 PASS: external JS/CSS/font/image dependencies 0; fetch/XHR/import calls 0; relative local assets only')


def check6():
    page = pages['index.html']
    assert len(page.checkboxes) == 96, len(page.checkboxes)
    expected_keys = set()
    for row in page.schedule_rows:
        subject = row['attrs']['data-schedule']
        boxes = row.get('checkboxes', [])
        if subject == 'drill-summary':
            assert not boxes
            continue
        day = row['attrs']['data-date']
        key = f'ipas:completed:{subject}:{day}'
        expected_keys.add(key)
        assert len(boxes) == 1 and boxes[0]['data-completion-key'] == key
        assert boxes[0].get('aria-label')
    assert len(expected_keys) == 96
    assert not pages['regulations.html'].checkboxes
    assert all(identifier in page.ids for identifier in (
        'completion-security-progress', 'completion-ai-progress',
        'copy-progress', 'paste-progress', 'clear-progress'))
    print('6 PASS: 96 leftmost checkboxes (security 41 + AI 55); unique date/subject keys; completion controls present')


checks = [check1, check2, check3, check4, check5, check6]
if __name__ == '__main__':
    for check in ([checks[int(sys.argv[1])-1]] if len(sys.argv) > 1 else checks):
        check()
