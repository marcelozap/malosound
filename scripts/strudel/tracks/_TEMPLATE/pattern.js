// ==========================================================
// <song name>
//
// Do not write the song here. Copy the closest template over the
// top of this file:
//
//     templates/halftime-152.js   dark, anthemic, chest
//     templates/house-122.js      Latin house, hips
//     templates/blues-88.js       practice bed, not a record
//
// Then change it until it is not the template any more. Pull extra
// parts from lib/parts.js as you need them.
//
// Fill in notes.md FIRST. A pattern with no notes.md becomes an
// anonymous loop within a week.
//
//   1. https://strudel.cc
//   2. Select all, delete, paste this file
//   3. Ctrl+Enter to play. Ctrl+. to stop.
// ==========================================================

setcpm(120 / 4)

samples('github:tidalcycles/dirt-samples')

$: s("bd ~ ~ ~").gain(0.9)

// ^ placeholder so the file plays something. Delete it.
