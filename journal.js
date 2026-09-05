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
  function link(text, url) {
    const a = el('a', 'text-link', text);
    const u = new URL(url, location.href);
    if (!['http:', 'https:'].includes(u.protocol)) throw new Error('Unsafe link');
    a.href = url;
    if (u.origin !== location.origin) { a.target = '_blank'; a.rel = 'noreferrer'; }
    return a;
  }
  function sources(entry, label = 'Sources & publication notes') {
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
    const url = new URL(entry.audioUrl);
    if (url.protocol !== 'https:' || url.username || url.password) throw new Error('Invalid audio URL');
    audio.src = url.href; audio.setAttribute('aria-label', `Listen to ${entry.title}`);
    const status = el('p', 'song-status'); status.hidden = true; status.setAttribute('role', 'status');
    function unavailable(message) { audio.pause(); audio.hidden = true; status.hidden = false; status.textContent = message; }
    audio.addEventListener('error', () => unavailable('The recording is temporarily unavailable. Please try again later.'));
    audio.addEventListener('loadedmetadata', () => {
      if (!Number.isFinite(audio.duration) || Math.abs(audio.duration - duration) > 1) unavailable('This recording is being checked. Please try again later.');
    });
    audio.addEventListener('play', () => document.querySelectorAll('audio').forEach(a => { if (a !== audio) a.pause(); }));
    wrap.append(audio, status);
    return wrap;
  }
  function renderEntry(session, index, duration) {
    const article = el('article', 'day-entry');
    article.id = `session-${session.date}`;
    const header = el('header', 'day-heading');
    header.append(el('span', 'eyebrow gold', `Journal / ${String(index + 1).padStart(3, '0')}`));
    const h = el('h2', '', shortDate(session.date)); h.id = 'selected-day-heading';
    article.setAttribute('aria-labelledby', h.id);
    header.append(h, el('p', 'day-subtitle', `${format(session.date, { weekday: 'long', year: 'numeric' })} · SPY · New York`));
    article.append(header);
    const morning = session.preOpen || session.morning;
    const pre = section('01', 'Before the open');
    if (morning) {
      pre.append(el('p', 'entry-status', morning.label), el('h4', '', morning.title), el('p', 'chapter-deck', morning.summary));
      (morning.paragraphs || []).forEach(p => pre.append(el('p', '', p)));
      const refs = sources(morning);
      if (morning.reportUrl) refs.append(link('Read the full morning research ↗', morning.reportUrl));
      if (morning.mapUrl) refs.append(link('Explore the market map ↗', morning.mapUrl));
      pre.append(refs);
    } else pre.append(el('h4', '', 'An open page.'), el('p', '', 'No before-open note was published for this date. The space stays open in the record.'));
    article.append(pre);
    const song = session.originalSong || session.closing;
    const chart = session.lineChart;
    const drawing = section('02', 'The line the day drew');
    drawing.append(el('h4', '', 'One session. One gesture.'));
    if (chart) {
      const figure = el('figure', 'session-drawing');
      if (chart.playheadUrl) figure.dataset.timelineSrc = chart.playheadUrl;
      const stage = el('div', 'drawing-stage');
      const img = el('img'); img.src = chart.url; img.alt = chart.alt; img.width = 1000; img.height = 340;
      const caption = el('figcaption', 'drawing-times');
      caption.append(el('span', '', chart.startLabel || '09:30 ET'), el('span', '', chart.endLabel || '16:00 ET'));
      stage.append(img); figure.append(stage, caption); drawing.append(figure, el('p', 'drawing-caption', chart.caption));
      if (chart.gapNote) drawing.append(el('p', 'data-gap', chart.gapNote));
      const method = el('details', 'journal-details'); method.append(el('summary', '', 'Behind the line'));
      (chart.notes || []).forEach(p => method.append(el('p', '', p)));
      method.append(link('View the source observations ↗', chart.dataUrl));
      drawing.append(method);
    } else drawing.append(el('p', '', session.closing?.marketClosed ? 'The market was closed. No session line was drawn.' : 'The line appears here after the session data is checked.'));
    article.append(drawing);
    const music = section('03', 'The day, in another key', 'blue');
    if (song?.audioUrl) {
      music.append(el('p', 'eyebrow blue', 'Original MaloSound instrumental'), el('h4', 'song-title', song.title));
      const sessionHours = chart?.sessionHours || '9:30 a.m.–4:00 p.m. ET';
      music.append(el('p', 'chapter-deck', `SPY’s ${shortDate(session.date)}, ${sessionHours} session, compressed into a 3:15 instrumental.`));
      music.append(player(song, duration));
      const meta = el('div', 'song-specs');
      ['03:15', `${song.tempoBpm || 80} BPM`, 'SPY → SOUND'].forEach(t => meta.append(el('span', '', t)));
      music.append(meta);
      if (song.thesis) music.append(el('p', '', song.thesis));
      const notes = sources(song, 'How the day became music'); notes.append(el('p', '', song.summary));
      (song.paragraphs || []).forEach(p => notes.append(el('p', '', p)));
      if (song.reportUrl) notes.append(link('Read the complete session ↗', song.reportUrl));
      if (song.midiUrl) notes.append(link('Download the editable MIDI ↗', song.midiUrl));
      music.append(notes);
    } else music.append(el('h4', '', song?.marketClosed ? 'A day of rest.' : 'The sound is still to come.'), el('p', '', song?.marketClosed ? 'No market session, no session song.' : 'The original song will appear here when the recording is ready.'));
    article.append(music);
    const earlier = [session.preOpen && session.morning, session.originalSong && session.closing].filter(Boolean);
    if (earlier.length) {
      const history = el('details', 'journal-details earlier-notes'); history.append(el('summary', '', 'Earlier notes from this date'));
      earlier.forEach(e => { history.append(el('h4', '', e.title), el('p', '', e.label), el('p', '', e.summary)); if(e.reportUrl) history.append(link('Read the original entry ↗',e.reportUrl)); });
      article.append(history);
    }
    return article;
  }
  fetch('/content/editions.json', { cache: 'no-cache' }).then(r => { if (!r.ok) throw new Error('Unavailable'); return r.json(); }).then(data => {
    if (!Array.isArray(data.sessions) || !data.sessions.length) throw new Error('No entries');
    const sessions = [...data.sessions].sort((a,b) => a.date.localeCompare(b.date));
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
    function choose(day, updateHash) {
      if (!byDate.has(day)) return;
      detachPlayhead();
      stage.querySelectorAll('audio').forEach(a => a.pause()); selected = day; month = day.slice(0,7);
      stage.replaceChildren(renderEntry(byDate.get(day), sessions.findIndex(s => s.date === day), data.songDurationSeconds));
      detachPlayhead = window.MaloSoundPlayhead?.mount(stage.querySelector('.day-entry')) || (() => {});
      drawCalendar();
      if (updateHash) history.replaceState(null, '', `#session-${day}`);
      announced.textContent = `Journal entry for ${fullDate(day)} selected.`;
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
      prev.disabled = month <= (data.seriesStartDate || sessions[0].date).slice(0,7);
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
        b.type = 'button'; b.disabled = !available;
        b.setAttribute('aria-label', `${fullDate(key)}${available ? ', open journal entry' : ', no journal entry'}`);
        if (available) b.setAttribute('aria-pressed', String(key === selected));
        b.addEventListener('click', () => { choose(key,true); calendar.querySelector(`[data-date="${key}"]`)?.focus(); });
        b.dataset.date = key; grid.append(b);
      }
      const legend = el('div', 'calendar-legend'); legend.append(el('span','legend-dot'),el('span','','A day with a story. Click to open.'));
      calendar.replaceChildren(el('span','eyebrow gold','Choose a session'),head,grid,legend);
      calendar.append(el('p','calendar-note', 'The journal begins September 3, 2026. Each entry keeps the morning thought, the observed line, and its song together.'));
    }
    window.addEventListener('hashchange', () => { if (byDate.has(hashDate())) choose(hashDate(),false); });
    choose(selected,false);
    if (byDate.has(hashDate())) stage.scrollIntoView({ block:'start', behavior:'instant' });
  }).catch(() => {
    root.replaceChildren(el('p', 'publishing-note', 'The journal could not load. Please refresh to try again.'), link('Read September 3 ↗','/reports/2026-09-03-spy-song.html'), link('Read September 4 ↗','/reports/2026-09-04-spy-song.html'));
  });
})();
