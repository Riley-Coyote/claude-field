// from pencil — a toy chingolo from a few pencil marks.
// The source is a self-sustained oscillator (van der Pol), standing in for the
// syringeal labia: "pressure" decides whether it sounds at all, "tension" sets
// its pitch. In the spirit of Mindlin's models, not their equations.

const SR = 44100;

// A song is a list of marks, as a pencil would write them.
//   {kind:'rise'|'fall'|'flat', lo, hi, dur}  — an introductory whistle (Hz, s)
//   {kind:'trill', lo, hi, n, gap}           — n descending syllables, gap = interval (s)
function gestures(song) {
  // turn marks into a timeline of segments: [t0, t1, f0, f1, on]
  const segs = []; let t = 0.05;
  for (const m of song) {
    if (m.kind === 'trill') {
      const syl = Math.min(0.6 * m.gap, 0.05);
      for (let i = 0; i < m.n; i++) {
        segs.push([t, t + syl, m.hi, m.lo, 1]);
        t += m.gap;
      }
      t += 0.05;
    } else {
      const f0 = m.kind === 'rise' ? m.lo : m.hi;
      const f1 = m.kind === 'fall' ? m.lo : m.kind === 'rise' ? m.hi : m.hi;
      segs.push([t, t + m.dur, f0, f1, 1]);
      t += m.dur + 0.07;
    }
  }
  return { segs, total: t + 0.1 };
}

function sing(song) {
  const { segs, total } = gestures(song);
  const N = Math.floor(total * SR);
  const out = new Float32Array(N);
  const freq = new Float32Array(N); // the instruction, kept for drawing
  // per-sample instruction
  let si = 0;
  for (let i = 0; i < N; i++) {
    const t = i / SR;
    while (si < segs.length && t > segs[si][1]) si++;
    if (si < segs.length && t >= segs[si][0]) {
      const [a, b, f0, f1] = segs[si];
      const u = (t - a) / (b - a);
      freq[i] = f0 * Math.pow(f1 / f0, u); // glides are log-linear
    } else freq[i] = 0;
  }
  // the labia: x'' - mu(beta - x^2) x' + w^2 x = 0, with a little damping when beta<0
  let x = 1e-3, v = 0, beta = -1, w = 2 * Math.PI * 4000, env = 0;
  const sub = 8, dt = 1 / (SR * sub);
  for (let i = 0; i < N; i++) {
    const target = freq[i] > 0 ? 1 : -1;
    beta += (target - beta) * 0.004;           // pressure can't jump
    if (freq[i] > 0) w += (2 * Math.PI * freq[i] - w) * 0.02; // nor can tension
    for (let s = 0; s < sub; s++) {
      const mu = 0.06 * w;                       // scaled so onset takes ~ a few ms
      const a = mu * (beta - x * x) * v - w * w * x;
      v += a * dt; x += v * dt;
    }
    if (Math.abs(x) < 1e-6 && beta > 0) x = 1e-4;  // a breath of noise to restart
    out[i] = x;
  }
  // light normalisation + soft edges
  let peak = 1e-9; for (const s of out) peak = Math.max(peak, Math.abs(s));
  for (let i = 0; i < N; i++) out[i] = 0.8 * out[i] / peak;
  return { out, freq, total, segs };
}

// what the oscillator actually did: frequency from zero crossings
function track(out, win = 0.004) {
  const W = Math.floor(win * SR), pts = [];
  for (let i = 0; i + W < out.length; i += W) {
    let zc = 0, e = 0;
    for (let j = i + 1; j < i + W; j++) {
      if ((out[j - 1] < 0) !== (out[j] < 0)) zc++;
      e += out[j] * out[j];
    }
    pts.push([i / SR, zc / 2 / win, Math.sqrt(e / W)]);
  }
  return pts;
}

// Two versions of one song. The pencil marks are invented in the shape the
// articles describe (2–4 whistles, then a descending trill, about two seconds);
// the only real fact encoded is the difference between them.
const TUTOR = [
  { kind: 'flat', lo: 4200, hi: 4200, dur: 0.22 },
  { kind: 'fall', lo: 3400, hi: 5600, dur: 0.20 },
  { kind: 'rise', lo: 3600, hi: 6000, dur: 0.20 },
  { kind: 'fall', lo: 3300, hi: 5200, dur: 0.20 },
  { kind: 'trill', lo: 3000, hi: 5000, n: 7, gap: 0.075 },
];
// what the young birds made of it: the final falling syllable spans more,
// as every adult in the park already sang it.
const LEARNED = TUTOR.map((m, i) => i === 3 ? { ...m, lo: 2600, hi: 6400 } : m);

if (typeof module !== 'undefined') module.exports = { sing, track, TUTOR, LEARNED, SR, gestures };
