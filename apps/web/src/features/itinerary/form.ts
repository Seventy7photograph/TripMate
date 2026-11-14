// 文件说明：前端功能模块：form。
export function dateTimeFor(date: string, time: string): string {
  if (!date || !time) return "";
  return `${date}T${time}:00`;
}

export function timeFromDateTime(value: string): string {
  const match = /T(\d{2}:\d{2})/.exec(value);
  return match?.[1] ?? "";
}

export function parseAmountToMinor(value: string): number | null | undefined {
  const normalized = value.trim();
  if (!normalized) return null;

  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(normalized);
  if (!match) return undefined;

  const whole = Number(match[1]);
  const fraction = Number((match[2] ?? "").padEnd(2, "0"));
  const minor = whole * 100 + fraction;
  return Number.isSafeInteger(minor) ? minor : undefined;
}

export function datesBetween(startDate: string, endDate: string): string[] {
  if (!startDate || !endDate || startDate > endDate) return [];

  const start = new Date(`${startDate}T00:00:00Z`);
  const end = new Date(`${endDate}T00:00:00Z`);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return [];

  const dates: string[] = [];
  for (
    let current = start;
    current.getTime() <= end.getTime();
    current = new Date(current.getTime() + 86_400_000)
  ) {
    dates.push(current.toISOString().slice(0, 10));
  }
  return dates;
}
