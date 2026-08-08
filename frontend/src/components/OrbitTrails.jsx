import { useEffect, useRef } from "react";

/**
 * Orbit Trails — canvas-2d.
 * Thin arcs of light circling a shared center, like star trails in a long
 * exposure: inner orbits whip, outer ones glide.
 */
export default function OrbitTrails({
  colors = ["#8f7bff", "#5b6cff", "#c96af2"],
  background = "#0f1013",
  speed = 1.0,
  trails = 80,
  className = "orbit-canvas",
}) {
  const canvasRef = useRef(null);
  const rafRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0, height = 0, cx = 0, cy = 0, dpr = 1;
    const hexToRgb = (h) => {
      const m = h.replace("#", "");
      return { r: parseInt(m.slice(0, 2), 16), g: parseInt(m.slice(2, 4), 16), b: parseInt(m.slice(4, 6), 16) };
    };
    const bg = hexToRgb(background);
    // Longer trails => lower clear alpha. trails 0..100 -> alpha ~0.28..0.02
    const fade = Math.max(0.02, 0.28 - (Math.min(100, Math.max(0, trails)) / 100) * 0.26);

    const particles = [];
    const build = () => {
      particles.length = 0;
      const maxR = Math.hypot(width, height) * 0.52;
      const minR = Math.min(width, height) * 0.05;
      const count = Math.round(Math.min(180, Math.max(70, (width * height) / 14000)));
      for (let i = 0; i < count; i++) {
        const t = Math.pow(Math.random(), 0.7); // bias toward inner
        const r = minR + t * (maxR - minR);
        // inner whip, outer glide: angular speed falls off with radius
        const w = (0.9 * (minR / r) + 0.05) * (Math.random() > 0.5 ? 1 : -1);
        const c = colors[i % colors.length];
        particles.push({
          r,
          a: Math.random() * Math.PI * 2,
          w,
          size: 0.6 + Math.random() * 1.8,
          color: hexToRgb(c),
          alpha: 0.35 + Math.random() * 0.55,
        });
      }
    };

    const resize = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      cx = width / 2;
      cy = height / 2;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = `rgb(${bg.r},${bg.g},${bg.b})`;
      ctx.fillRect(0, 0, width, height);
      build();
    };

    const draw = () => {
      // fade previous frame to leave trails
      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = `rgba(${bg.r},${bg.g},${bg.b},${fade})`;
      ctx.fillRect(0, 0, width, height);
      // additive glowing dots
      ctx.globalCompositeOperation = "lighter";
      for (const p of particles) {
        p.a += p.w * 0.02 * speed;
        const x = cx + Math.cos(p.a) * p.r;
        const y = cy + Math.sin(p.a) * p.r * 0.62; // slight ellipse for depth
        const { r, g, b } = p.color;
        ctx.beginPath();
        ctx.fillStyle = `rgba(${r},${g},${b},${p.alpha})`;
        ctx.shadowColor = `rgba(${r},${g},${b},0.9)`;
        ctx.shadowBlur = 8;
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowBlur = 0;
      rafRef.current = requestAnimationFrame(draw);
    };

    resize();
    window.addEventListener("resize", resize);
    if (reduced) {
      // static single frame
      ctx.globalCompositeOperation = "lighter";
      for (const p of particles) {
        const x = cx + Math.cos(p.a) * p.r;
        const y = cy + Math.sin(p.a) * p.r * 0.62;
        const { r, g, b } = p.color;
        ctx.fillStyle = `rgba(${r},${g},${b},${p.alpha})`;
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      rafRef.current = requestAnimationFrame(draw);
    }

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [colors, background, speed, trails]);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
}
