import { motion } from "motion/react";
import { Download, ExternalLink, FileJson, WifiOff } from "lucide-react";
import { reportUrl } from "../lib/api";

/** The published HTML report: a framed live preview plus export actions. */
export default function ReportPanel({ runId }) {
  const actions = [
    { href: reportUrl(runId), label: "Open report", icon: ExternalLink, target: "_blank" },
    { href: reportUrl(runId, { download: true }), label: "Download HTML", icon: Download },
    { href: reportUrl(runId, { offline: true, download: true }), label: "Offline version", icon: WifiOff },
    { href: `/api/runs/${runId}/result.json`, label: "Analysis JSON", icon: FileJson },
  ];
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {actions.map(({ href, label, icon: Icon, target }) => (
          <motion.a
            key={label}
            href={href}
            target={target}
            rel="noreferrer"
            whileHover={{ y: -2 }}
            whileTap={{ scale: 0.97 }}
            className="flex items-center gap-2 rounded-xl border border-line bg-panel-2 px-3.5 py-2 text-[13px] font-medium text-text/90 transition-colors hover:border-line-2"
          >
            <Icon size={15} />
            {label}
          </motion.a>
        ))}
      </div>
      <div className="relative overflow-hidden rounded-2xl border border-line-2 bg-[#fbf8f3] shadow-[0_30px_80px_-20px_rgba(0,0,0,0.7)]">
        <div className="flex items-center gap-2 border-b border-black/10 bg-[#efeae1] px-4 py-2">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
          <span className="ml-3 truncate font-mono text-[11px] text-black/50">{reportUrl(runId)}</span>
        </div>
        <iframe title="Generated news report" src={reportUrl(runId)} className="h-[78vh] w-full bg-[#fbf8f3]" />
      </div>
    </motion.div>
  );
}
