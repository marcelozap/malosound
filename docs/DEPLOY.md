# MaloSound instrument deployment

Production: https://malosound.ai, Vercel, GitHub repository marcelozap/malosound,
production branch master. A local preview or Sites deployment is not production proof.

## Reproducible build

Python 3.10+ standard library; no npm install or audio synthesis is needed in CI.

```powershell
python -X utf8 tools/build_website.py
python -m http.server 4188 --bind 127.0.0.1 --directory build
```

The allowlist stages 22 public files: the player, CSS, 404 page, cover image,
font and license, eight instrument documents, and eight House MP3s.
The builder does not regenerate journal data. Notes synthesize in the browser.

House bytes are deliberately NOT committed. config/instrument-audio.json pins
public release URLs, byte counts, SHA256s and corresponding document hashes.
The build uses matching local assets/instrument MP3s when present; otherwise it
fetches the release files and verifies them before staging. A missing/mismatched
asset fails the build. Keep the source WAVs and manifests backed up separately.

## Publishing

Commit only approved files. Never include another agent's unfinished journal
changes. Push the release commit to the integration branch first.

For the initial audio release, with GitHub credentials already available to Git:

```powershell
pwsh -File tools/publish_instrument_audio.ps1
```

The helper uploads only the eight manifest-pinned generated MP3s to the GitHub
release instrument-audio-2026-09-13. It never replaces conflicting assets and
does not store credentials. Publish those assets BEFORE pushing master so the
Vercel build can retrieve them. On future data/audio changes, use a new immutable
release tag and update the manifest plus builder release prefix together.

Fast-forward the approved commit to master without force. Vercel runs the
buildCommand/outputDirectory in vercel.json. Check the GitHub deployment status,
then check https://malosound.ai itself, its CSS/font, all eight documents/MP3s,
Notes/House switching and desktop/phone layouts. A successful build alone is
not evidence of a working live deployment.

## Scope and known limits

Eight dates: Aug 31; Sep 1, 2, 3, 4, 8, 9, 10, 2026. No automatic data updates.
390-minute sessions only; unknown/shortened session shapes must not be invented.
Pitch reflects smoothed market-price position, not personal trading outcomes.

Do not publish content/days, raw history, trading ledgers, broker files, private
recordings, local paths or credentials. The instrument remains a historical
interpretation. Data-use permission is a separate unresolved question, not
established by test results. Output-device latency, audible ear-to-eye alignment,
and Safari/iOS/Firefox behavior have not been established by Chromium UI checks.
