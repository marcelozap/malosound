// malosound — dsp/include/malosound/Biquad.h
//
// RBJ cookbook biquad, transposed direct form II.
// Coefficient calculation is NOT audio-thread safe (it uses transcendentals and
// is only cheap-ish); call it from prepare(). process() is a handful of FLOPs
// and is safe in the callback.

#pragma once

#include <cmath>

#include "Numerics.h"

namespace malosound {

class Biquad {
public:
    void reset() noexcept { z1_ = z2_ = 0.0f; }

    // y[n] — transposed DF-II, good numerical behaviour in float.
    // State is denormal-flushed: this filter runs on decaying tails all day.
    inline float process(float x) noexcept {
        const float y = b0_ * x + z1_;
        z1_ = flushDenormal(b1_ * x - a1_ * y + z2_);
        z2_ = flushDenormal(b2_ * x - a2_ * y);
        return y;
    }

    void setLowpass(double sampleRate, double freq, double q = 0.70710678) noexcept {
        const double w0 = kTwoPi * clampFreq(freq, sampleRate);
        const double cs = std::cos(w0), sn = std::sin(w0);
        const double alpha = sn / (2.0 * q);
        const double b0 = (1.0 - cs) * 0.5, b1 = 1.0 - cs, b2 = (1.0 - cs) * 0.5;
        const double a0 = 1.0 + alpha, a1 = -2.0 * cs, a2 = 1.0 - alpha;
        setCoeffs(b0, b1, b2, a0, a1, a2);
    }

    void setHighpass(double sampleRate, double freq, double q = 0.70710678) noexcept {
        const double w0 = kTwoPi * clampFreq(freq, sampleRate);
        const double cs = std::cos(w0), sn = std::sin(w0);
        const double alpha = sn / (2.0 * q);
        const double b0 = (1.0 + cs) * 0.5, b1 = -(1.0 + cs), b2 = (1.0 + cs) * 0.5;
        const double a0 = 1.0 + alpha, a1 = -2.0 * cs, a2 = 1.0 - alpha;
        setCoeffs(b0, b1, b2, a0, a1, a2);
    }

    // Constant skirt-gain bandpass (peak gain = Q).
    void setBandpass(double sampleRate, double freq, double q = 0.70710678) noexcept {
        const double w0 = kTwoPi * clampFreq(freq, sampleRate);
        const double cs = std::cos(w0), sn = std::sin(w0);
        const double alpha = sn / (2.0 * q);
        const double b0 = alpha, b1 = 0.0, b2 = -alpha;
        const double a0 = 1.0 + alpha, a1 = -2.0 * cs, a2 = 1.0 - alpha;
        setCoeffs(b0, b1, b2, a0, a1, a2);
    }

private:
    static constexpr double kTwoPi = 6.283185307179586;

    // Normalised frequency, kept clear of DC and Nyquist so the coefficients stay finite.
    static double clampFreq(double freq, double sampleRate) noexcept {
        if (sampleRate <= 0.0) return 0.25;
        double f = freq / sampleRate;
        if (f < 1.0e-5) f = 1.0e-5;
        if (f > 0.49)   f = 0.49;
        return f;
    }

    void setCoeffs(double b0, double b1, double b2, double a0, double a1, double a2) noexcept {
        const double inv = 1.0 / a0;
        b0_ = static_cast<float>(b0 * inv);
        b1_ = static_cast<float>(b1 * inv);
        b2_ = static_cast<float>(b2 * inv);
        a1_ = static_cast<float>(a1 * inv);
        a2_ = static_cast<float>(a2 * inv);
        reset();
    }

    float b0_ = 1.0f, b1_ = 0.0f, b2_ = 0.0f, a1_ = 0.0f, a2_ = 0.0f;
    float z1_ = 0.0f, z2_ = 0.0f;
};

} // namespace malosound
