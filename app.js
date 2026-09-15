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

  if (typeof document !== 'undefined') {
    updateSchedule();
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
  if (typeof module !== 'undefined') module.exports = { calendarState };
})();
