const dayKey = (d) => `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;

export function timeLabel(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  if (dayKey(d) === dayKey(now)) return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  const diffDays = (now - d) / 86400000;
  if (diffDays < 6) return d.toLocaleDateString([], { weekday: 'short' }) + ' ' + d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: d.getFullYear() === now.getFullYear() ? undefined : 'numeric' });
}

export function dayLabel(iso) {
  const d = new Date(iso);
  const now = new Date();
  const y = new Date(now);
  y.setDate(now.getDate() - 1);
  if (dayKey(d) === dayKey(now)) return 'Today';
  if (dayKey(d) === dayKey(y)) return 'Yesterday';
  const opts = { weekday: 'long', month: 'short', day: 'numeric' };
  if (d.getFullYear() !== now.getFullYear()) opts.year = 'numeric';
  return d.toLocaleDateString([], opts);
}

/** Split a list of articles into [{label, items}] by local day (F-29). */
export function groupByDay(items, key = 'published_at') {
  const groups = [];
  let current = null;
  for (const item of items) {
    const label = dayLabel(item[key]);
    if (!current || current.label !== label) {
      current = { label, items: [] };
      groups.push(current);
    }
    current.items.push(item);
  }
  return groups;
}

export function agoLabel(iso) {
  if (!iso) return 'never';
  const mins = Math.round((Date.now() - new Date(iso)) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} h ago`;
  return `${Math.round(hrs / 24)} d ago`;
}

export function clockLabel(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const t = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  return dayKey(d) === dayKey(now) ? t : `${d.toLocaleDateString([], { weekday: 'short' })} ${t}`;
}

const PALETTE = ['#2F5D50', '#4B3F8F', '#8F4B2E', '#1F4E79', '#6B4E16', '#3E6B3A', '#7A3B5C', '#3F5866'];
export function monogram(name = '?') {
  const clean = name.replace(/^(the|a)\s+/i, '').trim() || '?';
  let h = 0;
  for (const ch of clean) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return { letter: clean[0].toUpperCase(), color: PALETTE[h % PALETTE.length] };
}

export function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}
