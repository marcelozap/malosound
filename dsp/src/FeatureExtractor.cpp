#include "malosound/FeatureExtractor.h"

#include <cmath>

#include "malosound/Numerics.h"

namespace malosound {

void FeatureExtractor::prepare(double sampleRate) noexcept {
    if (sampleRate <= 0.0) sampleRate = 48000.0;
    sampleRate_ = sampleRate;

    bands_.prepare(sampleRate);
    pitch_.prepare(sampleRate);
    onset_.prepare(sampleRate / static_cast<double>(kHopSize));

    reset();
}

void FeatureExtractor::reset() noexcept {
    bands_.reset();
    pitch_.reset();
    onset_.reset();
    ring_.reset();

    hopCount_       = 0;
    hopSumSquares_  = 0.0;
    hopPeak_        = 0.0f;
    sampleTime_     = 0;
    framesProduced_ = 0;

    pitchHopCount_       = 0;
    lastPitchHz_         = 0.0f;
    lastPitchConfidence_ = 0.0f;
}

void FeatureExtractor::pushSample(float x) noexcept {
    // Reject non-finite input. A NaN from a misbehaving plugin upstream would
    // otherwise poison every filter state permanently, for the rest of the set.
    // Bit-level, not std::isfinite — see Numerics.h for why that matters.
    if (!isFiniteBits(x)) x = 0.0f;

    hopSumSquares_ += static_cast<double>(x) * x;
    const float a = std::fabs(x);
    if (a > hopPeak_) hopPeak_ = a;

    bands_.accumulate(x);
    pitch_.push(x);

    ++sampleTime_;
    if (++hopCount_ >= kHopSize) emitFrame();
}

void FeatureExtractor::process(const float* input, std::size_t numSamples) noexcept {
    if (input == nullptr) return;
    for (std::size_t i = 0; i < numSamples; ++i)
        pushSample(input[i]);
}

void FeatureExtractor::processStereo(const float* left, const float* right,
                                     std::size_t numSamples) noexcept {
    if (left == nullptr || right == nullptr) return;
    for (std::size_t i = 0; i < numSamples; ++i)
        pushSample(0.5f * (left[i] + right[i]));
}

void FeatureExtractor::emitFrame() noexcept {
    FeatureFrame f;
    f.sampleTime = sampleTime_;

    f.rms  = static_cast<float>(std::sqrt(hopSumSquares_ / static_cast<double>(kHopSize)));
    f.peak = hopPeak_;

    bands_.drain(f.low, f.mid, f.high);

    if (++pitchHopCount_ >= kPitchEveryNHops) {
        pitchHopCount_ = 0;
        pitch_.analyze(lastPitchHz_, lastPitchConfidence_);
    }
    f.pitchHz         = lastPitchHz_;
    f.pitchConfidence = lastPitchConfidence_;

    // Onset drive: weight toward the bands where an attack actually shows.
    // A full-mix master bus and a fingerpicked guitar both move here; the low
    // band is halved so a sustained bass note does not read as a hit.
    const float onsetEnergy = 0.5f * f.low + f.mid + f.high;
    f.onset = onset_.process(onsetEnergy, f.onsetStrength);

    ring_.push(f);   // never blocks; drops the oldest frame if the reader stalled
    ++framesProduced_;

    hopCount_      = 0;
    hopSumSquares_ = 0.0;
    hopPeak_       = 0.0f;
}

} // namespace malosound
