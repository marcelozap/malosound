// ==========================================================
// malosound — PARTS MENU
//
// This is not an import. strudel.cc cannot load a local file, so
// there is no `import { kick } from './parts.js'` to write. This is
// a menu you COPY FROM — open it beside the editor, take the block
// you want, paste it into your track's pattern.js.
//
// Every block here is lifted from a working template, so it is known
// to sound right rather than known to be syntactically valid.
//
// Everything assumes A minor. To move key, shift every note in every
// block by the same interval — see reference/keys-and-tempos.md.
// ==========================================================

samples('github:tidalcycles/dirt-samples')


// ==========================================================
// DRUMS — pick one spine, never two
// ==========================================================

// Four-on-the-floor. House, 122. Hips.
const drumsHouse = stack(
  s("bd*4").gain(0.95),
  s("~ cp ~ cp").gain(0.5).room(0.2),
  s("~ oh ~ oh").gain(0.38).lpf(9000),
  s("hh*8").gain(rand.range(0.10, 0.24)).late(rand.range(0, 0.012)),
)

// Half-time. 152. Chest.
// The kick is slow and the hats are fast — that contrast IS half-time.
// Take away the fast hats and it stops being half-time and starts being slow.
const drumsHalfTime = stack(
  s("bd ~ ~ ~").gain(1.0),
  s("~ ~ sd ~").gain(0.85).room(0.25),
  s("hh*8").gain(rand.range(0.10, 0.22)).lpf(8000),
)

// Blues shuffle. 88. [x ~ x] inside each beat = triplets.
// This one line is the whole difference between blues and rock.
const drumsShuffle = stack(
  s("[rd ~ rd]*4").gain(0.18).lpf(7000),
  s("stomp ~ stomp ~").lpf(400).gain(0.85).room(0.25),
  s("realclaps ~ realclaps ~").late(0.25).gain(0.4).room(0.35),
)

// Dembow. ~96. This is the beat-switch payload — see the note at the
// bottom of templates/halftime-152.js. Boom—ka-boom-ka.
const drumsDembow = stack(
  s("bd ~ ~ bd ~ ~ bd ~").gain(0.95),
  s("~ ~ sd ~ ~ ~ sd ~").gain(0.7).room(0.2),
  s("hh*8").gain(rand.range(0.08, 0.18)),
  s("rim(3,8)").gain(0.3).pan(0.65),
)


// ==========================================================
// LATIN PERCUSSION — euclidean. The signature layer.
//
// Change the two numbers and you find grooves you have not heard.
// (3,8) is the tresillo and it is the backbone of nearly all of it.
// Add this OVER any spine above. It is what makes house Latin house.
// ==========================================================

const percLatin = stack(
  s("bongo(3,8)").gain(0.32).pan(0.7),
  s("conga(5,8)").gain(0.28).pan(0.3),
  s("cabasa(7,16)").gain(0.18).pan(sine.range(0.4, 0.6).slow(8)),
)

// Sparser — for when the guitar is doing the rhythmic work.
const percSparse = stack(
  s("bongo(3,8)").gain(0.22).pan(0.7),
  s("cabasa(7,16)").gain(0.14).pan(0.45),
)

// Son clave, the 3-2. Ancient, and it will carry a whole section alone.
const clave = s("rim(3,8,0)").gain(0.35).pan(0.5)


// ==========================================================
// BASS
// ==========================================================

// Sub. One note, huge, gets out of the way. Half-time wants this.
const bassSub = note("a1 ~ ~ ~")
  .sound("sine").gain(0.9).attack(0.01).release(0.4)

// Driving house bass with a slow filter sweep — the sweep is what stops
// eight bars of the same note from getting boring.
const bassHouse = note("a1 [~ a1] c2 ~")
  .sound("sawtooth")
  .lpf(sine.range(300, 1400).slow(8))
  .gain(0.7)

// Octave pump. Obvious, effective, do not overuse.
const bassOctave = note("<a1 a2>*8")
  .sound("sawtooth").lpf(800).gain(0.6).release(0.1)


// ==========================================================
// HARMONY
// ==========================================================

const stabHouse = note("~ [a3,c4,e4] ~ [a3,c4,e4]")
  .sound("sawtooth")
  .lpf(2200).attack(0.005).release(0.15).gain(0.32).room(0.3)

const padDark = note("<[a2,c3,e3] [a2,c3,e3] [f2,a2,c3] [g2,b2,d3]>")
  .sound("triangle")
  .attack(1.2).release(1.8).gain(0.28).room(0.65).lpf(1600)

const padWide = note("<[a2,c3,e3] [f2,a2,c3]>")
  .sound("triangle")
  .attack(1.5).release(2).gain(0.24).room(0.6).lpf(1800).slow(4)


// ==========================================================
// THE EDGE DELAY
//
// The "Beautiful Day" trick, and it is not a pedal setting — it is a
// rhythm. A dotted-eighth delay turns a plain quarter-note line into a
// cascade, because the repeats land in the gaps instead of on the notes.
//
// delaytime is in CYCLES, and one cycle is four beats:
//     eighth         = 0.125
//     dotted eighth  = 0.1875   <- this one
//     quarter        = 0.25
//
// Two rules or it turns to mud:
//   1. Play FEWER notes than feels right. The delay fills the rest.
//   2. Feedback under ~0.45. Above that the repeats stack and smear.
//
// This block is here so the backing track can do it too — but the real
// use is the same setting on the actual guitar chain.
// ==========================================================

const leadEdge = note("<a4 ~ c5 ~ ~ e5 ~ ~>")
  .sound("triangle")
  .delay(0.5).delaytime(0.1875).delayfeedback(0.4)
  .gain(0.26).room(0.5).lpf(5000)

// Arpeggio version — more Fray than U2. Notes deliberately sparse.
const leadArp = note("<a4 e5 c5 e5>")
  .sound("triangle")
  .delay(0.45).delaytime(0.1875).delayfeedback(0.35)
  .gain(0.22).room(0.55).lpf(4500)


// ==========================================================
// LEAVING ROOM FOR THE GUITAR
//
// The backing track's job is to not be where the guitar is. Guitar
// lives roughly 800 Hz - 3 kHz, and everything that fights it there
// makes you play louder, which makes it worse.
//
// Applied to any pattern: scoop the guitar's range out of the pads and
// stabs rather than turning them down. Turning them down loses the part;
// filtering keeps the part and frees the space.
// ==========================================================

const guitarPocket = x => x.lpf(700).gain(0.9)      // keep it under the guitar
const guitarSpace  = x => x.hpf(3200).gain(0.9)     // or keep it above

// Usage:  guitarPocket(padDark)
//         stack(drumsHalfTime, bassSub, guitarPocket(padDark))


// ==========================================================
// QUICK TEST — uncomment one line to audition a block.
// ==========================================================

// $: drumsHalfTime
// $: stack(drumsHouse, percLatin)
// $: stack(drumsHalfTime, bassSub, guitarPocket(padDark), leadEdge)
