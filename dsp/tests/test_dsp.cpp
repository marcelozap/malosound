// malosound — dsp/tests/test_dsp.cpp
//
// The acceptance criteria in docs/ABLETON_PLUGIN_PLAN.md include "no audio
// callback allocations in profiling". This suite does not wait for profiling:
// it counts allocations directly by overriding global operator new, and fails
// the build if the audio path ever allocates.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <new>
#include <vector>

#include "malosound/FeatureExtractor.h"
#include "malosound/MidiParser.h"
#include "malosound/OneEuroFilter.h"
#include "malosound/SpscRing.h"
#include "testing.h"

// ---------------------------------------------------------------------------
// Allocation tripwire
// ---------------------------------------------------------------------------
namespace {
std::size_t g_allocations = 0;
bool        g_watching    = false;

struct AllocationGuard {
    std::size_t start;
    AllocationGuard() { g_watching = true; start = g_allocations; }
    ~AllocationGuard() { g_watching = false; }
    std::size_t count() const { return g_allocations - start; }
};
} // namespace

// noinline on the deallocators: if the compiler inlines them it loses track of
// the fact that the matching operator new is ours too, and warns about
// free()-ing a pointer from the builtin new (-Wmismatched-new-delete).
#if defined(__GNUC__) || defined(__clang__)
  #define MALO_NOINLINE __attribute__((noinline))
#elif defined(_MSC_VER)
  #define MALO_NOINLINE __declspec(noinline)
#else
  #define MALO_NOINLINE
#endif

MALO_NOINLINE void* operator new(std::size_t n) {
    if (g_watching) ++g_allocations;
    void* p = std::malloc(n ? n : 1);
    if (!p) throw std::bad_alloc();
    return p;
}
MALO_NOINLINE void* operator new[](std::size_t n) { return operator new(n); }
MALO_NOINLINE void operator delete(void* p) noexcept { std::free(p); }
MALO_NOINLINE void operator delete[](void* p) noexcept { std::free(p); }
MALO_NOINLINE void operator delete(void* p, std::size_t) noexcept { std::free(p); }
MALO_NOINLINE void operator delete[](void* p, std::size_t) noexcept { std::free(p); }

// ---------------------------------------------------------------------------
// Signal helpers
// ---------------------------------------------------------------------------
namespace {

constexpr double kSR = 48000.0;
constexpr double kTwoPi = 6.283185307179586;

void fillSine(std::vector<float>& buf, double freq, double amplitude, double sampleRate,
              double phase = 0.0) {
    for (std::size_t i = 0; i < buf.size(); ++i)
        buf[i] = static_cast<float>(amplitude * std::sin(kTwoPi * freq * i / sampleRate + phase));
}

// Runs the extractor over a buffer and returns the last frame produced.
malosound::FeatureFrame runAndTakeLast(malosound::FeatureExtractor& fx,
                                       const std::vector<float>& buf) {
    fx.process(buf.data(), buf.size());
    malosound::FeatureFrame f{};
    fx.frames().popLatest(f);
    return f;
}

} // namespace

