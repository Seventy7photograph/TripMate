// 文件说明：前端功能模块：export。
import type { PublicTrip, TripExportDocument } from "./types";

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function buildTripExportHtml(document: PublicTrip): string {
  const days = document.days
    .map(
      (day) => `
        <section>
          <h2>${escapeHtml(day.theme || `第 ${day.day_index} 天`)} · ${escapeHtml(day.date)}</h2>
          <ol>
            ${day.stops
              .map(
                (stop) =>
                  `<li><strong>${escapeHtml(stop.place_name || stop.place_id)}</strong><span>${escapeHtml(
                    stop.start_at.slice(11, 16),
                  )} · ${stop.duration_minutes} 分钟</span></li>`,
              )
              .join("")}
          </ol>
        </section>`,
    )
    .join("");
  return `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>TripMate ${escapeHtml(document.destination)}</title>
<style>
body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;margin:48px;color:#171512;background:#f4efe4}
header{border-bottom:1px solid #cfc7b8;padding-bottom:24px;margin-bottom:28px}
h1{font-family:Georgia,serif;font-size:44px;margin:0 0 8px}section{margin:24px 0}h2{font-size:18px}
ol{padding-left:24px}li{margin:10px 0}li span{display:block;color:#6f6a60;font-size:12px;margin-top:3px}
footer{margin-top:36px;color:#6f6a60;font-size:11px}@page{margin:16mm}
</style></head><body>
<header><h1>${escapeHtml(document.destination)}</h1>
<p>${escapeHtml(document.start_date)} 至 ${escapeHtml(document.end_date)} · ${document.party_size} 人 · v${document.version}</p></header>
${days}<footer>由 TripMate 生成 · ${escapeHtml(document.generated_at.slice(0, 10))}</footer></body></html>`;
}

export function printTripPdf(document: PublicTrip): void {
  const popup = window.open("", "_blank", "noopener,noreferrer");
  if (!popup) throw new Error("浏览器阻止了打印窗口");
  popup.document.write(buildTripExportHtml(document));
  popup.document.close();
  popup.focus();
  popup.print();
}

function download(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export async function exportTripImage(
  document: PublicTrip,
  filename = "tripmate-trip",
): Promise<void> {
  const lineHeight = 34;
  const height = Math.max(
    900,
    320 + document.days.reduce((total, day) => total + 92 + day.stops.length * lineHeight, 0),
  );
  const canvas = window.document.createElement("canvas");
  canvas.width = 1200;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("浏览器无法创建导出画布");
  context.fillStyle = "#f4efe4";
  context.fillRect(0, 0, canvas.width, height);
  context.fillStyle = "#171512";
  context.font = '52px Georgia, "Microsoft YaHei", serif';
  context.fillText(document.destination, 64, 96);
  context.font = '18px "Microsoft YaHei", sans-serif';
  context.fillStyle = "#6f6a60";
  context.fillText(
    `${document.start_date} 至 ${document.end_date} · ${document.party_size} 人 · v${document.version}`,
    64,
    132,
  );
  let y = 196;
  for (const day of document.days) {
    context.fillStyle = "#171512";
    context.font = '600 22px "Microsoft YaHei", sans-serif';
    context.fillText(day.theme || `第 ${day.day_index} 天`, 64, y);
    context.fillStyle = "#8b5c3e";
    context.font = '14px "Microsoft YaHei", sans-serif';
    context.fillText(day.date, 980, y);
    y += 38;
    for (const stop of day.stops) {
      context.fillStyle = "#171512";
      context.font = '16px "Microsoft YaHei", sans-serif';
      context.fillText(stop.place_name || stop.place_id, 88, y);
      context.fillStyle = "#6f6a60";
      context.font = '13px "Microsoft YaHei", sans-serif';
      context.fillText(
        `${stop.start_at.slice(11, 16)} · ${stop.duration_minutes} 分钟`,
        820,
        y,
      );
      y += lineHeight;
    }
    y += 54;
  }
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((value) => {
      if (value) resolve(value);
      else reject(new Error("图片导出失败"));
    }, "image/png");
  });
  download(blob, `${filename}.png`);
}

export function exportFilename(document: TripExportDocument): string {
  return document.filename;
}
