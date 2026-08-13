// malosound — dsp/tests/testing.h
//
// Deliberately dependency-free. No GoogleTest, no Catch2, no FetchContent.
// The point of this library is that it builds and tests offline in about a
// second on any machine with a C++17 compiler — adding a test framework that
// needs a network fetch would throw that away.

#pragma once

#include <cmath>
#include <cstdio>
#include <string>

namespace testing {

inline int& failures() { static int f = 0; return f; }
inline int& checks()   { static int c = 0; return c; }

inline void report(bool ok, const char* file, int line, const std::string& what) {
    ++checks();
    if (!ok) {
        ++failures();
        std::printf("  FAIL  %s:%d  %s\n", file, line, what.c_str());
    }
}

inline std::string f2s(double v) {
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%.6g", v);
    return std::string(buf);
}

inline int summary() {
    std::printf("\n%d checks, %d failures\n", checks(), failures());
    if (failures() == 0) std::printf("OK\n");
    return failures() == 0 ? 0 : 1;
}

} // namespace testing

#define SECTION(name) std::printf("\n== %s\n", name)

#define CHECK(cond) \
    ::testing::report((cond), __FILE__, __LINE__, "expected: " #cond)

#define CHECK_NEAR(actual, expected, tol)                                      \
    do {                                                                       \
        const double a_ = (actual), e_ = (expected), t_ = (tol);               \
        ::testing::report(std::fabs(a_ - e_) <= t_, __FILE__, __LINE__,        \
            std::string(#actual) + " = " + ::testing::f2s(a_) +                \
            ", expected " + ::testing::f2s(e_) + " +/- " + ::testing::f2s(t_));\
    } while (0)

#define CHECK_WITHIN_PERCENT(actual, expected, pct)                            \
    do {                                                                       \
        const double a_ = (actual), e_ = (expected), p_ = (pct);               \
        const double tol_ = std::fabs(e_) * p_ * 0.01;                         \
        ::testing::report(std::fabs(a_ - e_) <= tol_, __FILE__, __LINE__,      \
            std::string(#actual) + " = " + ::testing::f2s(a_) +                \
            ", expected " + ::testing::f2s(e_) + " +/- " + ::testing::f2s(p_) + "%"); \
    } while (0)
