// ==========================================================
// malosound — HALF-TIME 152
// The Drake "Headlines" lane. Dark, anthemic, chest not hips.
//
// COPY THIS FILE. Do not edit it in place.
//
//   1. https://strudel.cc
//   2. Select all, delete, paste
//   3. Ctrl+Enter to play. Ctrl+. to stop.
// ==========================================================

setcpm(152/4)

samples('github:tidalcycles/dirt-samples')

// KEY: A minor. Dark without being cartoonish.
// For heavier, move everything down to F# minor.


// ---------- PARTS ----------

const drums = stack(
  // The half-time feel: kick on 1, snare on 3. Space is the point.
  s("bd ~ ~ ~").gain(1.0),
  s("~ ~ sd ~").gain(0.85).room(0.25),
  // Hats run at full speed over the slow kick. That contrast IS half-time.
  s("hh*8").gain(rand.range(0.10, 0.22)).lpf(8000),
)

const drumsFill = stack(
  s("bd ~ ~ bd").gain(1.0),
  s("~ ~ sd [sd sd]").gain(0.85),
  s("hh*16").gain(rand.range(0.08, 0.20)).lpf(9000),
)

const sub = note("a1 ~ ~ ~")
  .sound("sine").gain(0.9).attack(0.01).release(0.4)

const pad = note("<[a2,c3,e3] [a2,c3,e3] [f2,a2,c3] [g2,b2,d3]>")
  .sound("triangle")
  .attack(1.2).release(1.8).gain(0.28).room(0.65).lpf(1600)

// The hook line. Sparse on purpose — leave room for the vocal.
const lead = note("<a4 ~ c5 ~ ~ e5 ~ ~>")
  .sound("triangle")
  .delay(0.5).delaytime(0.1875).delayfeedback(0.4)
  .gain(0.26).room(0.5).lpf(5000)


// ---------- SECTIONS ----------

const intro    = stack(pad, sub.gain(0.5))
const verse    = stack(drums, sub, pad)
const hook     = stack(drums, sub, pad, lead)
const bridge   = stack(pad, lead.gain(0.2))
const outro    = stack(drumsFill, sub, pad)


// ---------- ARRANGEMENT ----------
// Numbers are bars. Change any of them, hit Ctrl+Enter,
// it re-times itself. No manual counting.

$: arrange(
  [8,  intro],
  [16, verse],
  [16, hook],
  [16, verse],
  [16, hook],
  [8,  bridge],
  [16, hook],
  [8,  outro],
)


// ==========================================================
// THE BEAT SWITCH (if you want the "who is this" moment)
//
// Bad Bunny does this constantly. Drop the last third to
// ~96 dembow. Two ways:
//
//   A) Uncomment the line below to halve the tempo live:
//        // setcpm(96/4)
//      Crude but instant.
//
//   B) Better: build the dembow section in its own file,
//      bounce both, and cut them together in Logic. A real
//      beat switch usually needs a bar of silence or a riser
//      at the seam anyway.
// ==========================================================

// ==========================================================
// FREESTYLE NOTE
// A minor is the dark lane. If you're tracking the -IDO
// Spanish verses over this, the low register of A minor sits
// under a Spanish delivery better than C major does — C is
// bright and fights the menace.
// ==========================================================
