(() => {
  'use strict';
  const root = document.getElementById('current-editions');
  if (!root) return;
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text) n.textContent = text;
    return n;
  };
  const date = value => new Date(`${value}T12:00:00Z`);
  const format = (value, options) => new Intl.DateTimeFormat('en-US', { ...options, timeZone: 'UTC' }).format(date(value));
  const fullDate = value => format(value, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
  const shortDate = value => format(value, { month: 'long', day: 'numeric' });
  const miniDate = value => format(value, { month: 'short', day: 'numeric' });
  // Mirrors EXECUTION in tools/trade_journal.py; keep both in step.
  const EXECUTION_COLORS = { good:'#58dfa4', misplayed:'#ff7188', sat_out:'#e5b657', unreviewed:'#50b8f5' };
  const EXECUTION_LABELS = { good:'Played well', misplayed:'Misplayed', sat_out:'Sat out', unreviewed:'Not reviewed' };
  function link(text, url) {
    const a = el('a', 'text-link', text);
    const u = new URL(url, location.href);
    if (!['http:', 'https:'].includes(u.protocol)) throw new Error('Unsafe link');
    a.href = url;
    if (u.origin !== location.origin) { a.target = '_blank'; a.rel = 'noreferrer'; }
    return a;
  }
  function sources(entry, label = 'Notes + sources') {
    const details = el('details', 'journal-details');
    details.append(el('summary', '', label));
    if (entry.preparedAt) details.append(el('p', 'publication-time', `Prepared / added: ${entry.preparedAt}`));
    (entry.sources || []).forEach(s => details.append(link(s.label, s.url)));
    return details;
  }
  function section(number, label, accent = 'gold') {
    const s = el('section', `journal-chapter chapter-${number}`);
    const head = el('div', 'chapter-label');
    head.append(el('span', `chapter-number ${accent}`, number), el('h3', `eyebrow ${accent}`, label));
    s.append(head);
    return s;
  }
  function player(entry, duration) {
    const wrap = el('div', 'journal-player');
    const audio = el('audio'); audio.controls = true; audio.preload = 'metadata';
    const url = new URL(entry.audioUrl, location.href);
    const localAudio = url.origin === location.origin && /^\/assets\/audio\/[a-f0-9]{64}\.mp3$/.test(url.pathname);
    if ((!localAudio && url.protocol !== 'https:') || url.username || url.password) throw new Error('Invalid audio URL');
    audio.src = url.href; audio.setAttribute('aria-label', `Listen to ${entry.title}`);
    const status = el('p', 'song-status'); status.hidden = true; status.setAttribute('role', 'status');
    const retry = el('button', 'text-link', 'Retry recording'); retry.type = 'button'; retry.hidden = true;
    function unavailable(message) { audio.pause(); audio.hidden = true; status.hidden = false; status.textContent = message; retry.hidden = false; }
    retry.addEventListener('click', () => { audio.hidden = false; status.hidden = true; retry.hidden = true; audio.load(); });
    audio.addEventListener('error', () => unavailable('The recording could not load. Try loading it again.'));
    audio.addEventListener('loadedmetadata', () => {
      if (!Number.isFinite(audio.duration) || Math.abs(audio.duration - duration) > 1) unavailable('This recording is being checked. Please try again later.');
    });
    audio.addEventListener('play', () => document.querySelectorAll('audio').forEach(a => { if (a !== audio) a.pause(); }));
    wrap.append(audio, status, retry);
    return wrap;
  }
  function renderEntry(session, index, duration) {
    const article = el('article', 'day-entry');
    const performance = session.performance || { outcome: 'unrecorded', label: 'Unrecorded', glyph: '—', executionSections: [] };
    article.dataset.tradeResult = performance.outcome;
    article.id = `session-${session.date}`;
    const song = session.originalSong || session.closing;
    const chart = session.lineChart;
    const sessionHours = chart?.sessionHours || '9:30 a.m.–4:00 p.m. ET';
    const header = el('header', 'day-heading session-cover');
    const aura = el('div', 'cover-aura'); aura.setAttribute('aria-hidden', 'true');
    const orbit = el('div', 'cover-orbit'); orbit.setAttribute('aria-hidden', 'true');
    const copy = el('div', 'cover-copy');
    copy.append(el('span', 'eyebrow gold', `${shortDate(session.date)} · ${session.date.slice(0, 4)}`));
    const h = el('h2', '', song?.audioUrl ? (song.title || shortDate(session.date)) : (session.title || shortDate(session.date)));
    h.id = 'selected-day-heading';
    article.setAttribute('aria-labelledby', h.id);
    copy.append(h, el('p', 'day-subtitle', `SPY · ${song?.audioUrl ? 'SESSION CHART + RECORDING' : 'SESSION CHART'}`));
    header.append(aura, orbit, copy);
    article.append(header);

    const drawing = section('01', 'Market chart');
    const tradeStrip = el('div', 'trade-strip');
    const result = el('span', 'trade-result');
    const glyph = el('span', '', performance.glyph); glyph.setAttribute('aria-hidden', 'true');
    result.append(glyph, el('span', '', `My day · ${performance.label}`));
    tradeStrip.append(result);
    drawing.append(tradeStrip);
    if (chart) {
      const figure = el('figure', 'session-drawing');
      if (chart.playheadUrl) figure.dataset.timelineSrc = chart.playheadUrl;
      const stage = el('div', 'drawing-stage');
      const img = el('img'); img.src = chart.url; img.alt = chart.alt; img.width = 1000; img.height = 340;
      const caption = el('figcaption', 'drawing-times');
      caption.append(el('span', '', chart.startLabel || '09:30 ET'), el('span', '', chart.endLabel || '16:00 ET'));
      stage.append(img); figure.append(stage, caption); drawing.append(figure);
      if (chart.gapNote) drawing.append(el('p', 'data-gap', chart.gapShort || chart.gapNote));
      const method = el('details', 'journal-details'); method.append(el('summary', '', 'Behind the line'), el('p', '', chart.caption));
      if (chart.gapNote) method.append(el('p', '', chart.gapNote));
      (chart.notes || []).forEach(p => method.append(el('p', '', p)));
      method.append(link('View the source observations ↗', chart.dataUrl));
      drawing.append(method);
      const exec = performance.executionSections || [];
      const keys = ['unreviewed'].concat(['good','misplayed','sat_out'].filter(k => exec.some(x => x.execution === k)));
      const legend = el('div', 'exec-legend'); legend.setAttribute('role','img');
      legend.setAttribute('aria-label','Execution color key');
      keys.forEach(k => { const key = el('span','exec-key'); const swatch = el('i');
        swatch.style.background = EXECUTION_COLORS[k]; key.append(swatch, document.createTextNode(EXECUTION_LABELS[k])); legend.append(key); });
      drawing.append(legend);
    } else {
      drawing.append(el('p', '', session.closing?.marketClosed ? 'Closed session; no line.' : 'No line available yet.'));
    }
    const recordNotes = el('details', 'journal-details'); recordNotes.append(el('summary', '', 'Execution'));
    if (!(performance.executionSections || []).length) {
      recordNotes.append(el('p', '', 'No execution review yet.'));
    }
    (performance.executionSections || []).forEach(x => recordNotes.append(el('p', '', `${x.startTime}–${x.endTime} ET · ${EXECUTION_LABELS[x.execution]}${x.note ? ' · ' + x.note : ''}`)));
    if (performance.executionAssessedAt) recordNotes.append(el('p', '', `Execution reviewed at ${performance.executionAssessedAt}, after the close.`));
    if (performance.sourceLabel) recordNotes.append(el('p', '', `${performance.sourceLabel} · Net result recorded ${performance.recordedAt}.`));
    drawing.append(recordNotes);
    article.append(drawing);

    const music = section('02', 'Optional recording', 'blue');
    if (song?.audioUrl) {
      music.append(el('p', 'eyebrow blue', 'Original instrumental'));
      music.append(player(song, duration));
      const meta = el('div', 'song-specs');
      ['03:15', `${song.tempoBpm || 80} BPM`, 'SPY → SOUND'].forEach(t => meta.append(el('span', '', t)));
      music.append(meta);
      const notes = sources(song, 'About the song');
      notes.append(el('p', '', `SPY’s ${shortDate(session.date)}, ${sessionHours} session, compressed into a 3:15 instrumental.`));
      if (song.thesis) notes.append(el('p', '', song.thesis));
      if (song.summary) notes.append(el('p', '', song.summary));
      (song.paragraphs || []).forEach(p => notes.append(el('p', '', p)));
      if (song.reportUrl) notes.append(link('Read the complete session ↗', song.reportUrl));
      if (song.midiUrl) notes.append(link('Download the editable MIDI ↗', song.midiUrl));
      music.append(notes);
    } else {
      music.append(el('p', '', song?.marketClosed ? 'Closed session; chart-only.' : song?.songPending ? 'Recording pending.' : 'Chart-only session.'));
    }
    article.append(music);

    const morning = session.preOpen || session.morning;
    const pre = section('03', 'Context');
    const morningFold = el('details', 'morning-fold');
    morningFold.append(el('summary', '', 'Morning notes'));
    if (morning) {
      morningFold.append(el('p', 'entry-status', morning.label), el('h4', '', morning.title));
      const refs = sources(morning);
      refs.append(el('p', 'chapter-deck', morning.summary));
      (morning.paragraphs || []).forEach(p => refs.append(el('p', '', p)));
      if (morning.reportUrl) refs.append(link('Read the full morning research ↗', morning.reportUrl));
      if (morning.mapUrl) refs.append(link('Explore the market map ↗', morning.mapUrl));
      morningFold.append(refs);
    } else morningFold.append(el('p', '', 'No morning note for this date.'));
    pre.append(morningFold);
    article.append(pre);
    return article;
  }
  // The calendar holds only a small index; a day's full entry is fetched when it
  // is opened and then cached, so an archive of many months costs one small file.
  const detailCache = new Map();
  function loadDay(day, entry) {
    if (detailCache.has(day)) return Promise.resolve(detailCache.get(day));
    if (entry && entry.session) { detailCache.set(day, entry.session); return Promise.resolve(entry.session); }
    return fetch(entry.detailUrl, { cache: 'no-cache' })
      .then(r => { if (!r.ok) throw new Error('Unavailable'); return r.json(); })
      .then(session => { detailCache.set(day, session); return session; });
  }
  fetch('/content/journal-index.json', { cache: 'no-cache' })
    .then(r => { if (!r.ok) throw new Error('Unavailable'); return r.json(); })
    .catch(() => fetch('/content/editions.json', { cache: 'no-cache' })
      .then(r => { if (!r.ok) throw new Error('Unavailable'); return r.json(); })
      .then(full => ({ seriesStartDate: full.seriesStartDate, songDurationSeconds: full.songDurationSeconds,
                       days: [...(full.sessions || [])].map(s => ({ date: s.date, session: s,
                         outcome: (s.performance || {}).outcome || 'unrecorded',
                         outcomeLabel: (s.performance || {}).label || 'Unrecorded' })) })))
    .then(data => {
    if (!Array.isArray(data.days) || !data.days.length) throw new Error('No entries');
    const sessions = [...data.days].sort((a,b) => a.date.localeCompare(b.date));
    const byDate = new Map(sessions.map(s => [s.date,s]));
    const hashDate = () => location.hash.match(/^#session-(\d{4}-\d{2}-\d{2})$/)?.[1];
    let selected = byDate.has(hashDate()) ? hashDate() : sessions.at(-1).date;
    let month = selected.slice(0,7);
    const sidebar = el('aside', 'calendar-panel'); sidebar.setAttribute('aria-label', 'Journal calendar');
    const art = el('div', 'calendar-art'); art.setAttribute('aria-hidden', 'true'); art.append(el('span', '', 'SIGNAL / SOUND'));
    const calendar = el('div', 'calendar'); const stage = el('div', 'selected-session');
    const announced = el('p', 'sr-only'); announced.setAttribute('role', 'status'); announced.setAttribute('aria-live', 'polite');
    sidebar.append(art, calendar); root.replaceChildren(sidebar, stage, announced);
    let detachPlayhead = () => {};
    let pending = 0;
    function choose(day, updateHash) {
      const entry = byDate.get(day);
      if (!entry) return;
      detachPlayhead();
      stage.querySelectorAll('audio').forEach(a => a.pause()); selected = day; month = day.slice(0,7);
      drawCalendar();
      if (updateHash) history.replaceState(null, '', `#session-${day}`);
      const token = ++pending;
      if (!detailCache.has(day)) {
        stage.replaceChildren(el('p', 'calendar-note', `Opening ${fullDate(day)}…`));
      }
      loadDay(day, entry).then(session => {
        if (token !== pending) return;   // a later click already won
        stage.replaceChildren(renderEntry(session, sessions.findIndex(s => s.date === day), data.songDurationSeconds));
        detachPlayhead = window.MaloSoundPlayhead?.mount(stage.querySelector('.day-entry')) || (() => {});
        announced.textContent = `Journal entry for ${fullDate(day)} selected.`;
      }).catch(() => {
        if (token !== pending) return;
        stage.replaceChildren(el('p', 'calendar-note', `That entry could not be loaded. Try again, or pick another date.`));
        announced.textContent = `Journal entry for ${fullDate(day)} could not be loaded.`;
      });
    }
    function moveMonth(amount) {
      const d = date(`${month}-01`); d.setUTCMonth(d.getUTCMonth() + amount);
      month = d.toISOString().slice(0,7); drawCalendar();
      calendar.querySelector(amount < 0 ? '.month-prev' : '.month-next')?.focus();
    }
    function drawCalendar() {
      const head = el('div', 'calendar-head');
      const prev = el('button', 'month-prev', '←'); prev.type = 'button'; prev.setAttribute('aria-label', 'Previous month');
      const next = el('button', 'month-next', '→'); next.type = 'button'; next.setAttribute('aria-label', 'Next month');
      // The floor is the earlier of the declared start and the oldest entry, so
      // a day added before the series officially began is still reachable.
      const oldest = sessions[0].date.slice(0,7);
      const declared = (data.seriesStartDate || '').slice(0,7);
      prev.disabled = month <= (declared && declared < oldest ? declared : oldest);
      next.disabled = month >= sessions.at(-1).date.slice(0,7);
      prev.addEventListener('click', () => moveMonth(-1)); next.addEventListener('click', () => moveMonth(1));
      const title = el('h3','',format(`${month}-01`,{month:'long',year:'numeric'})); head.append(prev,title,next);
      const grid = el('div', 'calendar-grid'); grid.setAttribute('aria-label', title.textContent);
      ['M','T','W','T','F','S','S'].forEach(d => grid.append(el('span','weekday',d)));
      const first = date(`${month}-01`); const blanks = (first.getUTCDay()+6)%7;
      const count = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth()+1,0)).getUTCDate();
      for (let i=0;i<blanks;i++) grid.append(el('span','calendar-blank'));
      for (let day=1;day<=count;day++) {
        const key = `${month}-${String(day).padStart(2,'0')}`; const available = byDate.has(key);
        const b = el('button', `calendar-day${available ? ' has-entry' : ''}${key === selected ? ' is-selected' : ''}`, String(day));
        const row = byDate.get(key);
        const dayResult = row && (row.performance || (row.outcome ? { outcome: row.outcome, label: row.outcomeLabel } : null));
        if (dayResult) b.dataset.tradeResult = dayResult.outcome;
        b.type = 'button'; b.disabled = !available;
        b.setAttribute('aria-label', `${fullDate(key)}${available ? ', open journal entry' : ', no journal entry'}${dayResult ? `, my trading result: ${dayResult.label}` : ''}`);
        if (available) b.setAttribute('aria-pressed', String(key === selected));
        b.addEventListener('click', () => { choose(key,true); calendar.querySelector(`[data-date="${key}"]`)?.focus(); });
        b.dataset.date = key; grid.append(b);
      }
      const history = el('div', 'calendar-history');
      history.append(el('span', 'eyebrow gold', 'All sessions'));
      const list = el('div', 'calendar-history-list');
      for (const row of [...sessions].reverse()) {
        const b = el('button', `calendar-history-item${row.date === selected ? ' is-selected' : ''}${row.hasSong ? ' has-song' : ''}`, miniDate(row.date));
        b.type = 'button'; b.dataset.date = row.date;
        b.setAttribute('aria-label', `${fullDate(row.date)}${row.hasSong ? ', has recording' : ', chart-only'}`);
        b.addEventListener('click', () => { choose(row.date, true); });
        list.append(b);
      }
      history.append(list);
      const legend = el('div', 'calendar-legend'); legend.append(el('span','legend-dot'),el('span','','Sessions'));
      calendar.replaceChildren(el('span','eyebrow gold','Choose a session'),head,grid,history,legend);
    }
    window.addEventListener('hashchange', () => { if (byDate.has(hashDate())) choose(hashDate(),false); });
    choose(selected,false);
    if (byDate.has(hashDate())) stage.scrollIntoView({ block:'start', behavior:'instant' });
  }).catch(() => {
    root.replaceChildren(el('p', 'publishing-note', 'The journal could not load. Please refresh to try again.'), link('Read September 3 ↗','/reports/2026-09-03-spy-song.html'), link('Read September 4 ↗','/reports/2026-09-04-spy-song.html'));
  });
})();
