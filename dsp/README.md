# dsp — the malosound analysis core

Realtime feature extraction: level, three-band energy, onset, and monophonic
pitch. This is the engine behind the Voice Mirror Bridge plugin described in
[`docs/ABLETON_PLUGIN_PLAN.md`](../docs/ABLETON_PLUGIN_PLAN.md).

## Why there is no JUCE in here

JUCE belongs in the *plugin wrapper*, not in the analysis. Keeping this library
plain C++17 with zero dependencies buys three things that matter more than
convenience:

- it builds and tests in about a second, **offline**, on any machine
- the DSP can be tested without instantiating a plugin host
- when the bridge eventually needs a standalone diagnostic app, an LV2 build, or
  a completely different frontend, none of that touches this code

The wrapper's job is to call three functions. That is the whole coupling.

## Build and test

```bash
cmake -S dsp -B dsp/build -DCMAKE_BUILD_TYPE=Release
cmake --build dsp/build
ctest --test-dir dsp/build --output-on-failure
```

No CMake handy? One line works:

```bash
g++ -std=c++17 -O2 -Idsp/include -Idsp/tests dsp/src/*.cpp dsp/tests/test_dsp.cpp -o test_dsp && ./test_dsp
```

On Windows: `scripts/build-dsp.ps1`.

## Using it from the plugin

```cpp
#include "malosound/FeatureExtractor.h"

malosound::FeatureExtractor extractor;

void prepareToPlay(double sampleRate, int) {          // message thread
    extractor.prepare(sampleRate);
}

void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) {  // AUDIO THREAD
    const auto n = static_cast<std::size_t>(buffer.getNumSamples());
    if (buffer.getNumChannels() >= 2)
        extractor.processStereo(buffer.getReadPointer(0), buffer.getReadPointer(1), n);
    else
        extractor.process(buffer.getReadPointer(0), n);
}

void networkThreadTick() {                            // 30 Hz publish
    malosound::FeatureFrame frame;
    if (extractor.frames().popLatest(frame))
        sendOverWebSocketOrOsc(frame);                // newest state only
}
```

The extractor never touches the audio. It is read-only analysis — you can drop
it on the master bus mid-set without risking the mix.

## The realtime contract

`process()` must not allocate, lock, log, open a socket, touch the filesystem,
or wait on anything. `dsp/tests` enforces the allocation half of that by
overriding global `operator new` and counting calls across 400 audio blocks. If
you add a `std::vector`, a `std::string`, or a `std::function` to the audio path,
**the test suite fails.** That is the test working. Do not delete it.

## What the numbers mean

| Field | Range | Notes |
|---|---|---|
| `rms`, `peak` | linear | per 512-sample hop |
| `low` / `mid` / `high` | linear RMS | crossovers at 200 Hz and 2 kHz, 4th order |
| `pitchHz` | 23–750 Hz | 0 when unvoiced |
| `pitchConfidence` | 0–1 | gate the visuals on this, not on `pitchHz != 0` |
| `onsetStrength` | unitless | rectified energy flux |
| `onset` | bool | true on exactly one frame per hit |

Frames publish at **93 Hz** (48 kHz / 512), comfortably above the 30 Hz the plan
asks for, so the network thread always has something fresh to send. Pitch runs
every third hop (~31 Hz) because that is all anyone downstream consumes — see
`kPitchEveryNHops`.

## Design notes worth knowing before you change anything

**Pitch is decimated 4:1 before YIN.** Full-rate YIN over a long window costs
roughly 170 Mops/s and would eat the entire CPU budget on its own. Decimating to
12 kHz (with a proper anti-alias pair first — without it a cymbal folds down and
reads as a pitched note) keeps the same 41 Hz low-E resolution for a fraction of
the cost. Measured: **~1.1% of one core** for the whole extractor.

**Bands are IIR, not FFT.** The visual engine wants smooth band energies, not
spectral resolution. Biquads cost a few FLOPs per sample, add no latency, and
need no scratch buffer — which is what keeps the callback allocation-free
without an FFT plan living somewhere awkward.

**Onset threshold is adaptive.** The same detector runs on a fingerpicked guitar
and on a full mix off the master bus. A fixed threshold is wrong for at least
one of them. There is a 50 ms refractory period; below that you are detecting
one attack twice, not two notes.

**The ring drops frames rather than blocking.** If the network thread stalls, the
audio thread throws away the oldest frame and carries on. Never invert that.

## Test coverage

`ctest` runs 67 checks: ring buffer semantics under wraparound and overflow,
RMS against the analytic value, band separation at 60 / 800 / 6000 Hz, pitch
across the instrument range (41–660 Hz) plus a sawtooth harmonic trap and a
noise rejection case, onset firing once on a hit and not at all on a steady
tone, identical behaviour across 64–1024 sample host buffers and 44.1 / 48 /
96 kHz, NaN input recovery, and the two allocation tripwires.
