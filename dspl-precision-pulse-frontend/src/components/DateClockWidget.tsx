import { useEffect, useState } from 'react';

export default function DateClockWidget() {
  const [time, setTime] = useState<string>('');
  const [date, setDate] = useState<string>('');
  const [day, setDay] = useState<string>('');

  useEffect(() => {
    const updateDateTime = () => {
      const now = new Date();
      
      // Format time as HH:MM:SS
      const timeStr = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      });
      setTime(timeStr);
      
      // Format date as MMMM DD, YYYY
      const dateStr = now.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: '2-digit'
      });
      setDate(dateStr);
      
      // Format day
      const dayStr = now.toLocaleDateString('en-US', {
        weekday: 'long'
      });
      setDay(dayStr);
    };

    updateDateTime();
    const interval = setInterval(updateDateTime, 1000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center gap-1 bg-transparent">
      <div className="text-5xl font-bold text-slate-900 font-mono">
        {time || '00:00:00'}
      </div>
      <div className="text-base font-medium text-slate-600">
        {date || 'Loading...'}
      </div>
      <div className="text-sm font-normal text-slate-400">
        {day || 'Loading...'}
      </div>
    </div>
  );
}
