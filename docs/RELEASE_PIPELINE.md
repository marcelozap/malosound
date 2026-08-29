# maloSound Release Provenance Pipeline

The local end-to-end path from an audio file to a verifiable release bundle.
Everything runs inside `XIV/malosound` on local files. Nothing deploys a
contract, connects a wallet, mints a token, or uploads an asset.

**Writing for an artist rather than for the repo? → [`FOR_ARTISTS.md`](FOR_ARTISTS.md)**

## Shape

The pipeline is artist-driven. `artists/<slug>/artist.json` is the identity;
every path, key and royalty split comes from there.

```
artists/<slug>/artist.json          public identity: name, rights holder,
                                    royalty bps, PUBLIC key, fingerprint, paths
         │
         ├─ keys/          private signing seed          (gitignored)
         ├─ ledger/        append-only signed receipts    (tracked)
         ├─ analysis/      AudioAnalysisV1 artifacts      (tracked)
         ├─ companions/    Strudel patterns               (tracked)
         ├─ manifests/     release manifests              (tracked)
         ├─ incoming/      raw audio drops                (gitignored)
         └─ releases/      finished bundles; audio/ gitignored
```

`malosound` is registered against its historical paths (`data/receipts.jsonl`,
`data/keys/`, `releases/`, `manifests/`, `data/gold/audio_analysis`,
`scripts/strudel/tracks`) so its existing ledger and releases carry forward
unchanged. New artists get the uniform layout above.

## Commands

```powershell
# once per artist
python tools\onboard_artist.py --name "Artist Name"

# per release
python tools\release.py --artist <slug> --audio "<file>" --title "<title>"

# anyone, anywhere, with just the bundle
python <bundle>\verify.py <bundle> --fingerprint MS1-...

# prove the whole system from empty
python tools\system_selftest.py
```

`tools/release.py` accepts `--cover`, `--support-note`, `--release-slug`,
`--license`, `--consent`, `--created-at` and `--json`.

## What one release run does

1. **Analyse.** WAV goes through `tools/audio_analysis_v1.py`; everything else
   through `tools/audio_analysis_ffmpeg.py`. Both are validated against
   `schemas/audio_analysis.py` before anything downstream may sign them, and the
   result is written key-sorted so the artifact hash is reproducible.
2. **Sign.** `tools/receipts_ed25519.py` binds the audio hash and the analysis
   hash into one record, chained to the artist's previous record, and signs it
   with that artist's key. Then the whole ledger is re-verified.
3. **Companion.** `tools/procedural_companion.py` derives a Strudel pattern
   deterministically from the analysis, and the determinism is re-checked.
4. **Manifest.** `manifests/generator.py` writes the release manifest with the
   artist's ERC-2981-compatible royalty split.
5. **Package.** The bundle is assembled with package-relative paths, and
   `verify.py`, `index.html` and `ARTIST.json` are placed inside it.

## Receipt schemas

| Schema | Binds | Used by |
| --- | --- | --- |
| `malosound.receipt.v1` | audio hash, analysis hash, title, timestamp, previous hash | historical records |
| `malosound.receipt.v2` | all of v1 **plus the artist slug and public key** | every release since the registry |

The v2 addition is what stops a genuine receipt being re-attributed to another
artist: the artist identity is inside the hash the signature covers.
`verify_ledger` reads both and additionally refuses a ledger signed by more than
one key.

## Package schemas

| Schema | Paths | Verifies |
| --- | --- | --- |
| `malosound.release_package.v1` | absolute, machine-specific | only on the machine that built it, via `tools/verify_release_package.py` |
| `malosound.release_package.v2` | package-relative | anywhere, via the `verify.py` inside the bundle |

v1 remains for the historical fixture. `verify_release_package.py` now detects a
v2 bundle and points at the bundled verifier instead of failing confusingly.

## Schema boundary

`AudioAnalysisV1` is strict. It carries file identity, duration, sample rate,
channels, bit depth, SHA-256, onset candidates, RMS energy, confidence values,
model versions, provenance, and BPM/beat/downbeat estimates where the onset
evidence supports them.

It does not calculate loudness, true peak, key, or harmonic profile, and the
validator rejects a document that claims to.

## Signing boundary

One artist, one key, one ledger. Private seeds live under `artists/*/keys/` and
`data/keys/`, both gitignored. Public keys and fingerprints are tracked in
`artist.json`, because publishing them is the point.

## Evidence level

L1 — deterministic baseline. Every quantity here is computed reproducibly from
its input. No model, no learning, and no claim beyond that.
