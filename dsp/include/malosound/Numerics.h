// malosound — dsp/include/malosound/Numerics.h
//
// Two small guards that the audio path cannot do without, written so that no
// optimiser flag can delete them.

#pragma once

#include <cmath>
#include <cstdint>
#include <cstring>

namespace malosound {

// Bit-level finiteness test.
//
// std::isfinite() is legally COMPILED AWAY under -ffast-math / /fp:fast — the
// compiler is told NaN cannot happen, so the check is dead code. But NaN very
// much can happen: any plugin upstream in the chain can hand us one, and a
// single NaN through an IIR poisons the filter state permanently, for the rest
// of the session. Comparing the exponent bits cannot be optimised out.
inline bool isFiniteBits(float x) noexcept {
    std::uint32_t bits;
    std::memcpy(&bits, &x, sizeof(bits));
    return (bits & 0x7F800000u) != 0x7F800000u;   // all-ones exponent = inf or NaN
}

// Denormal flush.
//
// A decaying filter tail eventually drops into denormal range, where x86 can
// cost ~100x per operation. On a quiet passage that is exactly when it happens,
// and it can blow the audio deadline for no audible reason. Hosts usually set
// FTZ/DAZ, but "usually" is not a guarantee we get to rely on inside someone
// else's process.
inline float flushDenormal(float x) noexcept {
    return (std::fabs(x) < 1.0e-30f) ? 0.0f : x;
}

} // namespace malosound
