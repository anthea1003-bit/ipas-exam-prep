/* Calendar dates stay in the 2026 plan; today's date uses the device's local zone. */
(() => {
  'use strict';
  const DAY = 86400000;
  const dateNumber = date => Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / DAY;
  const scheduledDay = iso => {
    const [year, month, day] = iso.split('-').map(Number);
    return Date.UTC(year, month - 1, day) / DAY;
  };

  function calendarState(iso, now) {
    const today = dateNumber(now);
    const target = scheduledDay(iso);
    const monday = today - (now.getDay() + 6) % 7;
    return { remaining: target - today, past: target < today, week: target >= monday && target < monday + 7 };
  }

  function updateSchedule(now = new Date()) {
    const lessons = document.querySelectorAll('[data-kind="lesson"]');
    let pastLessons = 0;
    document.querySelectorAll('[data-date]').forEach(row => {
      const state = calendarState(row.dataset.date, now);
      row.classList.toggle('is-past', state.past);
      row.classList.toggle('is-week', state.week);
      const status = row.querySelector('.date-status');
      status.replaceChildren();
      if (state.week) {
        const badge = document.createElement('span');
        badge.className = 'badge';
        badge.textContent = '本週';
        status.append(badge);
      }
      status.append(document.createTextNode(state.past ? '已排定日期已過' : state.remaining === 0 ? '今天' : '已排定'));
      if (state.past && row.dataset.kind === 'lesson') pastLessons++;
    });
    document.querySelectorAll('[data-countdown]').forEach(element => {
      const { remaining } = calendarState(element.dataset.countdown, now);
      element.textContent = String(Math.max(0, remaining));
      element.parentElement.querySelector('[data-countdown-label]').textContent = remaining < 0 ? '考試日期已過' : remaining === 0 ? '今天考試' : '天後考試';
    });
    if (lessons.length) {
      const progress = document.getElementById('schedule-progress');
      progress.max = lessons.length;
      progress.value = pastLessons;
      document.getElementById('progress-count').textContent = `${pastLessons} / ${lessons.length} 堂日期已過`;
      const stamp = `${now.getFullYear()}/${String(now.getMonth() + 1).padStart(2, '0')}/${String(now.getDate()).padStart(2, '0')}`;
      document.getElementById('today-label').textContent = `今天 ${stamp} · 本週依週一至週日計算`;
    }
  }

  function revealAnchor() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const target = document.getElementById(id);
    if (!target) return;
    let parent = target;
    while (parent) {
      if (parent.tagName === 'DETAILS') parent.open = true;
      parent = parent.parentElement;
    }
    target.scrollIntoView({ block: 'start' });
  }

  function initCompletion() {
    if (!document.getElementById('completion-title')) return;
    // Version 1: 41 security dates, then 55 AI dates, starting 2026-09-21.
    // Date/subject storage keys remain independent of row order and lesson kind.
    const boxes = [...document.querySelectorAll('[data-completion-key]')];
    const status = document.getElementById('completion-status');
    const storageWarning = '此瀏覽器無法儲存進度；請複製進度碼備份，重新整理可能遺失。';
    let storageFailed = false;
    const announce = message => { status.textContent = message + (storageFailed ? ' ' + storageWarning : ''); };

    function readProgress() {
      boxes.forEach(box => {
        try { box.checked = localStorage.getItem(box.dataset.completionKey) === '1'; }
        catch { storageFailed = true; }
      });
      if (storageFailed) announce('');
    }

    function saveProgress(box) {
      try {
        if (box.checked) localStorage.setItem(box.dataset.completionKey, '1');
        else localStorage.removeItem(box.dataset.completionKey);
      } catch { storageFailed = true; }
    }

    function updateCompletion() {
      boxes.forEach(box => box.closest('tr').classList.toggle('is-complete', box.checked));
      for (const [subject, label] of [['security', '資安'], ['ai', 'AI']]) {
        const group = boxes.filter(box => box.closest('tr').dataset.schedule === subject);
        const count = group.filter(box => box.checked).length;
        document.getElementById(`completion-${subject}-count`).textContent = `${label} ${count}/${group.length}`;
        const progress = document.getElementById(`completion-${subject}-progress`);
        progress.max = group.length;
        progress.value = count;
      }
    }

    // Explicit subject/date ordering makes codes stable even if rows are reordered.
    const codeBoxes = [...boxes].sort((a, b) => {
      const rowA = a.closest('tr').dataset, rowB = b.closest('tr').dataset;
      return rowA.schedule === rowB.schedule ? rowA.date.localeCompare(rowB.date) : rowA.schedule === 'security' ? -1 : 1;
    });
    const codePrefix = 'IPAS1-20260921-';
    function encodeProgressCode() {
      let hex = '';
      for (let i = 0; i < codeBoxes.length; i += 4) {
        let bits = 0;
        for (let j = 0; j < 4; j++) if (codeBoxes[i + j]?.checked) bits |= 1 << j;
        hex += bits.toString(16);
      }
      return codePrefix + hex;
    }

    async function copyProgressCode() {
      const code = encodeProgressCode();
      try {
        await navigator.clipboard.writeText(code);
        announce('進度碼已複製，可在另一台裝置貼上。');
      } catch {
        window.prompt('請手動複製此進度碼：', code);
        announce('可從對話框手動複製進度碼。');
      }
    }

    function pasteProgressCode() {
      const input = window.prompt('貼上進度碼（會合併，不會取消已完成項目）：');
      if (input === null) return;
      const code = input.trim();
      if (!/^IPAS1-20260921-[0-9a-f]{24}$/i.test(code)) {
        announce('進度碼無效，請確認已完整複製本期課表的進度碼。');
        return;
      }
      const hex = code.slice(codePrefix.length);
      codeBoxes.forEach((box, i) => {
        if (parseInt(hex[Math.floor(i / 4)], 16) & (1 << (i % 4))) {
          box.checked = true;
          saveProgress(box);
        }
      });
      updateCompletion();
      announce('進度已合併，原本已完成的項目全部保留。');
    }

    function clearProgress() {
      if (!window.confirm('確定清除此裝置的全部完成進度？建議先複製進度碼備份。')) return;
      boxes.forEach(box => { box.checked = false; saveProgress(box); });
      updateCompletion();
      announce('此裝置的完成進度已清除。');
    }

    readProgress();
    updateCompletion();
    boxes.forEach(box => {
      box.disabled = false;
      box.addEventListener('change', () => {
        saveProgress(box);
        updateCompletion();
        announce(storageFailed ? '' : '完成進度已儲存於此裝置。');
      });
    });
    for (const [id, action] of [['copy-progress', copyProgressCode], ['paste-progress', pasteProgressCode], ['clear-progress', clearProgress]]) {
      const button = document.getElementById(id);
      button.disabled = false;
      button.addEventListener('click', action);
    }
    window.addEventListener('storage', event => {
      if (event.key === null || boxes.some(box => box.dataset.completionKey === event.key)) {
        readProgress();
        updateCompletion();
      }
    });
  }

  if (typeof document !== 'undefined') {
    updateSchedule();
    initCompletion();
    // Refresh when a sleeping tab resumes, and across midnight without reloading.
    if (document.querySelector('[data-kind="lesson"]')) {
      setInterval(() => updateSchedule(), 60000);
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden) updateSchedule();
      });
    }
    window.addEventListener('hashchange', revealAnchor);
    document.addEventListener('click', event => {
      const link = event.target.closest('a[href^="#"]');
      if (link && link.hash === location.hash) revealAnchor();
    });
    if (location.hash) revealAnchor();
  }
  // Node's built-in test runner can check calendar boundaries without a browser dependency.
  if (typeof module !== 'undefined') module.exports = { calendarState, initCompletion };
})();
