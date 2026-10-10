import { OneEuro } from './src/gesture/oneEuro.ts';

const FRAME = 1 / 60;
function jitter(centre: number, amplitude: number, frames: number): number[] {
  let seed = 0x9e3779b9;
  const next = (): number => {
    seed ^= seed << 13; seed >>>= 0;
    seed ^= seed >>> 17;
    seed ^= seed << 5; seed >>>= 0;
    return seed / 0x100000000;
  };
  return Array.from({ length: frames }, () => centre + (next() * 2 - 1) * amplitude);
}
const spread = (xs: number[]) => Math.max(...xs) - Math.min(...xs);

const input = jitter(300, 4, 240);
for (const beta of [0, 0.012]) {
  const f = new OneEuro(1.1, beta);
  const out = input.map((v, i) => f.filter(v, i * FRAME));
  console.log(`beta=${beta}  in=${spread(input).toFixed(3)}  out=${spread(out.slice(60)).toFixed(3)}  ratio=${(spread(input) / spread(out.slice(60))).toFixed(2)}x  final=${out[239].toFixed(3)}`);
}
const ramp = (beta: number): number => {
  const f = new OneEuro(1.1, beta);
  let out = 0;
  for (let i = 0; i < 30; i++) out = f.filter(i * 10, i * FRAME);
  return out;
};
console.log(`ramp target=290  beta=0 -> ${ramp(0).toFixed(2)}  beta=0.012 -> ${ramp(0.012).toFixed(2)}  ratio=${(ramp(0.012) / ramp(0)).toFixed(2)}x`);