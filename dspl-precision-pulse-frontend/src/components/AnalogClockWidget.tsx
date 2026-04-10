import { useEffect, useState } from 'react';

interface Marker {
  x1?: number;
  y1?: number;
  x2?: number;
  y2?: number;
  x?: number;
  y?: number;
}

export default function AnalogClockWidget() {
  const [time, setTime] = useState<{ hours: number; minutes: number; seconds: number }>({
    hours: 0,
    minutes: 0,
    seconds: 0
  });
  const [date, setDate] = useState<{ date: string; day: string }>({
    date: '',
    day: ''
  });

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      
      setTime({
        hours: now.getHours() % 12,
        minutes: now.getMinutes(),
        seconds: now.getSeconds()
      });

      setDate({
        date: now.toLocaleDateString('en-US', { month: 'short', day: '2-digit' }),
        day: now.toLocaleDateString('en-US', { weekday: 'long' })
      });
    };

    updateClock();
    const interval = setInterval(updateClock, 1000);

    return () => clearInterval(interval);
  }, []);

  const centerX = 140;
  const centerY = 110;
  const radius = 90;

  // Calculate hand positions
  const hourAngle = (time.hours + time.minutes / 60) * 30;
  const minuteAngle = time.minutes * 6;
  const secondAngle = time.seconds * 6;

  const hourX = centerX + 45 * Math.sin((hourAngle * Math.PI) / 180);
  const hourY = centerY - 45 * Math.cos((hourAngle * Math.PI) / 180);

  const minuteX = centerX + 63 * Math.sin((minuteAngle * Math.PI) / 180);
  const minuteY = centerY - 63 * Math.cos((minuteAngle * Math.PI) / 180);

  const secondX = centerX + 72 * Math.sin((secondAngle * Math.PI) / 180);
  const secondY = centerY - 72 * Math.cos((secondAngle * Math.PI) / 180);

  // Generate hour markers
  const hourMarkers: Marker[] = Array.from({ length: 12 }, (_, i) => {
    const angle = (i * 30 * Math.PI) / 180;
    const x1 = centerX + (radius - 15) * Math.sin(angle);
    const y1 = centerY - (radius - 15) * Math.cos(angle);
    const x2 = centerX + (radius - 5) * Math.sin(angle);
    const y2 = centerY - (radius - 5) * Math.cos(angle);
    return { x1, y1, x2, y2 };
  });

  // Generate minute markers
  const minuteMarkers: Marker[] = Array.from({ length: 60 }, (_, i) => {
    if (i % 5 === 0) return null as any;
    const angle = (i * 6 * Math.PI) / 180;
    const x = centerX + (radius - 8) * Math.sin(angle);
    const y = centerY - (radius - 8) * Math.cos(angle);
    return { x, y };
  }).filter((m): m is Marker => m !== null);

  return (
    <div className="flex flex-col items-center justify-center gap-4 bg-transparent">
      <svg width="280" height="240" viewBox="0 0 280 240" className="drop-shadow-lg">
        {/* Outer decorative ring */}
        <circle
          cx={centerX}
          cy={centerY}
          r={radius + 5}
          fill="none"
          stroke="#d1d5db"
          strokeWidth="3"
        />

        {/* Clock face background */}
        <circle
          cx={centerX}
          cy={centerY}
          r={radius}
          fill="#ffffff"
          stroke="#e5e7eb"
          strokeWidth="2"
        />

        {/* Hour markers */}
        {hourMarkers.map((marker, i) => (
          <line
            key={`hour-${i}`}
            x1={marker.x1}
            y1={marker.y1}
            x2={marker.x2}
            y2={marker.y2}
            stroke="#1e293b"
            strokeWidth="2"
          />
        ))}

        {/* Minute markers */}
        {minuteMarkers.map((marker, i) => (
          <circle
            key={`minute-${i}`}
            cx={marker.x}
            cy={marker.y}
            r="1.5"
            fill="#94a3b8"
          />
        ))}

        {/* Hour hand */}
        <line
          x1={centerX}
          y1={centerY}
          x2={hourX}
          y2={hourY}
          stroke="#1e293b"
          strokeWidth="6"
          strokeLinecap="round"
        />

        {/* Minute hand */}
        <line
          x1={centerX}
          y1={centerY}
          x2={minuteX}
          y2={minuteY}
          stroke="#475569"
          strokeWidth="4"
          strokeLinecap="round"
        />

        {/* Second hand */}
        <line
          x1={centerX}
          y1={centerY}
          x2={secondX}
          y2={secondY}
          stroke="#ef4444"
          strokeWidth="2"
          strokeLinecap="round"
        />

        {/* Center circle */}
        <circle cx={centerX} cy={centerY} r="6" fill="#1e293b" />
      </svg>

      {/* Date and Day display */}
      <div className="text-center">
        <div className="text-lg font-bold text-slate-900">{date.date}</div>
        <div className="text-sm font-normal text-slate-600">{date.day}</div>
      </div>
    </div>
  );
}
