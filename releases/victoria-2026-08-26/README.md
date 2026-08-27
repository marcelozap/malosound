# Victoria

Project XIV / maloSound — direct release bundle.

Open `index.html` to listen, download, and read what the receipt means.

## Verify this bundle

Python 3, this folder, no install and no internet:

```
python verify.py . --fingerprint MS1-BBVQ-2WV7-JAOA-26K3
```

A pass means the audio here is byte-for-byte what was signed, and it was
signed by the key published as `MS1-BBVQ-2WV7-JAOA-26K3`.

## What is in here

- `audio/vicotira9-08pm.mp3` — the track
- `data/vicotira9-08pm.audioanalysis.v1.json` — AudioAnalysisV1 measurements of that exact file
- `manifest/victoria-2026-08-26.release_manifest_v1.json` — release manifest with the ERC-2981-compatible royalty split
- `ledger/receipt_excerpt.jsonl` — the signed receipt
- `source/pattern.js` — deterministic Strudel companion pattern
- `ARTIST.json` — the artist's public key and fingerprint
- `verify.py` — the verifier, standalone

## Receipt

```
record hash   aacfd39c652112a43804d6b73a9c1319e976532236535beab761da4b5280ff5a
previous      fbf674171c5dfde239c736c7ec4b72fbacaf55ea96b9f5d0efc8df68846062a7
signed at     2026-08-26T16:01:53+00:00
public key    55cf872ab278db5ad87521b9d658ac64edf38e46323c61d96a8e925bb1332282
fingerprint   MS1-BBVQ-2WV7-JAOA-26K3
```

## Boundary

This is local file-based proof. No smart contract is deployed, no token is
minted, no wallet is connected, and no third party has attested to anything.
