/* Completion behavior through DOM events; uses only Node's built-in runner. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function fixture(saved = new Map(), blocked = false) {
  const element = () => ({ textContent: '', events: {}, addEventListener(type, fn) { this.events[type] = fn; } });
  const nodes = Object.fromEntries(['completion-title', 'completion-security-count', 'completion-ai-count',
    'completion-security-progress', 'completion-ai-progress', 'completion-status',
    'copy-progress', 'paste-progress', 'clear-progress'].map(id => [id, element()]));
  const boxes = ['security', 'ai'].flatMap(subject => Array.from({ length: subject === 'security' ? 41 : 55 }, (_, i) => {
    const day = new Date(Date.UTC(2026, 8, 21 + i)).toISOString().slice(0, 10);
    const flags = {};
    const row = { dataset: { schedule: subject, date: day }, classList: { toggle(name, value) { flags[name] = value; } } };
    return { ...element(), checked: false, disabled: true, flags,
      dataset: { completionKey: `ipas:completed:${subject}:${day}` }, closest() { return row; } };
  }));
  const storage = {
    getItem(key) { if (blocked) throw Error('blocked'); return saved.get(key) ?? null; },
    setItem(key, value) { if (blocked) throw Error('blocked'); saved.set(key, value); },
    removeItem(key) { if (blocked) throw Error('blocked'); saved.delete(key); },
  };
  let code, input, confirmed = false;
  const sandbox = { module: { exports: {} }, localStorage: storage,
    navigator: { clipboard: { async writeText(value) { code = value; } } },
    window: { prompt(message, value) { code = value ?? code; return input; }, confirm() { return confirmed; }, addEventListener() {} },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../app.js'), 'utf8'), sandbox);
  sandbox.document = { getElementById(id) { return nodes[id]; }, querySelectorAll() { return boxes; } };
  sandbox.module.exports.initCompletion();
  return { boxes, nodes, saved, sandbox, get code() { return code; },
    toggle(i, value) { boxes[i].checked = value; boxes[i].events.change(); },
    copy() { return nodes['copy-progress'].events.click(); },
    paste(value) { input = value; nodes['paste-progress'].events.click(); },
    clear(value) { confirmed = value; nodes['clear-progress'].events.click(); } };
}

test('all 96 dates persist independently, restore, dim and update subject counts', () => {
  const f = fixture();
  for (let i = 0; i < 96; i++) f.toggle(i, true);
  assert.equal(f.saved.size, 96);
  assert.equal(f.nodes['completion-security-count'].textContent, '資安 41/41');
  assert.equal(f.nodes['completion-ai-count'].textContent, 'AI 55/55');
  const restored = fixture(f.saved);
  assert.ok(restored.boxes.every(box => box.checked && box.flags['is-complete'] && !box.disabled));
  restored.toggle(0, false);
  assert.equal(restored.nodes['completion-security-progress'].value, 40);
  assert.equal(restored.boxes[0].flags['is-complete'], false);
  assert.equal(restored.boxes[41].checked, true);
  assert.equal(fixture(f.saved).boxes[0].checked, false);
});

test('short code round-trips across devices, merges, and rejects malformed input atomically', async () => {
  const source = fixture();
  [0, 40, 41, 95].forEach(i => source.toggle(i, true));
  await source.copy();
  assert.ok(source.code.length < 50);
  const target = fixture();
  target.toggle(1, true);
  target.paste(source.code);
  assert.deepEqual(target.boxes.flatMap((box, i) => box.checked ? [i] : []), [0, 1, 40, 41, 95]);
  target.paste(source.code);
  for (const invalid of [null, '', 'garbage', source.code + 'x', source.code.replace('IPAS1', 'IPAS2')]) target.paste(invalid);
  assert.equal(target.saved.size, 5);
  assert.equal(fixture(target.saved).nodes['completion-ai-progress'].value, 2);
});

test('clear requires confirmation and preserves unrelated storage', () => {
  const f = fixture(new Map([['unrelated', 'keep']]));
  f.toggle(0, true);
  f.clear(false);
  assert.equal(f.boxes[0].checked, true);
  f.clear(true);
  assert.ok(f.boxes.every(box => !box.checked && !box.flags['is-complete']));
  assert.deepEqual([...f.saved], [['unrelated', 'keep']]);
  assert.equal(f.nodes['completion-security-progress'].value, 0);
});

test('blocked storage and clipboard still allow session progress and manual code transfer', async () => {
  const f = fixture(new Map(), true);
  f.toggle(95, true);
  assert.equal(f.nodes['completion-ai-progress'].value, 1);
  assert.match(f.nodes['completion-status'].textContent, /儲存/);
  f.sandbox.navigator.clipboard.writeText = async () => { throw Error('denied'); };
  await f.copy();
  const target = fixture();
  target.paste(f.code);
  assert.equal(target.boxes[95].checked, true);
});
