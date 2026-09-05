(() => {
  'use strict';

  const current = document.getElementById('current-editions');
  if (!current) return;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function dateLabel(date) {
    return new Intl.DateTimeFormat('en-US', {
      weekday: 'long', month: 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC'
    }).format(new Date(`${date}T12:00:00Z`));
  }

  function editionCard(kind, entry, duration) {
    const morning = kind === 'morning';
    const accent = morning ? 'gold' : 'blue';
    const card = el('article', `edition ${morning ? 'morning' : 'evening'}`);
    const top = el('div', 'edition-top');
    top.append(el('span', `eyebrow ${accent}`, entry?.label || (morning ? 'Before the open' : 'After the close')));
    const number = el('span', 'edition-number', morning ? '01' : '02');
    number.setAttribute('aria-hidden', 'true');
    top.append(number);
    card.append(top, el('h3', '', entry ? entry.title : morning ? 'The reading.' : 'The song.'));

    if (!entry) {
      card.append(el('p', '', morning
        ? 'A personal reading of the day: what’s happening, what I’m watching, and the questions I’m bringing into the session.'
        : 'A song inspired by the session’s price action, with a reflection on how the day became music.'));
      card.append(el('div', 'edition-footer', morning ? 'No morning entry for this session yet' : 'The closing song is still to come'));
      return card;
    }

    card.append(el('p', '', entry.summary));
    if (entry.paragraphs?.length) {
      const details = el('details');
      details.append(el('summary', '', morning ? 'Read the morning entry' : 'Read the song notes'));
      entry.paragraphs.forEach(paragraph => details.append(el('p', '', paragraph)));
      card.append(details);
    }

    function link(text, url) {
      const a = el('a', 'text-link', text); a.href = url;
      if (url.startsWith('https:')) { a.target = '_blank'; a.rel = 'noreferrer'; }
      return a;
    }
    if (entry.reportUrl) card.append(link('Read the complete research ↗', entry.reportUrl));
    if (entry.mapUrl) card.append(link('Explore the interactive market map ↗', entry.mapUrl));
    if (entry.chart) {
      const figure = el('figure', 'market-chart'); const img = el('img');
      img.src = entry.chart.url; img.alt = entry.chart.alt; img.loading = 'lazy';
      figure.append(img, el('figcaption', '', entry.chart.caption));
      card.append(figure, link('Open chart image ↗', entry.chart.url), link('View source data ↗', entry.chart.dataUrl));
    }
    if (entry.song) {
      const music = el('div', 'reference-song');
      music.append(el('span', 'eyebrow blue', 'Listening selection · existing recording'),el('h4','',`${entry.song.title} — ${entry.song.artist}`),el('p','',entry.song.reason),link('Listen on the official channel ↗',entry.song.url));
      card.append(music);
    }
    if (entry.sources?.length) {
      const sources = el('details'); sources.append(el('summary','','Sources'));
      entry.sources.forEach(source=>sources.append(link(source.label,source.url)));
      card.append(sources);
    }
    if (!morning && entry.audioUrl) {
      const audioUrl = new URL(entry.audioUrl);
      if (audioUrl.protocol !== 'https:' || audioUrl.username || audioUrl.password) throw new Error('Invalid audio link');
      const audio = el('audio');
      audio.controls = true;
      audio.preload = 'metadata';
      audio.src = audioUrl.href;
      audio.setAttribute('aria-label', entry.title);
      const feedback = el('p', 'published-label');
      feedback.setAttribute('role', 'status');
      feedback.hidden = true;
      const unavailable = message => {
        audio.pause();
        audio.hidden = true;
        feedback.textContent = message;
        feedback.hidden = false;
      };
      audio.addEventListener('error', () => unavailable('This song is temporarily unavailable. Please try again later.'));
      audio.addEventListener('loadedmetadata', () => {
        if (!Number.isFinite(audio.duration) || Math.abs(audio.duration - duration) > 1) {
          unavailable('This recording is being updated to match the series duration.');
        }
      });
      audio.addEventListener('play', () => {
        document.querySelectorAll('audio').forEach(other => {
          if (other !== audio) other.pause();
        });
      });
      card.append(audio, feedback);
      const minutes = Math.floor(duration / 60);
      const seconds = String(duration % 60).padStart(2, '0');
      card.append(el('div', 'edition-footer', `${minutes}:${seconds} · One session, one song`));
    } else {
      card.append(el('div', 'edition-footer', morning ? 'The research edition' : 'Closing reflection · reference track'));
    }
    return card;
  }

  function sessionCards(session, duration) {
    const container = el('div', 'editions');
    container.append(editionCard('morning', session.morning, duration), editionCard('closing', session.closing, duration));
    return container;
  }

  fetch('content/editions.json', { cache: 'no-cache' })
    .then(response => {
      if (!response.ok) throw new Error('Journal unavailable');
      return response.json();
    })
    .then(data => {
      if (!Array.isArray(data.sessions)) throw new Error('Invalid journal');
      if (!data.sessions.length) return;
      const sessions = [...data.sessions].sort((a, b) => b.date.localeCompare(a.date));
      const featured = sessionCards(sessions[0], data.songDurationSeconds);
      const archive = document.createDocumentFragment();
      sessions.slice(1).forEach(session => {
        const item = el('details', 'past-session');
        item.id = 'session-' + session.date;
        if(location.hash === '#' + item.id) item.open = true;
        item.append(el('summary', '', dateLabel(session.date)), sessionCards(session, data.songDurationSeconds));
        archive.append(item);
      });
      current.replaceChildren(...featured.children);
      const date = document.getElementById('session-date');
      date.textContent = dateLabel(sessions[0].date);
      date.hidden = false;
      document.getElementById('session-archive').replaceChildren(archive);
      document.getElementById('past-sessions').hidden = sessions.length < 2;
    })
    .catch(() => {
      const message = el('p', 'session-date', 'The daily journal could not load. Please refresh to try again. The opening essay is available below.');
      message.setAttribute('role', 'status');
      current.before(message);
      current.hidden = true;
    });
})();
