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
PLAN_SHA256 = '16a71b8e23191d4f4a320ef942fe80fde0045ed93df0751288d0356a293b7b04'
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.refs, self.ids, self.text = [], [], [], set(), []
        self.sections, self.scopes = {}, []
        self.schedule_rows, self.cell = [], None
        self.checkboxes = []
        self.feed(text)
        self.close()
        assert not self.errors and not self.stack, (self.errors, self.stack)

    def handle_starttag(self, tag, pairs):
        attrs = dict(pairs)
        if tag == 'input' and attrs.get('type') == 'checkbox':
            self.checkboxes.append(attrs)
            assert self.stack[-1] == 'th' and self.schedule_rows[-1]['cells'] == []
            self.schedule_rows[-1].setdefault('checkboxes', []).append(attrs)
        if tag == 'tr' and 'data-schedule' in attrs:
            self.schedule_rows.append({'attrs': attrs, 'cells': []})
        if tag == 'td' and self.schedule_rows:
            self.cell = []
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
    tables, table = [], None
    for line in (ROOT / 'source/讀書計畫-資安AI-2026.md').read_text().splitlines():
        if line.startswith('| 日期 |'):
            table = []
            tables.append(table)
        elif re.match(r'\| \d', line):
            table.append([cell.strip().replace('**', '') for cell in line.strip('|').split('|')])
    assert len(tables) == 3 and len(tables[0]) == 41 and len(tables[2]) == 28
    for subject, source_rows, count in zip(('security', 'ai', 'drill-summary'), tables, (41, 55, 28)):
        actual = [row for row in pages['index.html'].schedule_rows if row['attrs']['data-schedule'] == subject]
        expected = []
        for row in source_rows:
            ends = [date(2026, *map(int, day.split('/'))) for day in row[0].split('–')]
            days = (ends[-1] - ends[0]).days + 1
            for offset in range(days):
                day = ends[0] + timedelta(days=offset)
                cells = row[:]
                cells[0] = f'{day.month}/{day.day}'
                if days > 1:
                    if row[1] == '總複習':
                        topic = ('參數量', '混淆矩陣', 'Grid', '形狀鏈')[offset]
                        cells[2:] = [f'還沒過清零；四大計算題（{topic}）做 3 題', '']
                    else:
                        full, quick = row[2].split('；'), row[3].split('；') if row[3] else []
                        cells[2:] = ['；'.join(full[offset::days]),
                                     '；'.join(term for i, term in enumerate(quick) if (i + len(full)) % days == offset)]
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
                expected.append((day.isoformat(), kind, cells))
        assert len(actual) == len(expected) == count, (subject, len(actual), len(expected))
        for rendered, (day, kind, cells) in zip(actual, expected):
            assert rendered['attrs']['data-date'] == day, (subject, day)
            assert rendered['attrs']['data-kind'] == kind, (subject, day, kind)
            assert rendered['cells'] == cells + ['已排定'], (subject, day, rendered['cells'], cells)
        if subject != 'drill-summary':
            assert [row[0] for row in expected] == [(date(2026, 9, 21) + timedelta(days=i)).isoformat() for i in range(count)]
    assert len(re.findall(r'data-kind="lesson"', index)) == 66
    assert 'max="66"' in index and '每天 2 小時' in index and '2026-09-20 改版' in index
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
                # All dated cells are compared above after independent span expansion.
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
    print(f'2 PASS: security 41/41 + AI 55/55 days; drill summary 28/28; lessons 66; keywords 12/12; source fragments {checked}/{checked}')


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
    print(f'4 PASS: 3 JPEGs width=1600; bytes={"/".join(sizes)} (<500000); original PNGs 3/3 + reference sources 3/3 unchanged; revised plan SHA256 pinned')


def check5():
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
for check in ([checks[int(sys.argv[1])-1]] if len(sys.argv) > 1 else checks):
    check()
