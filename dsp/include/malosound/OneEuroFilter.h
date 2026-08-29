// malosound — dsp/include/malosound/OneEuroFilter.h
//
// Adaptive 1-Euro smoothing for studio control curves.
//
// Use this after calibration and before perception mapping/dispatch:
//
//   Calibrate -> 1-Euro Filter -> Perception Curve -> Dispatch
//
// Defaults are the MaloSound studio contract: min cutoff 3.0 Hz, beta 0.5.

#pragma once

#include <algorithm>
#include <cmath>

#include "malosound/Numerics.h"

namespace malosound {

class OneEuroFilter {
public:
    struct Settings {
        float minCutoffHz = 3.0f;
        float beta        = 0.5f;
        float dCutoffHz   = 1.0f;
    };

    OneEuroFilter() noexcept = default;
    explicit OneEuroFilter(Settings settings) noexcept
        : settings_(sanitize(settings)) {}

    void setSettings(Settings settings) noexcept {
        settings_ = sanitize(settings);
    }

    Settings settings() const noexcept { return settings_; }

    void reset(float value = 0.0f, double timeSeconds = 0.0) noexcept {
        value = clean(value, 0.0f);
        xHat_ = value;
        dxHat_ = 0.0f;
        lastRaw_ = value;
        lastTimeSeconds_ = timeSeconds;
        initialized_ = true;
    }

    bool initialized() const noexcept { return initialized_; }

    float value() const noexcept { return initialized_ ? xHat_ : 0.0f; }

    float process(float value, double timeSeconds) noexcept {
        value = clean(value, initialized_ ? xHat_ : 0.0f);
        if (!initialized_) {
            reset(value, timeSeconds);
            return xHat_;
        }

        const double dt = timeSeconds - lastTimeSeconds_;
        if (!(dt > 0.0) || !std::isfinite(dt)) {
            lastRaw_ = value;
            lastTimeSeconds_ = timeSeconds;
            return xHat_;
        }

        const float dx = static_cast<float>((value - lastRaw_) / dt);
        const float dAlpha = alpha(settings_.dCutoffHz, static_cast<float>(dt));
        dxHat_ = lowpass(dx, dxHat_, dAlpha);

        const float cutoff = settings_.minCutoffHz + settings_.beta * std::fabs(dxHat_);
        const float xAlpha = alpha(cutoff, static_cast<float>(dt));
        xHat_ = lowpass(value, xHat_, xAlpha);

        lastRaw_ = value;
        lastTimeSeconds_ = timeSeconds;
        return xHat_;
    }

private:
    static constexpr float kPi = 3.14159265358979323846f;

    static Settings sanitize(Settings settings) noexcept {
        settings.minCutoffHz = std::max(0.001f, clean(settings.minCutoffHz, 3.0f));
        settings.beta = std::max(0.0f, clean(settings.beta, 0.5f));
        settings.dCutoffHz = std::max(0.001f, clean(settings.dCutoffHz, 1.0f));
        return settings;
    }

    static float clean(float value, float fallback) noexcept {
        return isFiniteBits(value) ? value : fallback;
    }

    static float alpha(float cutoffHz, float dtSeconds) noexcept {
        const float tau = 1.0f / (2.0f * kPi * cutoffHz);
        return 1.0f / (1.0f + tau / dtSeconds);
    }

    static float lowpass(float value, float previous, float alphaValue) noexcept {
        return flushDenormal(alphaValue * value + (1.0f - alphaValue) * previous);
    }

    Settings settings_{};
    bool initialized_ = false;
    float xHat_ = 0.0f;
    float dxHat_ = 0.0f;
    float lastRaw_ = 0.0f;
    double lastTimeSeconds_ = 0.0;
};

} // namespace malosound
