# Strudel cheatsheet

## Structure
```
stack(a, b, c)          play together
arrange([n, pat], ...)  song structure, auto-advancing. n = bars
setcpm(bpm/4)           tempo. ALWAYS divide by 4
hush()                  kill everything
$:                      play this pattern
_$:                     mute this pattern (underscore prefix)
```

## Mini-notation
```
"bd sd"        two events in one cycle
"bd*4"         four times
"bd ~ sd ~"    ~ is a rest
"[bd sd]"      squeeze into one slot
"<a b c>"      one per cycle, rotating
"a,c,e"        simultaneous (a chord)
"bd(3,8)"      euclidean: 3 hits over 8 slots
```

## Euclidean rhythms — the fastest way to find a new groove
```
(3,8)   tresillo — the Latin backbone
(5,8)   cinquillo
(7,16)  sparse, good for shakers
(2,5)   odd, unsettling
```

## Transformations
```
.fast(2) / .slow(4)
.every(4, x => x.fast(2))
.sometimesBy(0.4, x => x.speed(2))
.degradeBy(0.3)          drop 30% of hits at random
.mask("<1 1 1 0>")       silence on the 4th cycle
.late(0.02)              nudge late — makes it human
.cut(1)                  choke previous hit in group 1
.rev() / .palindrome()
```

## Sound shaping
```
.gain(0.5)               volume
.lpf(2000) / .hpf(200)   filters
.room(0.4)               reverb
.delay(0.5).delaytime(0.1875).delayfeedback(0.4)
.pan(0.3)                0 = left, 1 = right
.attack() .release()     envelope
.speed(2)                pitch + rate of a sample
```

## Modulators (put anywhere a number goes)
```
sine.range(300, 8000).slow(16)
rand.range(0.1, 0.3)
perlin.range(0, 1).slow(8)
```

## Samples — the thing that fixed the "kid's game" sound
`bd`, `cp`, `perc` are 8-bit-era one-shots. Thin plastic character is
baked in — filtering won't save them. These are real recordings:

```
stomp       real foot stomps on wood
realclaps   recorded hands
hh27        real hi-hat
gretsch     full acoustic kit
jazz        full acoustic kit, brushes
```

Every folder has numbered variants: `stomp:1`, `stomp:2`. Open the
**SOUNDS tab** in the right panel and audition them.

## When it stops playing mid-session
In order of likelihood:
1. Soundfont failed to load → swap to `.sound("sawtooth")`. This is why
   every template here uses synths, not `gm_` sounds
2. CPU overload → delete the `.room()` calls, most expensive thing
3. Sample name doesn't exist → check SOUNDS tab
4. Browser tab throttled in background → keep it focused

Open the console (Cmd+Option+J) when it dies. The error names the line.
