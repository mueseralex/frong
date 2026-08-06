/** Lightweight confetti / screen-shake helpers inspired by rippacks.fun CSS ritual. */

export function shake(level = "sm") {
  document.body.classList.remove("shake-sm", "shake-lg");
  void document.body.offsetWidth;
  document.body.classList.add(level === "lg" ? "shake-lg" : "shake-sm");
  setTimeout(() => document.body.classList.remove("shake-sm", "shake-lg"), level === "lg" ? 700 : 480);
}

export function burst(canvas, x, y, colors, count = 60, power = 12) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const parts = [];
  for (let i = 0; i < count; i++) {
    const a = Math.random() * Math.PI * 2;
    const s = (0.4 + Math.random()) * power;
    parts.push({
      x,
      y,
      vx: Math.cos(a) * s,
      vy: Math.sin(a) * s - 2,
      life: 1,
      color: colors[i % colors.length],
      size: 2 + Math.random() * 4,
      rot: Math.random() * Math.PI,
      spin: (Math.random() - 0.5) * 0.3,
    });
  }

  let raf;
  const tick = () => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    let alive = false;
    for (const p of parts) {
      if (p.life <= 0) continue;
      alive = true;
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.22;
      p.vx *= 0.99;
      p.life -= 0.016;
      p.rot += p.spin;
      ctx.save();
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
      ctx.restore();
    }
    if (alive) raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(raf);
}

export function sizeCanvas(canvas) {
  if (!canvas) return;
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
}
