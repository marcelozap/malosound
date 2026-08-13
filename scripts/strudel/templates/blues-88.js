// ==========================================================
// malosound — BLUES SHUFFLE 88, key of A
// This is a PRACTICE bed, not a record. Loops forever.
//
// COPY THIS FILE. Do not edit it in place.
// ==========================================================

setcpm(88/4)

samples('github:tidalcycles/dirt-samples')


// ---------- THE SHUFFLE ----------
// [x ~ x]*4 is hit-skip-hit inside each beat = triplets.
// This one line is what makes it blues instead of rock.
// If it feels stiff, look here first.

$: s("[rd ~ rd]*4").gain(0.18).lpf(7000)

// Real recordings, not 8-bit one-shots.
$: s("stomp ~ stomp ~").lpf(400).gain(0.85).room(0.25)
   .sometimesBy(0.3, x => x.gain(0.7))

$: s("realclaps ~ realclaps ~").late(0.25).gain(0.4).room(0.35)


// ---------- THE 12 BARS ----------
// Each [ ] is one bar. Walks the changes so you don't count.
// Bar 9 jumps to E — that's your tension bar. Land strong.

$: note("<[a2 c3 e3 fs3] [a2 c3 e3 fs3] [a2 c3 e3 fs3] [a2 c3 e3 fs3] [d3 f3 a3 b3] [d3 f3 a3 b3] [a2 c3 e3 fs3] [a2 c3 e3 fs3] [e3 g3 b3 cs4] [d3 f3 a3 b3] [a2 c3 e3 fs3] [e3 g3 b3 cs4]>")
  .sound("sawtooth").lpf(500).gain(0.6)


// ==========================================================
// WHERE TO PLAY — A minor pentatonic, box 1 (5th fret)
//   e|--5--8--
//   B|--5--8--
//   G|--5--7--
//   D|--5--7--
//   A|--5--7--
//   E|--5--8--
//
// The note that turns pentatonic into BLUES: Eb.
// 6th fret A string, 8th fret high E. Bend INTO it, don't sit.
// ==========================================================

// ==========================================================
// CHANGING KEY — move all bars by the same interval.
//
//   Key of E (best open-string key on guitar):
//     I = e2 g3 b3 cs4   IV = a2 c3 e3 fs3   V = b2 d3 fs3 gs3
//   Key of G:
//     I = g2 b2 d3 e3    IV = c3 e3 g3 a3    V = d3 fs3 a3 b3
//
// Sharps: fs cs gs.  Flats: ef bf af.
// ==========================================================

// ==========================================================
// Blues wants ONE key played to death. Same 12 bars for
// twenty minutes. The phrasing comes from repetition and
// space, not from new material. Leave gaps.
// ==========================================================
