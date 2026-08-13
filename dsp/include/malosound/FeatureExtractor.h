// malosound — dsp/include/malosound/FeatureExtractor.h
//
// The audio-thread entry point. This is the whole DSP core as far as the plugin
// wrapper is concerned:
//
//     prepare(sampleRate, maxBlockSize)   <- message thread, may be slow
//     process(input, numSamples)          <- AUDIO THREAD, must not block
//     frames()                            <- network thread drains the ring
//
// THE CONTRACT (from docs/ABLETON_PLUGIN_PLAN.md, "Realtime Audio Rules"):
// process() must not allocate, lock, log, open sockets, touch the filesystem,
// or wait on anything. dsp/tests enforces the allocation half of that with a
// global operator new counter — if you add a std::vector in here, the test
// suite fails. That is deliberate. Do not "fix" the test.
//
// This core has NO JUCE dependency on purpose. JUCE lives in the plugin wrapper;
// this library stays plain C++17 so it builds and unit-tests in a second without
// a framework, on any machine, offline.

#pragma once

#include <cstddef>
#include <cstdint>

#include "BandAnalyzer.h"
#include "FeatureFrame.h"
#include "OnsetDetector.h"
#include "PitchDetector.h"
#include "SpscRing.h"

namespace malosound {

class FeatureExtractor {
public:
    // Analysis hop in samples at host rate. 512 @ 48 kHz = 93.75 frames/sec,
    // comfortably above the 30 Hz publish rate the plan asks for, so the network
    // thread always has a fresh frame to send.
    static constexpr std::size_t kHopSize = 512;
    static constexpr std::size_t kRingCapacity = 64;

    // The YIN pass is the single most expensive thing in this library. The plan
    // asks for pitch at 15-30 Hz while frames publish at 30 Hz, so running it on
    // every hop (93 Hz) is three times more pitch than anyone consumes. Analyse
    // every third hop (~31 Hz) and hold the value in between: same published
    // result, a third of the CPU.
    static constexpr std::size_t kPitchEveryNHops = 3;

    using Ring = SpscRing<FeatureFrame, kRingCapacity>;

    // Message thread. Safe to be slow. Not safe to call while process() runs.
    void prepare(double sampleRate) noexcept;
    void reset() noexcept;

    // AUDIO THREAD. Mono input. No allocation, no locks, no IO.
    void process(const float* input, std::size_t numSamples) noexcept;

    // AUDIO THREAD. Convenience for stereo hosts — sums to mono at -6 dB.
    void processStereo(const float* left, const float* right, std::size_t numSamples) noexcept;

    // Network thread drains this.
    Ring& frames() noexcept { return ring_; }
    const Ring& frames() const noexcept { return ring_; }

    // Diagnostics (UI thread, 10 Hz per the plan).
    std::uint64_t framesProduced() const noexcept { return framesProduced_; }

    void setOnsetSensitivity(float s) noexcept { onset_.setSensitivity(s); }

private:
    void pushSample(float x) noexcept;   // audio thread, one mono sample
    void emitFrame() noexcept;           // audio thread, called at each hop boundary

    BandAnalyzer  bands_;
    OnsetDetector onset_;
    PitchDetector pitch_;
    Ring          ring_;

    double sampleRate_    = 48000.0;
    std::size_t hopCount_ = 0;
    double hopSumSquares_ = 0.0;
    float  hopPeak_       = 0.0f;

    std::size_t pitchHopCount_ = 0;
    float lastPitchHz_         = 0.0f;
    float lastPitchConfidence_ = 0.0f;

    std::uint64_t sampleTime_     = 0;
    std::uint64_t framesProduced_ = 0;
};

} // namespace malosound
