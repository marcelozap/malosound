cmake_minimum_required(VERSION 3.16)
project(malosound_dsp LANGUAGES CXX)

# No FetchContent, no find_package, no submodules. This library must build
# offline on a laptop that has never seen it before. If you are about to add a
# dependency here, that is the thing to think twice about.

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

add_library(malosound_dsp STATIC
    src/BandAnalyzer.cpp
    src/FeatureExtractor.cpp
    src/OnsetDetector.cpp
    src/PitchDetector.cpp
)

target_include_directories(malosound_dsp PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

if(MSVC)
    target_compile_options(malosound_dsp PRIVATE /W4)
else()
    target_compile_options(malosound_dsp PRIVATE -Wall -Wextra -Wshadow)
endif()

# DELIBERATELY NOT -ffast-math / /fp:fast.
#
# It looks like free speed and it is not. -ffast-math implies -ffinite-math-only,
# which tells the compiler NaN cannot occur — so it deletes the NaN guard in
# FeatureExtractor::pushSample() entirely. A single NaN handed to us by any
# upstream plugin then poisons every IIR state permanently, and the bridge goes
# silent for the rest of the set with no error anywhere.
#
# The test suite catches this: build with -ffast-math and the "NaN input does not
# poison the filter state" case fails. That failure is the flag telling the truth.
#
# The two things fast-math was wanted for are handled explicitly instead, in
# Numerics.h: denormal flushing in the filter state, and a bit-level finiteness
# check that no optimiser can remove. Measured cost of doing it honestly: ~1.1%
# of one core, against a 2-3% budget.
if(NOT MSVC)
    target_compile_options(malosound_dsp PRIVATE -fno-math-errno)
endif()

add_library(malosound::dsp ALIAS malosound_dsp)

# ---------------------------------------------------------------------------
option(MALOSOUND_DSP_TESTS "Build the malosound dsp test suite" ON)

if(MALOSOUND_DSP_TESTS)
    enable_testing()
    add_executable(test_dsp tests/test_dsp.cpp)
    target_link_libraries(test_dsp PRIVATE malosound_dsp)
    target_include_directories(test_dsp PRIVATE tests)

    # The allocation tripwire in the tests replaces global operator new. Fast-math
    # is fine here, but the test TU must NOT be built with an allocator that
    # bypasses operator new, so leave sanitizers/allocator flags off by default.
    add_test(NAME dsp COMMAND test_dsp)
endif()
