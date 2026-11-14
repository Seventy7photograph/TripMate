// 文件说明：前端功能模块：api。
import { request } from "../../lib/http";
import type { RequirementParseResult } from "./types";

export const assistantApi = {
  parse(
    token: string,
    text: string,
    attachmentIds: string[] = [],
  ): Promise<RequirementParseResult> {
    return request<RequirementParseResult>(
      "/api/v1/briefs/parse",
      {
        method: "POST",
        body: JSON.stringify({
          text,
          attachment_ids: attachmentIds,
        }),
      },
      token,
    );
  },
};
