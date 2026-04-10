'use client';

interface Props {
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  pageSizes?: number[];
  onPage: (p: number) => void;
  onPageSize: (s: number) => void;
}

export default function Pagination({ page, totalPages, totalItems, pageSize, pageSizes = [10, 25, 50, 100], onPage, onPageSize }: Props) {
  if (totalItems === 0) return null;

  const pages: number[] = [];
  const delta = 2;
  for (let i = Math.max(1, page - delta); i <= Math.min(totalPages, page + delta); i++) pages.push(i);

  const btn = (label: string, target: number, disabled: boolean, active = false) => (
    <button key={label + target}
      onClick={() => !disabled && onPage(target)}
      disabled={disabled}
      className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
        active ? 'bg-indigo-600 text-white' :
        disabled ? 'text-slate-600 cursor-not-allowed' :
        'text-slate-400 hover:bg-slate-700 hover:text-white'
      }`}
    >{label}</button>
  );

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-2 px-4 py-3 border-t border-slate-700/50">
      <div className="flex items-center gap-3">
        <span className="text-slate-500 text-xs">
          {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, totalItems)} of {totalItems.toLocaleString()}
        </span>
        <select value={pageSize} onChange={e => { onPageSize(Number(e.target.value)); onPage(1); }}
          className="px-2 py-1 bg-slate-800 border border-slate-600 text-white text-xs rounded focus:outline-none">
          {pageSizes.map(s => <option key={s} value={s}>{s} / page</option>)}
        </select>
      </div>
      <div className="flex gap-1">
        {btn('«', 1, page === 1)}
        {btn('‹', page - 1, page === 1)}
        {page - delta > 1 && <span className="text-slate-600 px-1 text-xs self-center">…</span>}
        {pages.map(p => btn(String(p), p, false, p === page))}
        {page + delta < totalPages && <span className="text-slate-600 px-1 text-xs self-center">…</span>}
        {btn('›', page + 1, page === totalPages)}
        {btn('»', totalPages, page === totalPages)}
      </div>
    </div>
  );
}
