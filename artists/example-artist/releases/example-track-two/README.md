# Example Track Two

Example Artist — direct release bundle.

Open `index.html` to listen, download, and read what the receipt means.

## Verify this bundle

Python 3, this folder, no install and no internet:

```
python verify.py . --fingerprint MS1-RE3L-M2BI-6WNR-OGR4
```

A pass means the audio here is byte-for-byte what was signed, and it was
signed by the key published as `MS1-RE3L-M2BI-6WNR-OGR4`.

## What is in here

- `audio/example-take.wav` — the track
- `data/example-take.audioanalysis.v1.json` — AudioAnalysisV1 measurements of that exact file
- `manifest/example-track-two.release_manifest_v1.json` — release manifest with the ERC-2981-compatible royalty split
- `ledger/receipt_excerpt.jsonl` — the signed receipt
- `source/pattern.js` — deterministic Strudel companion pattern
- `ARTIST.json` — the artist's public key and fingerprint
- `verify.py` — the verifier, standalone

## Receipt

```
record hash   88fa8345dca5df0926c0394f019a67ba1d9f7dada9fb14d6a2bc7a597e5a5d28
previous      9b1e47b705746146e8c131c802517894bd9806992a5a21d8cc44bf607f267fb6
signed at     2026-08-26T00:00:01+00:00
public key    5810437c12119622c9d2bab96a54a7242512f7ede44fcbb11ef185c562df8e80
fingerprint   MS1-RE3L-M2BI-6WNR-OGR4
```

## Boundary

This is local file-based proof. No smart contract is deployed, no token is
minted, no wallet is connected, and no third party has attested to anything.
