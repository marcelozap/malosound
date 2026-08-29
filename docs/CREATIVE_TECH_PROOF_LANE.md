# MaloSound Creative Technology Proof Lane

Last updated: 2026-08-28

## Objective

MaloSound is the XIV creative technology proof lane for original music, movement, DSP, stems, release tooling, and signed provenance. The lane should show working artifacts first: audio in, deterministic analysis out, coded companion generated, release bundle packaged, receipt verified.

Technology supports the music. It should make the work easier to verify, rebuild, publish, and explain without turning the project into a platform before the songs exist.

## Operating Rules

- Do not center GateKPT.
- Keep public language focused on MaloSound, XIV, Green Machine, original music, AudioAnalysisV1 JSON, coded rhythm, visual output, motion-mapped visuals, release workflow, and ownership records.
- Do not publish raw studio files, private filenames, local paths, private notes, private receipt internals, or unreleased analysis internals.
- Do not claim AI understands music.
- Do not claim a trained audio model unless that artifact exists and is verified.
- Keep audio binaries out of Git.

## Required Verification

Run these checks before calling the lane healthy:

```powershell
python tools\audio_analysis_v1.py --self-test
python tools\stem_io.py --self-test
python tools\receipts_ed25519.py verify --ledger data\receipts.jsonl
```

Current observed result on 2026-08-28:

```text
audio analysis v1 self-test OK
stem io self-test OK
ledger OK: data\receipts.jsonl
```

For the full local system check:

```powershell
python tools\system_selftest.py
```

Current observed result on 2026-08-28:

```text
SYSTEM SELF-TEST OK: 22/22 checks passed
```

## Determinism Check

Repeated analysis must produce byte-identical JSON when the same audio and fixed timestamp are used.

Fixture check performed on 2026-08-28:

```text
repeat_a_sha256=d46374a629b1c7ab3ccc61ce7ce405cfce2c336e5e0a75d824b08a0e5759f445
repeat_b_sha256=d46374a629b1c7ab3ccc61ce7ce405cfce2c336e5e0a75d824b08a0e5759f445
REPEAT ANALYSIS HASH OK
```

Use generated fixtures for public proof tests unless a track has been deliberately cleared for release.

## Demo Priority

The first public demo should be small enough to finish and honest enough to trust:

1. One short original audio artifact cleared for public release.
2. One AudioAnalysisV1 JSON summary with local paths and private names removed.
3. One coded rhythm or motion-mapped companion.
4. One ERC-2981-compatible manifest summary with 100% creator-owned splits.
5. One signed Ed25519/SHA-256 receipt summary.
6. One public MaloSound.ai page that explains what can be verified and what remains local.

Working title: "For Rosco." Treat that as an internal/demo title until the public release name is approved.

## No-Paid-AI Rebuild Path

The proof lane must remain usable without paid AI tools:

1. Run the setup script for hooks and local expectations.
2. Generate stems with the local stem generator.
3. Run AudioAnalysisV1 locally.
4. Generate the procedural companion locally.
5. Append and verify Ed25519 receipts locally.
6. Package the release bundle locally.
7. Publish only sanitized public artifacts.

## Next Implementation Step

Build a sanitized public `/proof/` page for MaloSound.ai that explains the artifact chain without exposing local paths, private filenames, raw receipt excerpts, or unreleased track material.
