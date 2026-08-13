// ==========================================================
// malosound — LATIN HOUSE 122
// Machine precision + Latin percussion. The dance lane.
//
// COPY THIS FILE. Do not edit it in place.
// ==========================================================

setcpm(122/4)

samples('github:tidalcycles/dirt-samples')

// KEY: A minor.  For F minor: f1 / af1 / c2  (sharps fs cs gs, flats ef bf af)


// ---------- PARTS ----------

const kick   = s("bd*4").gain(0.95)
const clap   = s("~ cp ~ cp").gain(0.5).room(0.2)
const ohat   = s("~ oh ~ oh").gain(0.38).lpf(9000)
const chat   = s("hh*8").gain(rand.range(0.10, 0.24)).late(rand.range(0, 0.012))

// Latin percussion — euclidean. This is the signature.
// Change the two numbers and you find grooves you haven't heard.
const perc   = stack(
  s("bongo(3,8)").gain(0.32).pan(0.7),
  s("conga(5,8)").gain(0.28).pan(0.3),
  s("cabasa(7,16)").gain(0.18).pan(sine.range(0.4, 0.6).slow(8)),
)

const bass   = note("a1 [~ a1] c2 ~")
  .sound("sawtooth")
  .lpf(sine.range(300, 1400).slow(8))
  .gain(0.7)

const stab   = note("~ [a3,c4,e4] ~ [a3,c4,e4]")
  .sound("sawtooth")
  .lpf(2200).attack(0.005).release(0.15).gain(0.32).room(0.3)

const pad    = note("<[a2,c3,e3] [f2,a2,c3]>")
  .sound("triangle")
  .attack(1.5).release(2).gain(0.24).room(0.6).lpf(1800).slow(4)


// ---------- SECTIONS ----------

const intro    = stack(chat, perc.gain(0.2), pad)
const build    = stack(kick, chat, perc, bass.gain(0.4))
const groove   = stack(kick, clap, chat, ohat, perc, bass)
const full     = stack(kick, clap, chat, ohat, perc, bass, stab, pad)
const breakdwn = stack(perc, pad, stab.gain(0.2))
const outro    = stack(kick.gain(0.7), perc, pad)


// ---------- ARRANGEMENT ----------

$: arrange(
  [8,  intro],
  [8,  build],
  [16, groove],
  [16, full],
  [8,  breakdwn],
  [16, full],
  [8,  outro],
)
// 80 bars, then back to the top. Forever.


// ---------- JAM MODE ----------
// To play instead of arrange: comment out the arrange block
// above and uncomment this. Swap the section name live.

// $: full
