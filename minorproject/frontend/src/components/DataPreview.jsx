import { motion } from "motion/react";
import { SEMANTIC_COLOR } from "../lib/format";

/** Inferred schema chips and the first rows of the raw dataset. */
export default function DataPreview({ preview, schema }) {
  if (!preview && !schema) return null;
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="kicker">Inferred schema</span>
        {schema && <span className="font-mono text-[11px] text-dim">{schema.length} columns</span>}
      </div>
      {schema && (
        <div className="flex flex-wrap gap-1.5 p-3">
          {schema.map((c, i) => (
            <motion.span
              key={c.name}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.03 }}
              className="flex items-center gap-1.5 rounded-lg border border-line bg-panel-2 px-2 py-1 text-[11.5px]"
              title={`${c.semantic}${c.missing ? ` · ${c.missing} missing` : ""}`}
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: SEMANTIC_COLOR[c.semantic] }} />
              <span className="max-w-[140px] truncate">{c.name}</span>
              <span className="font-mono text-[10px] text-dim">{c.semantic}</span>
            </motion.span>
          ))}
        </div>
      )}
      {preview && (
        <div className="max-h-[260px] overflow-auto border-t border-line">
          <table className="w-full text-left font-mono text-[11px]">
            <thead className="sticky top-0 bg-panel-2">
              <tr>
                {preview.columns.map((c) => (
                  <th key={c} className="whitespace-nowrap px-3 py-2 font-medium text-muted">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((r, i) => (
                <tr key={i} className="border-t border-line/60">
                  {r.map((v, j) => (
                    <td key={j} className="max-w-[180px] truncate whitespace-nowrap px-3 py-1.5 text-text/80">
                      {v === null ? <span className="text-dim">null</span> : String(v)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </motion.div>
  );
}
