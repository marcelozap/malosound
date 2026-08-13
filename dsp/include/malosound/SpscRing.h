// malosound — dsp/include/malosound/SpscRing.h
//
// Single-producer / single-consumer lock-free ring buffer.
//
// Producer = the audio thread. Consumer = the network thread.
// The audio thread must never block, so on overflow the producer DROPS the
// oldest frame rather than waiting. That is the correct trade for this system:
// the visual engine does not need every frame, it needs the newest one.
//
// Capacity must be a power of two so the wrap is a mask, not a modulo.

#pragma once

#include <array>
#include <atomic>
#include <cstddef>

namespace malosound {

template <typename T, std::size_t Capacity>
class SpscRing {
    static_assert((Capacity & (Capacity - 1)) == 0, "Capacity must be a power of two");
    static_assert(Capacity >= 2, "Capacity must be at least 2");

public:
    // Audio thread only. Never blocks, never allocates.
    // Returns false if it had to drop the oldest frame to make room.
    bool push(const T& item) noexcept {
        const auto w = writeIndex_.load(std::memory_order_relaxed);
        const auto r = readIndex_.load(std::memory_order_acquire);

        bool dropped = false;
        if (w - r >= Capacity) {
            // Full. Advance the reader past one frame — we are the only writer,
            // and a stale frame is worth less than a stalled audio callback.
            readIndex_.store(r + 1, std::memory_order_release);
            dropped = true;
            droppedCount_.fetch_add(1, std::memory_order_relaxed);
        }

        buffer_[w & kMask] = item;
        writeIndex_.store(w + 1, std::memory_order_release);
        return !dropped;
    }

    // Consumer thread only.
    bool pop(T& out) noexcept {
        const auto r = readIndex_.load(std::memory_order_relaxed);
        if (r == writeIndex_.load(std::memory_order_acquire))
            return false;

        out = buffer_[r & kMask];
        readIndex_.store(r + 1, std::memory_order_release);
        return true;
    }

    // Consumer convenience: throw away everything but the newest frame.
    // This is what the network thread actually wants at publish time.
    bool popLatest(T& out) noexcept {
        bool got = false;
        T tmp;
        while (pop(tmp)) { out = tmp; got = true; }
        return got;
    }

    std::size_t size() const noexcept {
        return writeIndex_.load(std::memory_order_acquire)
             - readIndex_.load(std::memory_order_acquire);
    }

    bool empty() const noexcept { return size() == 0; }

    std::size_t droppedCount() const noexcept {
        return droppedCount_.load(std::memory_order_relaxed);
    }

    void reset() noexcept {
        writeIndex_.store(0, std::memory_order_relaxed);
        readIndex_.store(0, std::memory_order_relaxed);
        droppedCount_.store(0, std::memory_order_relaxed);
    }

    static constexpr std::size_t capacity() noexcept { return Capacity; }

private:
    static constexpr std::size_t kMask = Capacity - 1;

    std::array<T, Capacity> buffer_{};
    std::atomic<std::size_t> writeIndex_{0};
    std::atomic<std::size_t> readIndex_{0};
    std::atomic<std::size_t> droppedCount_{0};
};

} // namespace malosound
