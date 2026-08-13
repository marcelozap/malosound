# Voice Mirror Bridge Plugin Technical Design

The bridge plugin exists to extract musical control data from the DAW without endangering monitoring, recording, or the live performance.

In the gateKPT MacBook + PC rig, this plugin runs on the MacBook inside Ableton/Logic/MainStage and sends lightweight control data to the PC visual app. See [MACBOOK_PC_DEPLOYMENT_PLAN.md](./MACBOOK_PC_DEPLOYMENT_PLAN.md).

## Targets

Initial formats:

- VST3 for Ableton Live, Reaper, Bitwig, Studio One, Cubase.
- AU for Logic Pro and MainStage.

Framework:

- JUCE C++.

Later:

- Standalone diagnostic app.
- LV2 if Linux demand exists.
- AAX only after commercial demand justifies Avid SDK/testing overhead.

## Plugin Modes

### Voice Insert

Inserted on the vocal track before or after vocal effects.

Outputs:

- Voice pitch.
- Voice level.
- Voice spectral bands.
- Voice onset.
- Optional scene/intensity automation.

### Master/Loop Insert

Inserted on the master bus or RC-505 loop return.

Outputs:

- Room/full-mix energy.
- Drum/transient pulses.
- Section intensity.

### MIDI/Chord Insert

Inserted on an instrument/MIDI track when the host supports MIDI into the plugin.

Outputs:

- Active notes.
- Chord color.
- Root/tension hints.

## Realtime Audio Rules

The audio callback must not:

- Allocate memory.
- Open sockets.
- Write files.
- Log to console.
- Lock a mutex that can be held by the UI/network thread.
- Block waiting for the visual engine.

The audio callback may:

- Read audio samples.
- Update fixed-size ring buffers.
- Compute simple feature values.
- Write atomics or lock-free queue entries.

## Thread Model

```text
Audio thread
  -> lightweight analysis
  -> lock-free feature queue

Network thread
  -> pop latest feature frame
  -> smooth/rate-limit
  -> serialize JSON or OSC
  -> send to localhost

UI thread
  -> parameters
  -> diagnostics
  -> connection state
```

The network thread should drop old frames and send the newest state. Visuals do not need every audio buffer.

## Analysis Blocks

Suggested features:

- RMS/peak: short sliding window.
- Bands: simple IIR filters or FFT-derived bands.
- Onset: spectral flux or energy delta with adaptive threshold.
- Pitch: autocorrelation/YIN-style detector for monophonic voice.
- Confidence: pitch stability plus energy threshold.
- MIDI: active note set and simple chord classification.

Suggested update rates:

- Audio buffer analysis: every callback.
- Feature publish: 30 Hz default.
- Pitch publish: 15-30 Hz.
- UI diagnostics: 10 Hz.

## Parameters

Automatable plugin parameters:

- `Intensity` 0-1
- `Scene` enum
- `Palette` enum
- `Bloom` 0-1
- `Motion` 0-1
- `Blackout` boolean
- `Bridge Enabled` boolean
- `Source Role` enum: voice/master/drums/piano/loop

These parameters let performers automate visuals from Ableton clips, arrangement lanes, MIDI controllers, or foot pedals.

## Network Strategy

Prototype:

- Plugin companion app hosts WebSocket.
- Browser visual engine connects as client.

Production:

- Plugin or helper process hosts WebSocket/OSC.
- Helper process is preferred if plugin sandboxing or DAW restrictions make direct networking unreliable.
- Discovery can be localhost-first; no cloud dependency.

## Failure Modes

- Visual engine closed: plugin continues silently.
- Network unavailable: plugin shows disconnected state, audio unaffected.
- Invalid visual command: ignore command.
- DAW buffer underrun risk: reduce analysis quality before touching audio safety.

## Test Matrix

DAWs:

- Ableton Live.
- Logic Pro.
- MainStage.
- Reaper.

Plugin formats:

- macOS AU.
- macOS VST3.
- Windows VST3.

Performance tests:

- 64, 128, 256, 512 sample buffers.
- 44.1, 48, 96 kHz sample rates.
- Voice-only track.
- Master bus full mix.
- MIDI chord track.
- Visual engine disconnected.
- Visual engine reconnecting during recording.

Acceptance criteria:

- No added audio latency.
- No audio callback allocations in profiling.
- No DAW crash when visual engine is killed.
- Stable 30 Hz feature stream.
- Under 2-3% CPU for bridge analysis on a modern Mac.
