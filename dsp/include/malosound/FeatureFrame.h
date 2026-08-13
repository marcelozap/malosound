// malosound — dsp/include/malosound/FeatureFrame.h
//
// One frame of extracted musical control data. This is the entire contract
// between the audio thread and everything downstream (network thread, visual
// engine, diagnostics UI).
//
// It is a trivially-copyable POD on purpose: it crosses a lock-free queue, so
// it must never own memory, never have a non-trivial destructor, and never
// grow a std::string.

#pragma once

#include <cstdint>
#include <type_traits>

namespace malosound {

struct FeatureFrame {
    // Sample index of the END of the analysis hop that produced this frame.
    // Monotonic from the last prepare() call. Downstream uses it to detect
    // dropped frames and to timestamp without touching a clock on the audio thread.
    std::uint64_t sampleTime = 0;

    // --- level ---
    float rms  = 0.0f;   // linear, 0..1-ish
    float peak = 0.0f;   // linear, absolute peak in the hop

    // --- spectral bands, linear RMS per band ---
    float low  = 0.0f;   // < ~200 Hz     — kick, bass guitar body
    float mid  = 0.0f;   // ~200-2000 Hz  — guitar, voice fundamentals
    float high = 0.0f;   // > ~2000 Hz    — cymbals, air, pick attack

    // --- pitch (monophonic; voice, guitar, bass) ---
    float pitchHz         = 0.0f;  // 0 when unvoiced
    float pitchConfidence = 0.0f;  // 0..1, YIN aperiodicity inverted, gated on level

    // --- onset ---
    float onsetStrength = 0.0f;    // rectified energy flux, unitless
    bool  onset         = false;   // true on the single frame the onset fires
};

static_assert(std::is_trivially_copyable<FeatureFrame>::value,
              "FeatureFrame crosses a lock-free queue and must stay trivially copyable");

} // namespace malosound
