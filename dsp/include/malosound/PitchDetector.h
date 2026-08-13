// malosound — dsp/include/malosound/PitchDetector.h
//
// YIN-style monophonic pitch detection on a decimated stream.
//
// Why decimated: full-rate YIN over a 2048-sample window costs ~1.8M ops per
// analysis. At 48 kHz / 512-sample hops that is ~170 Mops/s for pitch alone —
// enough to threaten the 2-3% CPU budget in ABLETON_PLUGIN_PLAN.md. Decimating
// by 4 (48k -> 12k) drops the same analysis to ~2.7 Mops/s while still
// resolving 55 Hz (low E on a bass, 41 Hz, needs the 8x path — see kDecim).
//
// Everything is a fixed std::array. No allocation, ever, including in prepare().

#pragma once

#include <array>
#include <cstddef>

#include "Biquad.h"

namespace malosound {

class PitchDetector {
public:
    // Decimation factor from host rate to analysis rate.
    static constexpr int kDecim = 4;
    // Analysis window, in decimated samples. 1024 @ 12 kHz = 85 ms — long enough
    // for two periods of a 41 Hz low B/E, short enough to track a sung note.
    static constexpr std::size_t kWindow = 1024;
    static constexpr std::size_t kMaxTau = 512;   // 12000/512 = 23 Hz floor
    static constexpr std::size_t kMinTau = 16;    // 12000/16  = 750 Hz ceiling

    void prepare(double sampleRate) noexcept;
    void reset() noexcept;

    // Audio thread. Feed every host-rate sample; the detector handles its own
    // anti-alias filtering and decimation internally.
    inline void push(float x) noexcept {
        const float f = aaB_.process(aaA_.process(x));
        if (++decimCounter_ < kDecim) return;
        decimCounter_ = 0;
        window_[writePos_] = f;
        writePos_ = (writePos_ + 1) & kWindowMask;
        if (filled_ < kWindow) ++filled_;
    }

    // Audio thread. Runs the actual YIN pass. Call once per hop, not per sample.
    // Writes 0 Hz / 0 confidence when the signal is unvoiced or too quiet.
    void analyze(float& pitchHz, float& confidence) noexcept;

    void setThreshold(float t) noexcept { threshold_ = t; }
    void setMinLevel(float l) noexcept { minLevel_ = l; }

private:
    static constexpr std::size_t kWindowMask = kWindow - 1;
    static_assert((kWindow & kWindowMask) == 0, "kWindow must be a power of two");

    Biquad aaA_, aaB_;                       // anti-alias before decimation
    std::array<float, kWindow> window_{};    // circular, decimated
    std::array<float, kWindow> linear_{};    // unwrapped copy for the YIN pass
    std::array<float, kMaxTau> diff_{};      // YIN difference function
    std::array<float, kMaxTau> cmnd_{};      // cumulative mean normalised difference

    std::size_t writePos_ = 0;
    std::size_t filled_   = 0;
    int   decimCounter_   = 0;
    double analysisRate_  = 12000.0;
    float threshold_      = 0.15f;
    float minLevel_       = 1.0e-3f;
    float lastPitch_      = 0.0f;
};

} // namespace malosound
