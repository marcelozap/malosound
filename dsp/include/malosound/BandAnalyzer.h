// malosound — dsp/include/malosound/BandAnalyzer.h
//
// Three-band energy split with IIR filters rather than an FFT.
// Deliberate choice: the visual engine wants smooth band energies at 30 Hz, not
// spectral resolution. IIRs cost a few FLOPs per sample, need no window, no
// buffering latency, and no scratch memory — which keeps the audio callback
// allocation-free without an FFT plan living somewhere.

#pragma once

#include "Biquad.h"

namespace malosound {

class BandAnalyzer {
public:
    void prepare(double sampleRate) noexcept;
    void reset() noexcept;

    // Audio thread. Accumulates squared energy per band.
    inline void accumulate(float x) noexcept {
        const float l = lowB_.process(lowA_.process(x));
        const float m = midB_.process(midA_.process(x));
        const float h = highB_.process(highA_.process(x));
        sumLow_  += l * l;
        sumMid_  += m * m;
        sumHigh_ += h * h;
        ++count_;
    }

    // Audio thread. Reads the accumulated RMS per band and clears the accumulator.
    void drain(float& low, float& mid, float& high) noexcept;

private:
    // Two cascaded biquads per band = 4th order, ~24 dB/oct. Enough separation
    // that a kick does not light up the "high" band.
    Biquad lowA_, lowB_;
    Biquad midA_, midB_;
    Biquad highA_, highB_;

    double sumLow_ = 0.0, sumMid_ = 0.0, sumHigh_ = 0.0;
    unsigned count_ = 0;
};

} // namespace malosound
