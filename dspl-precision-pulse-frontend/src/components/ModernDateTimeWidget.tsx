import { useEffect, useState } from 'react';

export default function ModernDateTimeWidget() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  if (!now) return null;

  const h24 = now.getHours();
  const min = now.getMinutes();
  const sec = now.getSeconds();
  const period = h24 >= 12 ? 'PM' : 'AM';
  const h12 = h24 % 12 || 12;
  const pad = (n: number) => String(n).padStart(2, '0');

  const day  = now.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase();
  const date = now.toLocaleDateString('en-US', { day: '2-digit', month: 'short' }).toUpperCase();

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 rounded-2xl border border-indigo-500/20 bg-slate-800/70 backdrop-blur-sm shadow-lg">
      {/* Date pill */}
      <div className="flex flex-col items-center leading-tight">
        <span className="text-indigo-400 font-bold text-[10px] tracking-widest">{day}</span>
        <span className="text-white font-semibold text-xs">{date}</span>
      </div>

      {/* Divider */}
      <div className="w-px h-8 bg-slate-600/60" />

      {/* Time */}
      <div className="flex items-baseline gap-1">
        <span className="text-white font-bold text-2xl tabular-nums leading-none tracking-tight">
          {pad(h12)}:{pad(min)}
        </span>
        <div className="flex flex-col items-start leading-none gap-0.5">
          <span className="text-indigo-400 font-bold text-[9px] tracking-wide">{period}</span>
          <span className="text-slate-400 font-semibold text-[10px] tabular-nums">{pad(sec)}s</span>
        </div>
      </div>
    </div>
  );
}
