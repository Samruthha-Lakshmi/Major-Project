import { AnimatePresence, motion, useMotionValue, useSpring } from "motion/react";
import { Archive, BookOpen, Newspaper, Radio } from "lucide-react";
import { useEffect } from "react";
import { NavLink, Link, useLocation } from "react-router-dom";
import { useFeed } from "../hooks/useFeed";
import Ticker from "./Ticker";

const NAV = [
  { to: "/", label: "Studio", icon: Newspaper, end: true },
  { to: "/live", label: "Live Desk", icon: Radio },
  { to: "/archive", label: "Archive", icon: Archive },
  { to: "/method", label: "Method", icon: BookOpen },
];

function CursorGlow() {
  const x = useMotionValue(-400);
  const y = useMotionValue(-400);
  const sx = useSpring(x, { stiffness: 60, damping: 20 });
  const sy = useSpring(y, { stiffness: 60, damping: 20 });
  useEffect(() => {
    const move = (e) => {
      x.set(e.clientX - 300);
      y.set(e.clientY - 300);
    };
    window.addEventListener("pointermove", move);
    return () => window.removeEventListener("pointermove", move);
  }, [x, y]);
  return (
    <motion.div
      aria-hidden
      style={{ x: sx, y: sy }}
      className="pointer-events-none fixed left-0 top-0 z-0 h-[600px] w-[600px] rounded-full bg-[radial-gradient(circle,rgba(255,90,54,0.07),transparent_60%)]"
    />
  );
}

export default function Layout({ children }) {
  const { connected, health } = useFeed();
  const location = useLocation();

  return (
    <div className="grain relative min-h-screen overflow-x-hidden">
      <div aria-hidden className="grid-bg pointer-events-none absolute inset-x-0 top-0 h-[720px]" />
      <CursorGlow />

      <header className="sticky top-0 z-40 border-b border-line bg-ink/75 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-[1400px] items-center gap-4 px-4 sm:px-6">
          <Link to="/" className="group flex items-center gap-2.5">
            <motion.div
              whileHover={{ rotate: -8, scale: 1.06 }}
              className="grid h-9 w-9 place-items-center rounded-xl border border-line-2 bg-panel-2"
            >
              <svg viewBox="0 0 32 32" className="h-5 w-5">
                <path d="M8 22V10h6a6 6 0 0 1 0 12H8z" fill="none" stroke="#ecebe7" strokeWidth="2.6" />
                <circle cx="23.5" cy="21.5" r="3" fill="#ff5a36" />
              </svg>
            </motion.div>
            <div className="leading-tight">
              <div className="font-serif text-[19px] font-extrabold tracking-tight">
                The Data <span className="text-accent">Desk</span>
              </div>
              <div className="kicker hidden !text-[9.5px] sm:block">Automated data journalism</div>
            </div>
          </Link>

          <nav className="ml-auto flex items-center gap-1 rounded-full border border-line bg-panel/60 p-1">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} className="relative">
                {({ isActive }) => (
                  <span
                    className={`relative z-10 flex items-center gap-2 rounded-full px-3 py-1.5 text-[13px] font-medium transition-colors sm:px-4 ${
                      isActive ? "text-ink" : "text-muted hover:text-text"
                    }`}
                  >
                    {isActive && (
                      <motion.span
                        layoutId="nav-pill"
                        className="absolute inset-0 -z-10 rounded-full bg-text"
                        transition={{ type: "spring", stiffness: 420, damping: 34 }}
                      />
                    )}
                    <Icon size={15} strokeWidth={2.2} />
                    <span className="hidden md:inline">{label}</span>
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="hidden items-center gap-3 lg:flex">
            {health?.llm_available && (
              <span className="rounded-full border border-violet/30 bg-violet/10 px-2.5 py-1 font-mono text-[10.5px] text-violet">
                Claude ready
              </span>
            )}
            <span className="flex items-center gap-2 font-mono text-[11px] text-muted">
              <span className="relative flex h-2 w-2">
                {connected && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-teal opacity-60" />}
                <span className={`relative inline-flex h-2 w-2 rounded-full ${connected ? "bg-teal" : "bg-dim"}`} />
              </span>
              {connected ? "LIVE" : "OFFLINE"}
            </span>
          </div>
        </div>
        <Ticker />
      </header>

      <AnimatePresence mode="wait">
        <motion.main
          key={location.pathname.split("/")[1] || "home"}
          initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          exit={{ opacity: 0, y: -10, filter: "blur(6px)" }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 mx-auto max-w-[1400px] px-4 pb-24 pt-8 sm:px-6"
        >
          {children}
        </motion.main>
      </AnimatePresence>

      <footer className="relative z-10 border-t border-line py-8">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3 px-4 text-[12px] text-dim sm:px-6">
          <span>Automated Data Journalism Pipeline for Statistical Analysis and HTML News Report Generation</span>
          <span className="font-mono">v{health?.version ?? "1.0.0"} · Dhanalakshmi College of Engineering · AI &amp; DS</span>
        </div>
      </footer>
    </div>
  );
}
