// 文件说明：前端功能模块：sse。
import type { ParsedSseEvent, PlanningEvent } from "./types";

export function parseSseChunks(chunks: string[]): ParsedSseEvent[] {
  const text = chunks.join("");
  return text
    .split(/\r?\n\r?\n/)
    .filter((block) => block.trim())
    .map((block) => parseSseBlock(block))
    .filter((event): event is ParsedSseEvent => event !== null);
}

export function parseSseBlock(block: string): ParsedSseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }
  if (!dataLines.length) return null;
  try {
    return {
      event,
      data: JSON.parse(dataLines.join("\n")) as PlanningEvent,
    };
  } catch {
    return null;
  }
}
