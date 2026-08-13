#include "malosound/PitchDetector.h"

#include <cmath>

namespace malosound {

namespace {
constexpr double kQ1 = 0.541196;   // 4th-order Butterworth pair
constexpr double kQ2 = 1.306563;

// Integration length for the YIN difference function. Must satisfy
// kIntegration + kMaxTau <= kWindow so the lag never reads past the window.
constexpr std::size_t kIntegration = PitchDetector::kWindow - PitchDetector::kMaxTau;
static_assert(kIntegration + PitchDetector::kMaxTau <= PitchDetector::kWindow,
              "YIN lag would read past the analysis window");
} // namespace

void PitchDetector::prepare(double sampleRate) noexcept {
    if (sampleRate <= 0.0) sampleRate = 48000.0;
    analysisRate_ = sampleRate / static_cast<double>(kDecim);

    // Anti-alias below the decimated Nyquist before throwing samples away.
    // Without this, a cymbal folds down and reads as a pitched note.
    const double cutoff = analysisRate_ * 0.42;
    aaA_.setLowpass(sampleRate, cutoff, kQ1);
    aaB_.setLowpass(sampleRate, cutoff, kQ2);

    reset();
}

void PitchDetector::reset() noexcept {
    aaA_.reset();
    aaB_.reset();
    window_.fill(0.0f);
    linear_.fill(0.0f);
    diff_.fill(0.0f);
    cmnd_.fill(0.0f);
    writePos_     = 0;
    filled_       = 0;
    decimCounter_ = 0;
    lastPitch_    = 0.0f;
}

void PitchDetector::analyze(float& pitchHz, float& confidence) noexcept {
    pitchHz    = 0.0f;
    confidence = 0.0f;

    if (filled_ < kWindow) return;

    // Unwrap the circular buffer oldest-first. Fixed-size copy, no allocation.
    for (std::size_t i = 0; i < kWindow; ++i)
        linear_[i] = window_[(writePos_ + i) & kWindowMask];

    // Level gate first — YIN on silence returns confident nonsense.
    double sumSq = 0.0;
    for (std::size_t i = 0; i < kWindow; ++i)
        sumSq += static_cast<double>(linear_[i]) * linear_[i];
    const float rms = static_cast<float>(std::sqrt(sumSq / static_cast<double>(kWindow)));
    if (rms < minLevel_) { lastPitch_ = 0.0f; return; }

    // --- YIN step 1: squared difference function ---
    for (std::size_t tau = 0; tau < kMaxTau; ++tau) {
        double acc = 0.0;
        for (std::size_t j = 0; j < kIntegration; ++j) {
            const double d = static_cast<double>(linear_[j]) - linear_[j + tau];
            acc += d * d;
        }
        diff_[tau] = static_cast<float>(acc);
    }

    // --- YIN step 2: cumulative mean normalised difference ---
    cmnd_[0] = 1.0f;
    double running = 0.0;
    for (std::size_t tau = 1; tau < kMaxTau; ++tau) {
        running += diff_[tau];
        cmnd_[tau] = (running > 0.0)
            ? static_cast<float>(diff_[tau] * static_cast<double>(tau) / running)
            : 1.0f;
    }

    // --- YIN step 3: absolute threshold, first dip below it wins ---
    std::size_t bestTau = 0;
    for (std::size_t tau = kMinTau; tau < kMaxTau; ++tau) {
        if (cmnd_[tau] < threshold_) {
            // Descend to the local minimum rather than taking the first crossing —
            // the crossing point is on the shoulder and reads sharp.
            while (tau + 1 < kMaxTau && cmnd_[tau + 1] < cmnd_[tau]) ++tau;
            bestTau = tau;
            break;
        }
    }

    if (bestTau == 0) {
        // Nothing cleared the threshold. Fall back to the global minimum so we
        // still report something, but the confidence will be low and the caller
        // can gate on it.
        float best = cmnd_[kMinTau];
        bestTau = kMinTau;
        for (std::size_t tau = kMinTau + 1; tau < kMaxTau; ++tau) {
            if (cmnd_[tau] < best) { best = cmnd_[tau]; bestTau = tau; }
        }
        if (best > 0.6f) { lastPitch_ = 0.0f; return; }   // aperiodic: call it unvoiced
    }

    // --- YIN step 4: parabolic interpolation for sub-sample tau ---
    double refined = static_cast<double>(bestTau);
    if (bestTau > 0 && bestTau + 1 < kMaxTau) {
        const double y0 = cmnd_[bestTau - 1];
        const double y1 = cmnd_[bestTau];
        const double y2 = cmnd_[bestTau + 1];
        const double denom = 2.0 * (2.0 * y1 - y0 - y2);
        if (std::fabs(denom) > 1.0e-12)
            refined += (y2 - y0) / denom;
    }

    if (refined <= 0.0) { lastPitch_ = 0.0f; return; }

    pitchHz    = static_cast<float>(analysisRate_ / refined);
    confidence = 1.0f - cmnd_[bestTau];
    if (confidence < 0.0f) confidence = 0.0f;
    if (confidence > 1.0f) confidence = 1.0f;

    lastPitch_ = pitchHz;
}

} // namespace malosound
