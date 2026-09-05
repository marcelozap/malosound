(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const clamp = (n, low, high) => Math.max(low, Math.min(high, n));
  const songClock = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
  const marketClock = minutes => `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(Math.floor(minutes % 60)).padStart(2, '0')} ET`;

  function validate(data) {
    if (data.durationSeconds !== 195 || data.marketStartMinutes !== 570 || data.marketDurationMinutes !== 390 ||
        data.width !== 1000 || data.height !== 340 || !Array.isArray(data.points) || data.points.length !== 391 ||
        !data.points.every((p, i) => p.minute === i && Number.isFinite(p.x) && Number.isFinite(p.y) && p.x >= 0 && p.x <= 1000 && p.y >= 0 && p.y <= 340) ||
        !Array.isArray(data.gaps) || !data.gaps.every(g => Number.isInteger(g.startMinute) && Number.isInteger(g.endMinute) && g.startMinute >= 0 && g.endMinute > g.startMinute && g.endMinute <= 390)) {
      throw new Error('Invalid session timeline');
    }
    return data;
  }

  // Interpolate the already-drawn line between minute boundaries, never a
  // missing source interval. This describes the artwork, not inferred ticks.
  function position(data, seconds) {
    const minute = clamp(seconds, 0, data.durationSeconds) * (data.marketDurationMinutes / data.durationSeconds);
    const left = Math.floor(minute), right = Math.min(left + 1, data.points.length - 1);
    const fraction = minute - left;
    const a = data.points[left], b = data.points[right];
    const gap = data.gaps.some(g => minute >= g.startMinute && minute < g.endMinute);
    return { minute, x: a.x + (b.x - a.x) * fraction, y: gap ? null : a.y + (b.y - a.y) * fraction, gap };
  }

  function mount(article) {
    const figure = article.querySelector('.session-drawing[data-timeline-src]');
    const stage = figure?.querySelector('.drawing-stage');
    const audio = article.querySelector('audio');
    if (!figure || !stage || !audio) return () => {};
    const abort = new AbortController();
    let disposed = false, frame = 0;
    const cleanups = [];
    const listen = (node, event, callback) => {
      node.addEventListener(event, callback);
      cleanups.push(() => node.removeEventListener(event, callback));
    };
    const stop = () => { if (frame) cancelAnimationFrame(frame); frame = 0; };
    const cleanup = () => { disposed = true; abort.abort(); stop(); cleanups.splice(0).forEach(f => f()); article.classList.remove('is-playing'); };
    const url = new URL(figure.dataset.timelineSrc, location.href);
    if (url.origin !== location.origin) return cleanup;

    fetch(url.href, { signal: abort.signal }).then(r => {
      if (!r.ok) throw new Error('Timeline unavailable');
      return r.json();
    }).then(validate).then(data => {
      if (disposed) return;
      const make = (tag, cls, text) => {
        const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n;
      };
      const svg = document.createElementNS(NS, 'svg');
      svg.setAttribute('class', 'line-playhead'); svg.setAttribute('viewBox', '0 0 1000 340'); svg.setAttribute('aria-hidden', 'true');
      function shape(tag, attributes) {
        const n = document.createElementNS(NS, tag); Object.entries(attributes).forEach(([k, v]) => n.setAttribute(k, v)); svg.append(n); return n;
      }
      const beam = shape('line', { y1: 18, y2: 322, class: 'playhead-beam' });
      const halo = shape('circle', { r: 12, class: 'playhead-halo' });
      const dot = shape('circle', { r: 4.5, class: 'playhead-dot' });
      stage.append(svg);
      const controls = make('div', 'line-controls');
      const toggle = make('button', 'line-toggle', '▶'); toggle.type = 'button';
      const slider = make('input', 'line-seek'); slider.type = 'range'; slider.min = '0'; slider.max = String(data.durationSeconds); slider.step = '0.1';
      slider.setAttribute('aria-label', 'Song position');
      const time = make('span', 'line-song-clock'); time.setAttribute('aria-hidden', 'true');
      controls.append(toggle, slider, time);
      const readout = make('p', 'line-readout');
      const clock = make('span', 'line-market-clock');
      const note = make('span', 'line-gap-label');
      readout.append(clock, note);
      const feedback = make('p', 'line-feedback'); feedback.hidden = true; feedback.setAttribute('role', 'status');
      figure.append(controls, readout, feedback);
      cleanups.push(() => { svg.remove(); controls.remove(); readout.remove(); feedback.remove(); });
      const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
      let invalid = false, lastSecond = -1, lastGap = null;
      const validDuration = () => Number.isFinite(audio.duration) && Math.abs(audio.duration - data.durationSeconds) <= 1;
      function update() {
        if (disposed) return;
        const seconds = clamp(Number.isFinite(audio.currentTime) ? audio.currentTime : 0, 0, data.durationSeconds);
        const p = position(data, seconds);
        const ready = validDuration() && !invalid && !audio.error;
        article.classList.toggle('is-playing', ready && !audio.paused && !audio.ended && audio.readyState >= 3);
        toggle.disabled = invalid || !!audio.error;
        slider.disabled = !ready;
        svg.style.visibility = ready ? 'visible' : 'hidden';
        beam.setAttribute('x1', p.x); beam.setAttribute('x2', p.x);
        [dot, halo].forEach(n => {
          n.style.display = p.gap ? 'none' : '';
          if (!p.gap) { n.setAttribute('cx', p.x); n.setAttribute('cy', p.y); }
        });
        beam.setAttribute('class', p.gap ? 'playhead-beam is-gap' : 'playhead-beam');
        slider.value = seconds;
        slider.setAttribute('aria-valuetext', `${songClock(seconds)} of ${songClock(data.durationSeconds)}; ${marketClock(data.marketStartMinutes + p.minute)}${p.gap ? '; missing source data' : ''}`);
        time.textContent = `${songClock(seconds)} / ${songClock(data.durationSeconds)}`;
        clock.textContent = marketClock(data.marketStartMinutes + p.minute);
        if (Math.floor(seconds) !== lastSecond || p.gap !== lastGap) {
          note.textContent = p.gap ? 'Source gap' : '';
          lastSecond = Math.floor(seconds); lastGap = p.gap;
        }
        toggle.textContent = audio.paused || audio.ended ? '▶' : 'Ⅱ';
        toggle.setAttribute('aria-label', `${audio.paused || audio.ended ? 'Play' : 'Pause'} this session’s song`);
      }
      function tick() {
        frame = 0; update();
        if (!disposed && !audio.paused && !audio.ended && !motion.matches && !document.hidden && !invalid) frame = requestAnimationFrame(tick);
      }
      function start() { stop(); update(); if (!audio.paused && !audio.ended && !motion.matches && !document.hidden && !invalid) frame = requestAnimationFrame(tick); }
      function checkDuration() {
        if (Number.isFinite(audio.duration) && !validDuration()) {
          invalid = true; stop(); audio.pause(); feedback.hidden = false; feedback.textContent = 'This recording’s timing is being checked. Please try again later.';
        }
        update();
      }
      listen(toggle, 'click', async () => {
        if (!audio.paused && !audio.ended) { audio.pause(); return; }
        if (audio.ended) audio.currentTime = 0;
        feedback.hidden = true;
        try { await audio.play(); } catch (error) {
          if (!disposed && error.name !== 'AbortError') { feedback.textContent = 'Playback could not start. Try the audio controls below.'; feedback.hidden = false; }
        }
      });
      listen(slider, 'input', () => { if (validDuration() && !invalid) { audio.currentTime = clamp(Number(slider.value), 0, data.durationSeconds); update(); } });
      ['timeupdate','seeking','seeked','ratechange'].forEach(event => listen(audio, event, update));
      listen(audio, 'play', update); listen(audio, 'playing', start);
      ['pause','ended','waiting','stalled','emptied'].forEach(event => listen(audio, event, () => { stop(); update(); }));
      ['loadedmetadata','durationchange'].forEach(event => listen(audio, event, checkDuration));
      listen(audio, 'error', () => { invalid = true; stop(); update(); feedback.textContent = 'The recording is temporarily unavailable. Please try again later.'; feedback.hidden = false; });
      listen(document, 'visibilitychange', start);
      listen(motion, 'change', start);
      checkDuration(); start();
    }).catch(error => {
      if (disposed || error.name === 'AbortError') return;
      const message = document.createElement('p'); message.className = 'line-feedback';
      message.textContent = 'The moving line is temporarily unavailable. You can still listen below.';
      figure.append(message); cleanups.push(() => message.remove());
    });
    return cleanup;
  }
  window.MaloSoundPlayhead = { mount };
  // The homepage mounts when the selected entry changes; static reports mount here.
  document.querySelectorAll('.standalone-journal .day-entry').forEach(article => {
    const cleanup = mount(article);
    window.addEventListener('pagehide', event => { if (!event.persisted) cleanup(); }, { once: true });
  });
})();
