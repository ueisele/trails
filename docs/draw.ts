import { loadRenderer } from "/home/eiseleu/repositories/weather-cards/scripts/lib/renderer"
const { Canvas, encodePng } = await loadRenderer()

type Rgb = readonly [number, number, number]
const GROUND: Rgb = [17, 22, 28]
const STONE: Rgb = [226, 232, 238]
const STONE2: Rgb = [150, 163, 176]
const WARM: Rgb = [217, 89, 38]
const COOL: Rgb = [57, 135, 229]
const MOSS: Rgb = [58, 158, 112]

/** A flattened stone. `band` takes a vertical span per column, which is what makes a smooth
 *  organic outline possible at all with this rasteriser — a rounded rect leaves visible seams. */
function stone(c: any, cx: number, cy: number, w: number, h: number, tilt: number, tone: Rgb) {
  const points: [number, number, number][] = []
  const steps = Math.max(24, Math.round(w))
  for (let i = 0; i <= steps; i++) {
    const t = i / steps
    const x = cx - w / 2 + w * t
    const k = Math.sqrt(Math.max(0, 1 - Math.pow(2 * t - 1, 2)))
    const mid = cy + tilt * (t - 0.5)
    points.push([x, mid - h / 2 * k, mid + h / 2 * k])
  }
  c.band(points, tone, 1)
}

/** A cairn: stones of unequal size, each set a little off the one below, narrowing upward. Built
 *  rather than printed is the whole difference between a waymark and a wedding cake. */
function cairn(c: any, s: number, cx: number, base: number, height: number, tone: Rgb, tone2: Rgb) {
  const stones = [
    { w: 0.64, h: 0.150, dx: 0.000, tilt: 0.020 },
    { w: 0.50, h: 0.135, dx: 0.045, tilt: -0.030 },
    { w: 0.40, h: 0.125, dx: -0.040, tilt: 0.025 },
    { w: 0.28, h: 0.110, dx: 0.030, tilt: -0.015 },
    { w: 0.17, h: 0.090, dx: -0.010, tilt: 0.010 },
  ]
  let y = base
  stones.forEach((st, i) => {
    const w = height * st.w, h = height * st.h
    y -= h / 2
    stone(c, cx + height * st.dx, y, w, h, height * st.tilt, i % 2 ? tone2 : tone)
    y -= h / 2 - height * 0.012
  })
  return y
}

function icon(kind: "almanac" | "atlas", size: number, style: number) {
  const c = new Canvas(size, size, GROUND)
  const cx = size * 0.5
  const base = size * (kind === "atlas" ? 0.80 : 0.855)
  const height = size * 0.88

  // **The pair is an arc above and a path below.** Same weight, same stroke, opposite side of the
  // same cairn: one site is what the sky is doing, the other is where the ground goes.
  if (kind === "atlas") {
    const stroke = Math.max(1.8, size * 0.045)
    let prev: [number, number] | undefined
    for (let step = 0; step <= 100; step++) {
      const t = step / 100
      const p: [number, number] = [size * 0.06 + size * 0.88 * t,
        size * 0.905 + size * 0.055 * Math.sin(t * Math.PI * 1.7 - 0.6)]
      if (prev) c.line(prev[0], prev[1], p[0], p[1], MOSS, stroke)
      prev = p
    }
  } else {
    const stroke = Math.max(1.8, size * 0.045)
    let prev: [number, number] | undefined
    for (let step = 0; step <= 100; step++) {
      const t = step / 100
      const p: [number, number] = [size * 0.11 + size * 0.78 * t,
        size * 0.285 - size * 0.105 * Math.sin(t * Math.PI)]
      if (prev) c.line(prev[0], prev[1], p[0], p[1], WARM, stroke)
      prev = p
    }
  }
  cairn(c, size, cx, base, height, STONE, STONE2)
  return encodePng(c)
}

for (const [name, kind, style] of [
  ["almanac", "almanac", 0], ["atlas", "atlas", 0],
] as const) {
  for (const size of [512, 192, 180]) {
    await Bun.write(`/tmp/icons/${name}-${size}.png`, icon(kind, size, style))
  }
}
console.log("gezeichnet")
