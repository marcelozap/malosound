const library = document.getElementById('library');
const main = document.querySelector('main');

if (main) {
  const panel = document.createElement('details');
  panel.className = 'background-listening';
  panel.setAttribute('aria-labelledby', 'listening-title');
  panel.innerHTML = `
    <summary class="background-listening__summary"><span>Moonlight</span><span id="listening-indicator">Background music</span></summary>
    <div class="background-listening__body">
    <div class="background-listening__credit">
      <p class="background-listening__label">Background listening</p>
      <h2 id="listening-title">Moonlight Sonata / III. Presto</h2>
      <p>Beethoven / Paul Pitman, piano
        <a href="https://commons.wikimedia.org/wiki/File:Moonlight_Sonata_Presto.ogg" target="_blank" rel="noopener noreferrer">Recording credits</a>
      </p>
    </div>
    <audio controls loop preload="none" aria-label="Background music: Moonlight Sonata, third movement, performed by Paul Pitman" src="/assets/beat-room/moonlight-presto-paul-pitman.mp3"></audio>
    <label class="background-listening__layer" ${library ? '' : 'hidden'}><input id="listening-layer" type="checkbox" aria-describedby="listening-status"> Layer with beat</label>
    <p id="listening-status" class="background-listening__status" role="status"></p>
    </div>
  `;
  main.after(panel);
  document.body.classList.add('has-background-listening');

  const audio = panel.querySelector('audio');
  const layer = panel.querySelector('#listening-layer');
  const message = panel.querySelector('[role="status"]');
  const indicator = panel.querySelector('#listening-indicator');
  const beatButton = document.getElementById('play');
  const instrumentButton = document.getElementById('listen');
  const transportButton = beatButton || instrumentButton;
  const defaultHint = library ? 'Optional loop. Pauses when you make a beat.' : 'Optional loop. Pauses for the instrument soundtrack.';
  const pauseHint = library ? 'Paused for your beat.' : 'Paused for the instrument.';
  let handingOver = false;
  audio.volume = 0.18;
  message.textContent = defaultHint;

  function pauseListening(reason) {
    if (handingOver || audio.paused) return;
    audio.pause();
    message.textContent = reason;
  }

  for (const [id, reason] of [
    ['play', 'Paused for your beat.'],
    ['listen', 'Paused for the instrument.'],
    ['record', 'Paused for recording.'],
    ['export', 'Paused for export.'],
  ]) {
    document.getElementById(id)?.addEventListener('click', () => {
      if (id !== 'play' || !layer.checked) pauseListening(reason);
    }, true);
  }

  audio.addEventListener('play', () => {
    const recordingOrExporting = document.querySelector('#genre-filters button')?.disabled || document.getElementById('export')?.disabled;
    if (recordingOrExporting) {
      audio.pause();
      message.textContent = 'Finish recording or exporting before listening.';
      return;
    }
    handingOver = true;
    try {
      if (!layer.checked && transportButton?.getAttribute('aria-pressed') === 'true') transportButton.click();
      for (const other of document.querySelectorAll('audio')) {
        if (other !== audio) other.pause();
      }
    } finally {
      handingOver = false;
    }
    indicator.textContent = 'Playing';
    message.textContent = layer.checked
      ? 'Not tempo-synced. Piano stays out of exports.'
      : (library ? 'Listening only. Never included in beat exports.' : defaultHint);
  });
  audio.addEventListener('pause', () => { indicator.textContent = 'Background music'; });

  layer.addEventListener('change', () => {
    if (!layer.checked && beatButton?.getAttribute('aria-pressed') === 'true') {
      pauseListening('Paused for your beat.');
    }
    message.textContent = layer.checked
      ? 'Not tempo-synced. Piano stays out of exports.'
      : defaultHint;
  });

  document.addEventListener('play', (event) => {
    if (event.target !== audio) pauseListening('Paused for your audio.');
  }, true);

  // A beat may finish starting asynchronously after a click. Observe the
  // existing transport state instead of introducing a second audio clock.
  const transportObserver = new MutationObserver(() => {
    if (!layer.checked && transportButton?.getAttribute('aria-pressed') === 'true') pauseListening(pauseHint);
    if (document.querySelector('#genre-filters button')?.disabled) pauseListening('Paused while you work.');
  });
  if (transportButton) transportObserver.observe(transportButton, { attributes: true, attributeFilter: ['aria-pressed'] });
  const filters = document.getElementById('genre-filters');
  if (filters) transportObserver.observe(filters, { attributes: true, subtree: true, attributeFilter: ['disabled'] });

  audio.addEventListener('error', () => {
    message.textContent = 'The recording could not load. Reload the page to try again.';
  });
  window.addEventListener('pagehide', () => audio.pause());
}