// ---------------------------------------------------------------------------
int main() {
    std::printf("malosound dsp — test suite\n");

    // -----------------------------------------------------------------------
    SECTION("SpscRing: push/pop and wraparound");
    {
        malosound::SpscRing<int, 4> ring;
        int out = 0;
        CHECK(!ring.pop(out));
        CHECK(ring.empty());

        for (int i = 1; i <= 3; ++i) CHECK(ring.push(i));
        CHECK(ring.size() == 3);
        CHECK(ring.pop(out) && out == 1);
        CHECK(ring.pop(out) && out == 2);

        // Wrap well past capacity — the mask arithmetic must hold.
        for (int i = 0; i < 100; ++i) ring.push(i);
        CHECK(ring.size() <= 4);
        CHECK(ring.pop(out));
    }

    SECTION("SpscRing: overflow drops oldest, never blocks the producer");
    {
        malosound::SpscRing<int, 4> ring;
        for (int i = 0; i < 4; ++i) CHECK(ring.push(i));
        CHECK(!ring.push(99));                    // reports the drop
        CHECK(ring.droppedCount() == 1);
        int out = 0;
        CHECK(ring.pop(out));
        CHECK(out == 1);                          // 0 was the one dropped
    }

    SECTION("SpscRing: popLatest keeps only the newest frame");
    {
        malosound::SpscRing<int, 8> ring;
        for (int i = 0; i < 5; ++i) ring.push(i);
        int out = -1;
        CHECK(ring.popLatest(out));
        CHECK(out == 4);
        CHECK(ring.empty());
        CHECK(!ring.popLatest(out));
    }

    // -----------------------------------------------------------------------
    SECTION("level: RMS of a sine is amplitude/sqrt(2)");
    {
        malosound::FeatureExtractor fx;
        fx.prepare(kSR);
        std::vector<float> buf(static_cast<std::size_t>(kSR));   // 1 second
        fillSine(buf, 440.0, 0.5, kSR);
        const auto f = runAndTakeLast(fx, buf);
        CHECK_NEAR(f.rms, 0.5 / std::sqrt(2.0), 0.01);
        CHECK_NEAR(f.peak, 0.5, 0.02);
    }

    SECTION("level: silence reads zero and produces no pitch");
    {
        malosound::FeatureExtractor fx;
        fx.prepare(kSR);
        std::vector<float> buf(static_cast<std::size_t>(kSR), 0.0f);
        const auto f = runAndTakeLast(fx, buf);
        CHECK_NEAR(f.rms, 0.0, 1e-6);
        CHECK(f.pitchHz == 0.0f);
        CHECK(!f.onset);
    }

    // -----------------------------------------------------------------------
    SECTION("bands: energy lands in the right band");
    {
        struct Case { double freq; const char* band; };
        const Case cases[] = { {60.0, "low"}, {800.0, "mid"}, {6000.0, "high"} };

        for (const auto& c : cases) {
            malosound::FeatureExtractor fx;
            fx.prepare(kSR);
            std::vector<float> buf(static_cast<std::size_t>(kSR), 0.0f);
            fillSine(buf, c.freq, 0.5, kSR);
            const auto f = runAndTakeLast(fx, buf);

            std::printf("  %5.0f Hz -> low %.4f  mid %.4f  high %.4f\n",
                        c.freq, f.low, f.mid, f.high);

            if (c.band[0] == 'l') {
                CHECK(f.low > f.mid && f.low > f.high);
            } else if (c.band[0] == 'm') {
                CHECK(f.mid > f.low && f.mid > f.high);
            } else {
                CHECK(f.high > f.low && f.high > f.mid);
            }
        }
    }

    // -----------------------------------------------------------------------
    SECTION("pitch: tracks guitar and bass fundamentals");
    {
        // Low E bass (41.2), low E guitar (82.4), A (110), A440, and the
        // e-string 12th fret (659.3) — the range this rig actually plays.
        const double freqs[] = { 41.20, 82.41, 110.0, 220.0, 440.0, 659.26 };
        for (double target : freqs) {
            malosound::FeatureExtractor fx;
            fx.prepare(kSR);
            std::vector<float> buf(static_cast<std::size_t>(kSR * 0.5));
            fillSine(buf, target, 0.4, kSR);
            const auto f = runAndTakeLast(fx, buf);
            std::printf("  target %7.2f Hz -> %7.2f Hz  (conf %.2f)\n",
                        target, f.pitchHz, f.pitchConfidence);
            CHECK_WITHIN_PERCENT(f.pitchHz, target, 2.0);
            CHECK(f.pitchConfidence > 0.5f);
        }
    }

    SECTION("pitch: a sawtooth reports the fundamental, not a harmonic");
    {
        malosound::FeatureExtractor fx;
        fx.prepare(kSR);
        std::vector<float> buf(static_cast<std::size_t>(kSR * 0.5));
        const double f0 = 146.83;   // D3
        for (std::size_t i = 0; i < buf.size(); ++i) {
            double s = 0.0;
            for (int h = 1; h <= 8; ++h)
                s += std::sin(kTwoPi * f0 * h * i / kSR) / h;
            buf[i] = static_cast<float>(0.3 * s);
        }
        const auto f = runAndTakeLast(fx, buf);
        std::printf("  sawtooth D3 -> %.2f Hz (conf %.2f)\n", f.pitchHz, f.pitchConfidence);
        CHECK_WITHIN_PERCENT(f.pitchHz, f0, 2.0);
    }

    SECTION("pitch: noise is reported as unvoiced, not as a confident note");
    {
        malosound::FeatureExtractor fx;
        fx.prepare(kSR);
        std::vector<float> buf(static_cast<std::size_t>(kSR * 0.5));
        unsigned seed = 12345u;
        for (auto& s : buf) {
            seed = seed * 1103515245u + 12345u;
            s = 0.3f * (static_cast<float>((seed >> 16) & 0x7fff) / 16384.0f - 1.0f);
        }
        const auto f = runAndTakeLast(fx, buf);
        std::printf("  noise -> %.2f Hz (conf %.2f)\n", f.pitchHz, f.pitchConfidence);
        CHECK(f.pitchConfidence < 0.9f);
    }

    // -----------------------------------------------------------------------
    SECTION("onset: a hit after silence fires exactly once");
    {
        malosound::FeatureExtractor fx;
        fx.prepare(kSR);

        std::vector<float> silence(static_cast<std::size_t>(kSR * 0.5), 0.0f);
        fx.process(silence.data(), silence.size());
        malosound::FeatureFrame drain{};
        while (fx.frames().pop(drain)) {}

        // Percussive hit: fast attack, exponential decay, broadband.
        std::vector<float> hit(static_cast<std::size_t>(kSR * 0.4), 0.0f);
        unsigned seed = 777u;
        for (std::size_t i = 0; i < hit.size(); ++i) {
            const double env = std::exp(-static_cast<double>(i) / (kSR * 0.05));
            seed = seed * 1103515245u + 12345u;
            const double n = static_cast<double>((seed >> 16) & 0x7fff) / 16384.0 - 1.0;
            hit[i] = static_cast<float>(0.7 * env * n);
        }
        fx.process(hit.data(), hit.size());

        int onsets = 0;
        malosound::FeatureFrame f{};
        while (fx.frames().pop(f)) if (f.onset) ++onsets;
        std::printf("  onsets detected: %d\n", onsets);
        CHECK(onsets >= 1);
        CHECK(onsets <= 2);   // the attack must not retrigger through the decay
    }

    SECTION("onset: a steady tone does not fire repeatedly");
    {
        malosound::FeatureExtractor fx;
        fx.prepare(kSR);
        std::vector<float> buf(static_cast<std::size_t>(kSR * 2.0));
        fillSine(buf, 220.0, 0.4, kSR);
        fx.process(buf.data(), buf.size());

        int onsets = 0;
        malosound::FeatureFrame f{};
        while (fx.frames().pop(f)) if (f.onset) ++onsets;
        std::printf("  onsets over 2 s of steady tone: %d\n", onsets);
        CHECK(onsets <= 2);   // the initial attack is legitimate; a stream is not
    }

    // -----------------------------------------------------------------------
    SECTION("frame rate: hop size produces the expected frame count");
    {
        malosound::FeatureExtractor fx;
        fx.prepare(kSR);
        std::vector<float> buf(static_cast<std::size_t>(kSR));
        fillSine(buf, 440.0, 0.3, kSR);
        fx.process(buf.data(), buf.size());
        const auto expected = static_cast<std::uint64_t>(kSR) / malosound::FeatureExtractor::kHopSize;
        CHECK(fx.framesProduced() == expected);
        std::printf("  %llu frames in 1 s (%.1f Hz publish headroom)\n",
                    static_cast<unsigned long long>(fx.framesProduced()),
                    static_cast<double>(expected));
        CHECK(static_cast<double>(expected) >= 30.0);   // the plan asks for 30 Hz
    }

    SECTION("robustness: NaN input does not poison the filter state");
    {
        malosound::FeatureExtractor fx;
        fx.prepare(kSR);
        std::vector<float> bad(4096, std::nanf(""));
        fx.process(bad.data(), bad.size());

        std::vector<float> good(static_cast<std::size_t>(kSR * 0.5));
        fillSine(good, 220.0, 0.4, kSR);
        const auto f = runAndTakeLast(fx, good);
        CHECK(std::isfinite(f.rms));
        CHECK_WITHIN_PERCENT(f.pitchHz, 220.0, 2.0);
    }

    // -----------------------------------------------------------------------
    SECTION("studio curves: 1-Euro filter has frozen defaults");
    {
        malosound::OneEuroFilter filter;
        const auto settings = filter.settings();
        CHECK_NEAR(settings.minCutoffHz, 3.0, 1e-6);
        CHECK_NEAR(settings.beta, 0.5, 1e-6);
        CHECK_NEAR(settings.dCutoffHz, 1.0, 1e-6);
    }

    SECTION("studio curves: 1-Euro filter smooths steady movement");
    {
        malosound::OneEuroFilter filter;
        filter.reset(0.0f, 0.0);
        const float slow = filter.process(1.0f, 1.0 / 60.0);
        CHECK(slow > 0.0f);
        CHECK(slow < 1.0f);
    }

    SECTION("studio curves: beta opens the filter for fast movement");
    {
        malosound::OneEuroFilter fixed({3.0f, 0.0f, 1.0f});
        malosound::OneEuroFilter adaptive({3.0f, 0.5f, 1.0f});
        fixed.reset(0.0f, 0.0);
        adaptive.reset(0.0f, 0.0);

        const float fixedOut = fixed.process(1.0f, 1.0 / 60.0);
        const float adaptiveOut = adaptive.process(1.0f, 1.0 / 60.0);
        CHECK(adaptiveOut > fixedOut);
        CHECK(adaptiveOut < 1.0f);
    }

    SECTION("studio curves: invalid samples hold the last usable value");
    {
        malosound::OneEuroFilter filter;
        filter.reset(0.25f, 0.0);
        const float before = filter.value();
        const float after = filter.process(std::nanf(""), 1.0 / 60.0);
        CHECK_NEAR(after, before, 1e-6);
        CHECK(std::isfinite(filter.process(0.75f, 2.0 / 60.0)));
    }

    SECTION("REALTIME CONTRACT: 1-Euro processing allocates zero bytes");
    {
        malosound::OneEuroFilter filter;
        filter.reset(0.0f, 0.0);
        std::size_t leaked = 0;
        {
            AllocationGuard guard;
            for (int i = 1; i <= 1000; ++i) {
                const float value = (i % 120 < 60) ? 1.0f : 0.0f;
                filter.process(value, static_cast<double>(i) / 60.0);
            }
            leaked = guard.count();
        }
        CHECK(leaked == 0);
    }

    // -----------------------------------------------------------------------
    SECTION("MIDI parser: note on, note off, and note-on zero velocity");
    {
        malosound::MidiParser parser;
        malosound::MidiMessage msg{};
        CHECK(!parser.feed(0x90, msg));
        CHECK(!parser.feed(60, msg));
        CHECK(parser.feed(127, msg));
        CHECK(msg.type == malosound::MidiMessageType::NoteOn);
        CHECK(msg.channel == 0);
        CHECK(msg.data1 == 60);
        CHECK(msg.data2 == 127);
        CHECK(msg.isNoteOn());

        CHECK(!parser.feed(0x80, msg));
        CHECK(!parser.feed(60, msg));
        CHECK(parser.feed(0, msg));
        CHECK(msg.type == malosound::MidiMessageType::NoteOff);
        CHECK(msg.isNoteOffLike());

        CHECK(!parser.feed(0x90, msg));
        CHECK(!parser.feed(61, msg));
        CHECK(parser.feed(0, msg));
        CHECK(msg.type == malosound::MidiMessageType::NoteOn);
        CHECK(msg.isNoteOffLike());
    }

    SECTION("MIDI parser: control change and running status");
    {
        malosound::MidiParser parser;
        malosound::MidiMessage msg{};
        CHECK(!parser.feed(0xB2, msg));
        CHECK(!parser.feed(21, msg));
        CHECK(parser.feed(96, msg));
        CHECK(msg.type == malosound::MidiMessageType::ControlChange);
        CHECK(msg.channel == 2);
        CHECK(msg.data1 == 21);
        CHECK(msg.data2 == 96);

        CHECK(!parser.feed(22, msg));
        CHECK(parser.feed(110, msg));
        CHECK(msg.type == malosound::MidiMessageType::ControlChange);
        CHECK(msg.channel == 2);
        CHECK(msg.data1 == 22);
        CHECK(msg.data2 == 110);
    }

    SECTION("MIDI parser: realtime byte does not break pending message");
    {
        malosound::MidiParser parser;
        malosound::MidiMessage msg{};
        CHECK(!parser.feed(0x90, msg));
        CHECK(!parser.feed(60, msg));
        CHECK(parser.feed(0xF8, msg));
        CHECK(msg.type == malosound::MidiMessageType::Realtime);
        CHECK(parser.feed(100, msg));
        CHECK(msg.type == malosound::MidiMessageType::NoteOn);
        CHECK(msg.data1 == 60);
        CHECK(msg.data2 == 100);
    }

    SECTION("MIDI parser: malformed data is ignored until status arrives");
    {
        malosound::MidiParser parser;
        malosound::MidiMessage msg{};
        CHECK(!parser.feed(64, msg));
        CHECK(!parser.feed(0xC0, msg));
        CHECK(parser.feed(10, msg));
        CHECK(msg.type == malosound::MidiMessageType::ProgramChange);
        CHECK(msg.data1 == 10);
    }

    SECTION("MIDI active notes: tracks held notes and bounds");
    {
        malosound::MidiParser parser;
        malosound::ActiveNotes active;
        malosound::MidiMessage msg{};

        const std::uint8_t bytes[] = {0x90, 64, 100, 67, 100, 60, 100, 67, 0, 0x80, 60, 0};
        for (const auto byte : bytes) {
            if (parser.feed(byte, msg)) {
                active.handle(msg);
            }
        }

        CHECK(active.count() == 1);
        CHECK(active.isActive(64));
        CHECK(!active.isActive(67));
        CHECK(!active.isActive(60));
        CHECK(active.lowest() == 64);
        CHECK(active.highest() == 64);
    }

    SECTION("REALTIME CONTRACT: MIDI parsing and active-note tracking allocate zero bytes");
    {
        malosound::MidiParser parser;
        malosound::ActiveNotes active;
        malosound::MidiMessage msg{};
        const std::uint8_t bytes[] = {0x90, 60, 127, 64, 100, 67, 100, 64, 0, 0xB0, 21, 96, 0xF8};
        std::size_t leaked = 0;
        {
            AllocationGuard guard;
            for (int i = 0; i < 1000; ++i) {
                for (const auto byte : bytes) {
                    if (parser.feed(byte, msg)) {
                        active.handle(msg);
                    }
                }
            }
            leaked = guard.count();
        }
        CHECK(leaked == 0);
    }

    SECTION("host buffer sizes: 64/128/256/512/1024 all behave identically");
    {
        std::vector<float> reference;
        for (std::size_t blockSize : {64u, 128u, 256u, 512u, 1024u}) {
            malosound::FeatureExtractor fx;
            fx.prepare(kSR);
            std::vector<float> buf(static_cast<std::size_t>(kSR * 0.5));
            fillSine(buf, 330.0, 0.4, kSR);
            for (std::size_t i = 0; i < buf.size(); i += blockSize) {
                const std::size_t n = std::min(blockSize, buf.size() - i);
                fx.process(buf.data() + i, n);
            }
            malosound::FeatureFrame f{};
            fx.frames().popLatest(f);
            CHECK_WITHIN_PERCENT(f.pitchHz, 330.0, 2.0);
            CHECK_NEAR(f.rms, 0.4 / std::sqrt(2.0), 0.01);
        }
    }

    SECTION("sample rates: 44.1 / 48 / 96 kHz all resolve the same note");
    {
        for (double sr : {44100.0, 48000.0, 96000.0}) {
            malosound::FeatureExtractor fx;
            fx.prepare(sr);
            std::vector<float> buf(static_cast<std::size_t>(sr * 0.5));
            fillSine(buf, 196.0, 0.4, sr);   // G3
            const auto f = runAndTakeLast(fx, buf);
            std::printf("  %.0f Hz host rate -> %.2f Hz\n", sr, f.pitchHz);
            CHECK_WITHIN_PERCENT(f.pitchHz, 196.0, 2.0);
        }
    }

    // -----------------------------------------------------------------------
    SECTION("REALTIME CONTRACT: process() allocates zero bytes");
    {
        malosound::FeatureExtractor fx;
        fx.prepare(kSR);                       // prepare may allocate; process may not

        std::vector<float> buf(512);
        fillSine(buf, 440.0, 0.4, kSR);

        std::size_t leaked = 0;
        {
            AllocationGuard guard;
            for (int block = 0; block < 400; ++block)
                fx.process(buf.data(), buf.size());
            leaked = guard.count();
        }
        std::printf("  allocations during 400 audio blocks: %zu\n", leaked);
        CHECK(leaked == 0);
    }

    SECTION("REALTIME CONTRACT: draining the ring from the reader allocates nothing");
    {
        malosound::FeatureExtractor fx;
        fx.prepare(kSR);
        std::vector<float> buf(512);
        fillSine(buf, 440.0, 0.4, kSR);
        for (int i = 0; i < 200; ++i) fx.process(buf.data(), buf.size());

        std::size_t leaked = 0;
        {
            AllocationGuard guard;
            malosound::FeatureFrame f{};
            while (fx.frames().pop(f)) {}
            leaked = guard.count();
        }
        CHECK(leaked == 0);
    }

    // -----------------------------------------------------------------------
    SECTION("BUDGET: analysis cost vs realtime");
    {
        // ABLETON_PLUGIN_PLAN.md acceptance: "under 2-3% CPU for bridge analysis
        // on a modern Mac". This is a rough guide, not a pass/fail gate — CI
        // machines and laptops differ — so it prints rather than asserts.
        malosound::FeatureExtractor fx;
        fx.prepare(kSR);
        std::vector<float> buf(512);
        fillSine(buf, 220.0, 0.4, kSR);

        constexpr int kBlocks = 4000;   // 512 * 4000 / 48000 = ~42.7 s of audio
        const auto t0 = std::chrono::steady_clock::now();
        for (int i = 0; i < kBlocks; ++i) {
            fx.process(buf.data(), buf.size());
            malosound::FeatureFrame f{};
            while (fx.frames().pop(f)) {}
        }
        const auto t1 = std::chrono::steady_clock::now();

        const double elapsed = std::chrono::duration<double>(t1 - t0).count();
        const double audioSeconds = kBlocks * 512.0 / kSR;
        const double cpuPercent = 100.0 * elapsed / audioSeconds;
        std::printf("  %.2f s of analysis for %.1f s of audio  ->  %.3f%% of one core\n",
                    elapsed, audioSeconds, cpuPercent);
        std::printf("  (plan budget: 2-3%%)\n");
        CHECK(cpuPercent < 25.0);   // generous: only catches a catastrophic regression
    }

    return testing::summary();
}
