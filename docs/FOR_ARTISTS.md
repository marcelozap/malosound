# maloSound, for artists

You made something. You want people to hear it, and you want the people who
care to be able to support you directly. You do not want to wait on a
distributor, a playlist, or a payout formula to make that possible.

This is the tooling for that. Four commands, no account, no server, no fee.

---

## What you get

A folder. Inside it: your track, a page that plays it, and a receipt that proves
the track is yours and has not been altered. You can email the folder, put it on
a USB stick, host it anywhere, or sell the download. The proof travels with it.

Anyone can check the proof themselves, on their own machine, with no internet
and nothing installed but Python. They do not have to trust you, or maloSound,
or anyone else.

## What you do not get

Be clear about this before you tell anyone about it.

- **This is not a blockchain release.** Nothing is deployed, minted, or put on
  chain. The royalty terms are written in a standard-compatible format so they
  *could* be used on chain later. Today they are a file.
- **This is not copyright registration.** A signature proves *you held these
  bytes at this time and signed them*. It does not adjudicate who wrote the
  song. It is evidence, not a court.
- **This is not a store.** There is no payment processing here. The bundle is
  what you hand over once someone has paid you, however you take payment.
- **This is not distribution.** Nobody discovers you because of a receipt. That
  is what the free upload to Instagram and YouTube is for.

The receipt is the better receipt. It is not the pitch.

---

## The four commands

### 1. Onboard yourself, once

```
python tools/onboard_artist.py --name "Your Name"
```

This makes your signing key and registers you. It prints a fingerprint like
`MS1-BBVQ-2WV7-JAOA-26K3`. That fingerprint is your public identity — put it in
your bio, your video descriptions, your site. It is how people know a bundle is
really yours.

Your private key lands in `artists/<you>/keys/`. It never enters git. Back it
up somewhere you trust. If you lose it you cannot sign as yourself again; if
someone else gets it they can sign as you.

Optional flags worth knowing:

```
--slug your-name              folder name, derived from --name otherwise
--rights-holder "Legal Name"  the person or entity holding the rights
--royalty-bps 1000            resale royalty in basis points (1000 = 10%)
--link instagram=https://...  repeatable; shows on your release pages
```

### 2. Release a track

```
python tools/release.py --artist your-name --audio path/to/track.wav --title "Track Title"
```

WAV, MP3, FLAC, M4A — the analyser picks the right decoder. Add `--cover art.jpg`
for cover art, and `--support-note "..."` for a line on the page about how people
can support this particular release.

That one command:

1. measures the audio and writes an `AudioAnalysisV1` file describing that exact file
2. signs the audio and the analysis together into your ledger, chained to your last release
3. generates a deterministic Strudel companion pattern from the analysis
4. writes the release manifest, with your ERC-2981-compatible royalty split
5. builds the bundle: audio, page, receipt, manifest, verifier
6. verifies the finished bundle the way a stranger would

### 3. Check it yourself

```
python artists/your-name/releases/track-title/verify.py \
       artists/your-name/releases/track-title \
       --fingerprint MS1-...
```

### 4. Prove the whole system, any time

```
python tools/system_selftest.py
```

Onboards two artists who did not exist a second ago, releases for both, then
tries six ways to fake one and shows each being caught. Runs in a temporary
directory; your work is untouched. This is the run to show someone who asks
whether it actually works.

---

## What is in a bundle

```
releases/<track>/
  index.html      the page: play, download, and what the receipt means
  audio/          the track
  data/           AudioAnalysisV1 measurements of that exact file
  manifest/       release manifest with the royalty split
  ledger/         the signed receipt
  source/         the Strudel companion pattern
  ARTIST.json     your public key and fingerprint
  verify.py       the verifier, standalone
  README.md       what to do with all of it
  PACKAGE_MANIFEST.json
```

Every path inside the bundle is relative to the bundle. Move the folder
anywhere, to any operating system — it still verifies.

---

## How someone else checks your release

Give them the folder and your fingerprint. They run:

```
python verify.py . --fingerprint MS1-...
```

Behind that one line: every file is re-hashed against the manifest; the receipt's
record hash is recomputed from scratch; the Ed25519 signature is checked against
the public key; the key in the receipt is checked against the fingerprint you
published; and the signed audio hash is checked against the audio actually sitting
in the folder.

If any of it was touched, the check fails and says which part.

Without `--fingerprint` it still proves the bundle is internally consistent and
signed by the key it carries — it just cannot prove *whose* key that is. The
fingerprint is what closes that gap, which is why publishing it matters.

## What forgery looks like when it fails

`tools/system_selftest.py` runs these live every time:

| Attempt | Caught by |
| --- | --- |
| Audio swapped for a different file | signed audio hash does not match the folder |
| Audio swapped *and* the manifest rewritten to match | the signature covers the hash, not the manifest |
| The signed title edited | record hash no longer recomputes; signature fails |
| Bundle re-labelled as another artist | the artist slug is inside the signed hash |
| Another artist's key pasted into `ARTIST.json` | receipt was not signed by that key |
| A real bundle offered under the wrong fingerprint | fingerprint mismatch |

---

## Your ledger

Each artist has their own append-only ledger. Every receipt carries the hash of
the one before it, so the releases form a chain in the order you made them.
Removing or reordering a release breaks every receipt after it.

```
python tools/artist_registry.py list          every artist on this machine
python tools/artist_registry.py check         key, fingerprint and ledger agree
python tools/artist_registry.py show <slug>   one artist
```

A ledger is signed by exactly one key. If a second key ever appears in it,
`check` fails and names the line.

---

## The release shape this is built for

1. **Make the music.** That part is still the hard part and nothing here helps.
2. **Free attention layer.** Instagram snippet, 20–45 seconds. YouTube upload,
   full track or visualiser. No friction, no signup, no ask.
3. **Direct support layer.** The bundle: download, cover, receipt, and the page
   explaining why any of it matters.
4. **Proof layer.** The receipt, the analysis, the manifest, the companion
   pattern. Underneath, not in front.

Lead with the music:

> I made three songs about my friend.
> You can listen free.
> If you want to support directly, here is the verified download.

Not with the cryptography. The receipt should feel like a better receipt, not
like homework.

---

## Honest limits, one more time

The signature proves the bytes and the key. It does not prove authorship,
originality, clearance, or that you are who your fingerprint says you are — that
last one rests on you publishing the fingerprint somewhere people already trust
to be you. Nothing here has been reviewed by a lawyer, and none of it is a
substitute for one where money or rights are actually at stake.

What it does do is put the proof in the artist's hands instead of a platform's.
That is the whole claim, and it is worth stating no larger than it is.
