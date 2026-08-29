// maloSound provenance companion
// source_name: example-take.wav
// source_id: 98092f2d46a9ab08
// source_hash: 98092f2d46a9ab08bb3bc9f8e8ea2f3be0f2d26298dad811ae9dbfff36a45b32
// Generated deterministically from AudioAnalysisV1. Edit only after re-hashing.

setcpm(30)

stack(
  s("bd ~ bd bd").bank("RolandTR909").gain(0.9),
  s("~ clap ~ sd").bank("RolandTR909").gain(0.55),
  s("[~ hh]*4").bank("RolandTR909").gain(0.32),
  note("c2 bb1 ~ g1").s("sawtooth").lpf(520).gain(0.38)
)
