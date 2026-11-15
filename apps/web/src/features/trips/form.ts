// 文件说明：前端功能模块：form。
import type { TransportStrategy, TripBrief } from "./types";

function emptyTransportStrategy(): TransportStrategy {
  return {
    strategy: "unspecified",
    segments: [],
    constraints: [],
  };
}

export interface TripBriefFormInput {
  destination: string;
  origin: string;
  startDate: string;
  endDate: string;
  partySize: string;
  budgetAmount: string;
  currency: string;
  interests: string;
  pace: "relaxed" | "balanced" | "intensive";
  transportPreferences: string;
  transportStrategy: TransportStrategy;
  lodgingPreferences: string;
  mustVisit: string;
  avoid: string;
  constraints: string;
}

export type TripBriefInput = TripBrief;

export function emptyTripBriefForm(): TripBriefFormInput {
  return {
    destination: "",
    origin: "",
    startDate: "",
    endDate: "",
    partySize: "1",
    budgetAmount: "",
    currency: "CNY",
    interests: "",
    pace: "balanced",
    transportPreferences: "",
    transportStrategy: emptyTransportStrategy(),
    lodgingPreferences: "",
    mustVisit: "",
    avoid: "",
    constraints: "",
  };
}

export function tripBriefToForm(
  brief: Partial<TripBrief> | null | undefined,
): TripBriefFormInput {
  const empty = emptyTripBriefForm();
  if (!brief) return empty;
  return {
    destination: brief.destination ?? empty.destination,
    origin: brief.origin ?? empty.origin,
    startDate: brief.start_date ?? empty.startDate,
    endDate: brief.end_date ?? empty.endDate,
    partySize:
      brief.party_size === undefined ? empty.partySize : String(brief.party_size),
    budgetAmount:
      brief.budget_minor === null || brief.budget_minor === undefined
        ? empty.budgetAmount
        : (brief.budget_minor / 100).toFixed(2).replace(/\.00$/, ""),
    currency: brief.currency ?? empty.currency,
    interests: brief.interests?.join(", ") ?? empty.interests,
    pace: brief.pace ?? empty.pace,
    transportPreferences:
      brief.transport_preferences?.join(", ") ?? empty.transportPreferences,
    transportStrategy:
      brief.transport_strategy ?? empty.transportStrategy,
    lodgingPreferences:
      brief.lodging_preferences?.join(", ") ?? empty.lodgingPreferences,
    mustVisit: brief.must_visit?.join(", ") ?? empty.mustVisit,
    avoid: brief.avoid?.join(", ") ?? empty.avoid,
    constraints: brief.constraints?.join(", ") ?? empty.constraints,
  };
}

export function parseYuanToMinor(value: string): number | null | undefined {
  const normalized = value.trim();
  if (!normalized) return null;

  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(normalized);
  if (!match) return undefined;

  const whole = Number(match[1]);
  const fraction = Number((match[2] ?? "").padEnd(2, "0"));
  const minor = whole * 100 + fraction;
  return Number.isSafeInteger(minor) ? minor : undefined;
}

export function splitList(value: string): string[] {
  const items: string[] = [];
  for (const raw of value.split(/[,，\n]/)) {
    const item = raw.trim();
    if (item && !items.includes(item)) {
      items.push(item);
    }
  }
  return items;
}

export function toTripBriefInput(form: TripBriefFormInput): TripBriefInput {
  return {
    destination: form.destination.trim(),
    origin: form.origin.trim() || null,
    start_date: form.startDate,
    end_date: form.endDate,
    party_size: Number(form.partySize),
    budget_minor: parseYuanToMinor(form.budgetAmount) ?? null,
    currency: form.currency.trim().toUpperCase(),
    interests: splitList(form.interests),
    pace: form.pace,
    transport_preferences: splitList(form.transportPreferences),
    transport_strategy: form.transportStrategy,
    lodging_preferences: splitList(form.lodgingPreferences),
    must_visit: splitList(form.mustVisit),
    avoid: splitList(form.avoid),
    constraints: splitList(form.constraints),
  };
}

export function validateTripBriefForm(form: TripBriefFormInput): string | null {
  if (!form.destination.trim()) {
    return "请填写目的地。";
  }
  if (!form.startDate || !form.endDate) {
    return "请选择完整的旅行日期。";
  }
  if (form.startDate > form.endDate) {
    return "开始日期不能晚于结束日期。";
  }

  const partySize = Number(form.partySize);
  if (!Number.isInteger(partySize) || partySize < 1 || partySize > 20) {
    return "出行人数需为 1 到 20 人。";
  }

  if (parseYuanToMinor(form.budgetAmount) === undefined) {
    return "预算最多保留两位小数。";
  }
  if (!/^[A-Za-z]{3}$/.test(form.currency.trim())) {
    return "货币需为三位字母代码。";
  }
  return null;
}
