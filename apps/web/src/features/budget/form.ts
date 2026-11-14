// 文件说明：前端功能模块：form。
export function parseBudgetAmount(value: string): number | null | undefined {
  const normalized = value.trim();
  if (!normalized) return null;

  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(normalized);
  if (!match) return undefined;

  const whole = Number(match[1]);
  const fraction = Number((match[2] ?? "").padEnd(2, "0"));
  const minor = whole * 100 + fraction;
  return Number.isSafeInteger(minor) ? minor : undefined;
}

export function toBudgetMinor(value: string): number {
  return parseBudgetAmount(value) ?? 0;
}

export function formatMoney(minor: number, currency: string): string {
  const absolute = Math.abs(minor);
  const whole = Math.floor(absolute / 100);
  const fraction = absolute % 100;
  const amount = fraction
    ? `${whole}.${String(fraction).padStart(2, "0")}`
    : String(whole);
  const symbols: Record<string, string> = {
    CNY: "¥",
    USD: "$",
    EUR: "€",
    JPY: "¥",
  };
  const sign = minor < 0 ? "-" : "";
  return `${sign}${symbols[currency] ?? `${currency} `}${amount}`;
}
