import { animate, useInView } from "motion/react";
import { useEffect, useRef } from "react";
import { fmtNum } from "../lib/format";

/** Counts up to `value` when scrolled into view (and on every change). */
export default function AnimatedNumber({ value, format = fmtNum, duration = 1.1, className = "" }) {
  const ref = useRef(null);
  const from = useRef(0);
  const inView = useInView(ref, { once: true });

  useEffect(() => {
    if (value === null || value === undefined) return undefined;
    if (document.hidden) {
      // Background tabs get no animation frames; show the real value straight away.
      from.current = value;
      if (ref.current) ref.current.textContent = format(value);
      return undefined;
    }
    if (!inView) return undefined;
    const controls = animate(from.current, value, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => {
        from.current = v; // the displayed value, so an interrupted count resumes from where it is
        if (ref.current) ref.current.textContent = format(Number.isInteger(value) ? Math.round(v) : v);
      },
    });
    return () => controls.stop();
  }, [value, inView, duration, format]);

  return (
    <span ref={ref} className={`tabular ${className}`}>
      {format(0)}
    </span>
  );
}
