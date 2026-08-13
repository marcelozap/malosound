// malosound — dsp/include/malosound/OnsetDetector.h
//
// Energy-flux onset detection with an adaptive threshold and a refractory
// period. Fed once per hop from FeatureExtractor, not per sample.
//
// Adaptive rather than fixed because the same detector runs on a quiet
// fingerpicked guitar and on a full mix off the master bus, and a fixed
// threshold is wrong for at least one of them.

#pragma once

namespace malosound {

class OnsetDetector {
public:
    void prepare(double hopsPerSecond) noexcept;
    void reset() noexcept;

    // Returns true on the hop where an onset fires. `strength` is written with
    // the rectified flux regardless.
    bool process(float bandEnergy, float& strength) noexcept;

    void setSensitivity(float s) noexcept;   // 0..1, higher = more onsets
    void setMinLevel(float lvl) noexcept { minLevel_ = lvl; }

private:
    float previousEnergy_ = 0.0f;
    float runningMean_    = 0.0f;   // slow follower over the flux signal
    float sensitivity_    = 0.5f;
    float minLevel_       = 1.0e-4f;
    float meanCoeff_      = 0.05f;  // set from hop rate in prepare()
    int   refractoryHops_ = 3;
    int   sinceLastOnset_ = 1000;
};

} // namespace malosound
