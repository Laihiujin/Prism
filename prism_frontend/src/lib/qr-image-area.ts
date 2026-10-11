// Locate QR finder patterns without decoding the payload (branded QR codes
// can be scannable by the official app while failing a generic decoder).
export function qrImageArea(data: Uint8ClampedArray, width: number, height: number) {
  const centers: { x: number; y: number; unit: number; hits: number }[] = []
  const black = (x: number, y: number) => {
    const i = (y * width + x) * 4
    return data[i] + data[i + 1] + data[i + 2] < 360
  }
  for (let y = 0; y < height; y += 2) {
    const runs: { start: number; size: number; dark: boolean }[] = []
    let start = 0, dark = black(0, y)
    for (let x = 1; x <= width; x++) {
      const next = x < width && black(x, y)
      if (x < width && next === dark) continue
      runs.push({ start, size: x - start, dark })
      if (runs.length > 5) runs.shift()
      if (runs.length === 5 && runs[0].dark && runs[2].dark && runs[4].dark) {
        const unit = runs.reduce((n, r) => n + r.size, 0) / 7
        if (unit >= 1.5 && runs.every((r, i) => Math.abs(r.size - unit * (i === 2 ? 3 : 1)) < unit * 0.65)) {
          const cx = runs[2].start + runs[2].size / 2
          // Confirm the same finder pattern on the vertical axis.
          const lengths: number[] = []
          let pos = y
          while (pos >= 0 && black(Math.floor(cx), pos)) pos--
          const middleTop = pos + 1
          pos = y
          while (pos < height && black(Math.floor(cx), pos)) pos++
          const middleBottom = pos
          lengths[2] = middleBottom - middleTop
          let top = middleTop - 1, bottom = middleBottom
          for (const index of [1, 0]) {
            const from = top
            while (top >= 0 && black(Math.floor(cx), top) === (index === 0)) top--
            lengths[index] = from - top
          }
          for (const index of [3, 4]) {
            const from = bottom
            while (bottom < height && black(Math.floor(cx), bottom) === (index === 4)) bottom++
            lengths[index] = bottom - from
          }
          if (lengths.every((n, i) => Math.abs(n - unit * (i === 2 ? 3 : 1)) < unit * 0.85)) {
            const cy = (middleTop + middleBottom) / 2
            const existing = centers.find(c => Math.hypot(c.x - cx, c.y - cy) < unit * 2)
            if (existing) existing.hits++
            else centers.push({ x: cx, y: cy, unit, hits: 1 })
          }
        }
      }
      start = x; dark = next
    }
  }
  const candidates = centers.filter(c => c.hits >= 2).sort((a, b) => b.hits - a.hits).slice(0, 20)
  for (const corner of candidates) for (const right of candidates) for (const below of candidates) {
    const size = right.x - corner.x
    if (size < corner.unit * 14 || below.y - corner.y < 25) continue
    if (Math.abs(right.y - corner.y) > corner.unit * 2 || Math.abs(below.x - corner.x) > corner.unit * 2) continue
    if (Math.abs(below.y - corner.y - size) > size * 0.12) continue
    if ([right, below].some(c => Math.abs(c.unit - corner.unit) > corner.unit * 0.5)) continue
    const margin = corner.unit * 7.5
    const x = Math.max(0, Math.floor(corner.x - margin)), y = Math.max(0, Math.floor(corner.y - margin))
    return { x, y, width: Math.min(width - x, Math.ceil(size + margin * 2)), height: Math.min(height - y, Math.ceil(size + margin * 2)) }
  }
  return null
}
