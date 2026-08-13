# Where the audio actually lives

`C:\Users\Green Machine\Music\XIV Music Library\`

That library is already well organised — numbered folders, a drop inbox, clear
separation of loops / seeds / stems / exports. **Do not move it into this repo.**

This repo holds *code and configuration*: Max for Live devices, DSP source,
Ableton templates and racks, release metadata, and scripts. The bytes stay in
the library. Git is bad at 4 GB of samples and worse at binary Live sets.

Referenced from scripts as `$env:XIV_MUSIC_LIBRARY`, defaulting to the path above.
