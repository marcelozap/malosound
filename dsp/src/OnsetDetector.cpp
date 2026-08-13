#include "malosound/OnsetDetector.h"

#include <cmath>

namespace malosound {

void OnsetDetector::prepare(double hopsPerSecond) noexcept {
    if (hopsPerSecond <= 0.0) hopsPerSecond = 90.0;

    // Slow follower over the flux signal, ~350 ms. Long enough that a single
    // hit does not raise the threshold above the next hit in the same bar.
    constexpr double kMeanTauSeconds = 0.35;
    meanCoeff_ = static_cast<float>(1.0 - std::exp(-1.0 / (kMeanTauSeconds * hopsPerSecond)));

    // 50 ms refractory. Below this you are detecting the attack transient twice,
    // not detecting two notes.
    refractoryHops_ = static_cast<int>(0.05 * hopsPerSecond + 0.5);
    if (refractoryHops_ < 1) refractoryHops_ = 1;

    reset();
}

void OnsetDetector::reset() noexcept {
    previousEnergy_ = 0.0f;
    runningMean_    = 0.0f;
    sinceLastOnset_ = 1000;
}

void OnsetDetector::setSensitivity(float s) noexcept {
    if (s < 0.0f) s = 0.0f;
    if (s > 1.0f) s = 1.0f;
    sensitivity_ = s;
}

bool OnsetDetector::process(float bandEnergy, float& strength) noexcept {
    // Half-wave rectified flux: energy going UP is an onset, energy going down
    // is a release and must never fire.
    float flux = bandEnergy - previousEnergy_;
    if (flux < 0.0f) flux = 0.0f;
    previousEnergy_ = bandEnergy;
    strength = flux;

    if (sinceLastOnset_ < 1000000) ++sinceLastOnset_;

    // Adaptive floor. sensitivity 1.0 -> 1.5x the recent mean flux,
    // sensitivity 0.0 -> 7.5x, which only the hardest hits clear.
    const float multiplier = 1.5f + 6.0f * (1.0f - sensitivity_);
    const float threshold  = runningMean_ * multiplier;

    const bool loudEnough  = bandEnergy > minLevel_;
    const bool clearsFloor = flux > threshold && flux > minLevel_;
    const bool ready       = sinceLastOnset_ >= refractoryHops_;

    // Update the mean AFTER the comparison, so a hit does not mask itself.
    runningMean_ += meanCoeff_ * (flux - runningMean_);

    if (loudEnough && clearsFloor && ready) {
        sinceLastOnset_ = 0;
        return true;
    }
    return false;
}

} // namespace malosound
