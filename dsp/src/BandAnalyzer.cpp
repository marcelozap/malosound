#include "malosound/BandAnalyzer.h"

#include <cmath>

namespace malosound {

namespace {
// Crossovers. Chosen for what the instruments actually are, not round numbers:
// bass guitar and kick body sit under 200; guitar and voice fundamentals live
// between; pick attack and cymbals are above 2k.
constexpr double kLowCross  = 200.0;
constexpr double kHighCross = 2000.0;

// Butterworth Q pair for a cascaded 4th-order response.
constexpr double kQ1 = 0.541196;
constexpr double kQ2 = 1.306563;
} // namespace

void BandAnalyzer::prepare(double sampleRate) noexcept {
    lowA_.setLowpass(sampleRate, kLowCross, kQ1);
    lowB_.setLowpass(sampleRate, kLowCross, kQ2);

    // Bandpass built as HP then LP so the passband stays flat rather than peaky.
    midA_.setHighpass(sampleRate, kLowCross, kQ1);
    midB_.setLowpass(sampleRate, kHighCross, kQ1);

    highA_.setHighpass(sampleRate, kHighCross, kQ1);
    highB_.setHighpass(sampleRate, kHighCross, kQ2);

    reset();
}

void BandAnalyzer::reset() noexcept {
    lowA_.reset();  lowB_.reset();
    midA_.reset();  midB_.reset();
    highA_.reset(); highB_.reset();
    sumLow_ = sumMid_ = sumHigh_ = 0.0;
    count_ = 0;
}

void BandAnalyzer::drain(float& low, float& mid, float& high) noexcept {
    if (count_ == 0) {
        low = mid = high = 0.0f;
        return;
    }
    const double inv = 1.0 / static_cast<double>(count_);
    low  = static_cast<float>(std::sqrt(sumLow_  * inv));
    mid  = static_cast<float>(std::sqrt(sumMid_  * inv));
    high = static_cast<float>(std::sqrt(sumHigh_ * inv));

    sumLow_ = sumMid_ = sumHigh_ = 0.0;
    count_ = 0;
}

} // namespace malosound
