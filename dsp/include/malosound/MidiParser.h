// malosound — dsp/include/malosound/MidiParser.h
//
// Dependency-free MIDI byte parser and tiny active-note tracker.
//
// This is intentionally not tied to JUCE. A plugin wrapper can feed bytes from
// juce::MidiBuffer into this parser, while the core stays offline-testable.

#pragma once

#include <algorithm>
#include <array>
#include <cstdint>

namespace malosound {

enum class MidiMessageType : std::uint8_t {
    None,
    NoteOff,
    NoteOn,
    ControlChange,
    ProgramChange,
    ChannelPressure,
    PitchBend,
    Realtime,
    Unsupported,
};

struct MidiMessage {
    MidiMessageType type = MidiMessageType::None;
    std::uint8_t status = 0;
    std::uint8_t channel = 0;
    std::uint8_t data1 = 0;
    std::uint8_t data2 = 0;

    bool isNoteOn() const noexcept {
        return type == MidiMessageType::NoteOn && data2 > 0;
    }

    bool isNoteOffLike() const noexcept {
        return type == MidiMessageType::NoteOff || (type == MidiMessageType::NoteOn && data2 == 0);
    }

    bool isControlChange() const noexcept {
        return type == MidiMessageType::ControlChange;
    }
};

class MidiParser {
public:
    void reset() noexcept {
        runningStatus_ = 0;
        pendingStatus_ = 0;
        pendingCount_ = 0;
        expectedData_ = 0;
        data_[0] = 0;
        data_[1] = 0;
    }

    bool feed(std::uint8_t byte, MidiMessage& out) noexcept {
        out = {};

        if (byte >= 0xF8u) {
            out.type = MidiMessageType::Realtime;
            out.status = byte;
            return true;
        }

        if (byte & 0x80u) {
            return feedStatus(byte, out);
        }

        if (!pendingStatus_) {
            if (!runningStatus_) {
                return false;
            }
            pendingStatus_ = runningStatus_;
            expectedData_ = expectedDataBytes(pendingStatus_);
            pendingCount_ = 0;
        }

        if (pendingCount_ < data_.size()) {
            data_[pendingCount_] = byte & 0x7Fu;
        }
        ++pendingCount_;

        if (pendingCount_ < expectedData_) {
            return false;
        }

        out = buildMessage(pendingStatus_, data_[0], expectedData_ > 1 ? data_[1] : 0);
        pendingStatus_ = 0;
        pendingCount_ = 0;
        expectedData_ = 0;
        return true;
    }

private:
    static std::uint8_t expectedDataBytes(std::uint8_t status) noexcept {
        const std::uint8_t high = status & 0xF0u;
        if (high == 0xC0u || high == 0xD0u) {
            return 1;
        }
        if (high >= 0x80u && high <= 0xE0u) {
            return 2;
        }
        return 0;
    }

    bool feedStatus(std::uint8_t byte, MidiMessage& out) noexcept {
        const std::uint8_t expected = expectedDataBytes(byte);
        if (expected == 0) {
            runningStatus_ = 0;
            pendingStatus_ = 0;
            pendingCount_ = 0;
            expectedData_ = 0;
            out.type = MidiMessageType::Unsupported;
            out.status = byte;
            return true;
        }

        runningStatus_ = byte;
        pendingStatus_ = byte;
        pendingCount_ = 0;
        expectedData_ = expected;
        return false;
    }

    static MidiMessage buildMessage(std::uint8_t status, std::uint8_t data1, std::uint8_t data2) noexcept {
        MidiMessage msg;
        msg.status = status;
        msg.channel = static_cast<std::uint8_t>(status & 0x0Fu);
        msg.data1 = data1;
        msg.data2 = data2;

        switch (status & 0xF0u) {
        case 0x80u: msg.type = MidiMessageType::NoteOff; break;
        case 0x90u: msg.type = MidiMessageType::NoteOn; break;
        case 0xB0u: msg.type = MidiMessageType::ControlChange; break;
        case 0xC0u: msg.type = MidiMessageType::ProgramChange; break;
        case 0xD0u: msg.type = MidiMessageType::ChannelPressure; break;
        case 0xE0u: msg.type = MidiMessageType::PitchBend; break;
        default: msg.type = MidiMessageType::Unsupported; break;
        }
        return msg;
    }

    std::uint8_t runningStatus_ = 0;
    std::uint8_t pendingStatus_ = 0;
    std::uint8_t pendingCount_ = 0;
    std::uint8_t expectedData_ = 0;
    std::array<std::uint8_t, 2> data_{};
};

class ActiveNotes {
public:
    static constexpr std::size_t kNoteCount = 128;

    void reset() noexcept {
        active_.fill(false);
        count_ = 0;
        lowest_ = 0;
        highest_ = 0;
    }

    void handle(const MidiMessage& message) noexcept {
        if (message.isNoteOn()) {
            setActive(message.data1, true);
        } else if (message.isNoteOffLike()) {
            setActive(message.data1, false);
        }
    }

    bool isActive(std::uint8_t note) const noexcept {
        return note < kNoteCount && active_[note];
    }

    std::uint8_t count() const noexcept { return count_; }
    std::uint8_t lowest() const noexcept { return count_ ? lowest_ : 0; }
    std::uint8_t highest() const noexcept { return count_ ? highest_ : 0; }

private:
    void setActive(std::uint8_t note, bool on) noexcept {
        if (note >= kNoteCount || active_[note] == on) {
            return;
        }
        active_[note] = on;
        count_ = static_cast<std::uint8_t>(on ? count_ + 1 : count_ - 1);
        recalcBounds();
    }

    void recalcBounds() noexcept {
        if (count_ == 0) {
            lowest_ = 0;
            highest_ = 0;
            return;
        }
        for (std::uint8_t i = 0; i < kNoteCount; ++i) {
            if (active_[i]) {
                lowest_ = i;
                break;
            }
        }
        for (int i = static_cast<int>(kNoteCount) - 1; i >= 0; --i) {
            if (active_[static_cast<std::size_t>(i)]) {
                highest_ = static_cast<std::uint8_t>(i);
                break;
            }
        }
    }

    std::array<bool, kNoteCount> active_{};
    std::uint8_t count_ = 0;
    std::uint8_t lowest_ = 0;
    std::uint8_t highest_ = 0;
};

} // namespace malosound
