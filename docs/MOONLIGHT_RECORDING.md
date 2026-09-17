# Optional background listening

User-supplied recording added on 2026-09-17.

- Work: Ludwig van Beethoven, Piano Sonata No. 14, Op. 27 No. 2, third movement (Presto).
- Performer, from the uploaded MP3 tags: Paul Pitman.
- Original file: `816_sonata_no_14_in_c_sharp_minor_moonlight_op_27_no_2_-_iii_presto-db0da312-e462-447d-a7cb-c70ab4779363.mp3`.
- Website copy: `assets/beat-room/moonlight-presto-paul-pitman.mp3`.
- File size: 15,785,980 bytes. ffprobe duration: 493.175875 seconds.
- No transcoding or changes to the user's recording.

## Rights reference

https://commons.wikimedia.org/wiki/File:Moonlight_Sonata_Presto.ogg

The source identifies the same composition, movement, and performer. It states
that Paul Pitman released the recording into the public domain worldwide, with
a fallback grant permitting any purpose if public-domain dedication is not
legally possible. Wikimedia lists permission ticket 2008012110017088. It also
identifies the composition as public domain. Checked 2026-09-17.

The uploaded MP3 was identified by its embedded metadata, not by a byte-for-byte
comparison with Wikimedia's Ogg file. This document does not claim those files
are identical. The page keeps a visible performer credit and rights-source link.

Original Musopen work page:
https://musopen.org/music/2547-piano-sonata-no-14-in-c-sharp-minor-moonlight-sonata-op-27-no-2/

## Behavior

Optional native audio player above the groove library. No autoplay, preload
disabled, initial volume 18%, looping enabled. User must explicitly start it.
By default, starting the beat pauses background listening, and starting
background listening stops a running beat. The optional "Layer with beat"
checkbox lets both play together with their existing independent volumes.
Layering does not synchronize tempo or time-stretch either source. Turning
layering off pauses the piano if the beat is running. Starting a take or an
export always pauses background listening, even with layering enabled.
Background listening never starts or resumes automatically.

The player is not connected to the beat engine, offline WAV renderer, or
microphone recording destination. The MP3 is not included in exported beats or
the digital recording mix. As with any audio through speakers, a physical
microphone can pick up room sound; use headphones.

Local addition only. No new playback tests, build, commit, or deployment were
performed for this addition.
