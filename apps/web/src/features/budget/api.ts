// 文件说明：前端功能模块：api。
import { request } from "../../lib/http";
import type {
  BudgetSummary,
  ExpenseCreateInput,
  ExpenseCreateResponse,
} from "./types";

export const budgetApi = {
  get(token: string, tripId: string): Promise<BudgetSummary> {
    return request<BudgetSummary>(
      `/api/v1/trips/${encodeURIComponent(tripId)}/budget`,
      {},
      token,
    );
  },

  createExpense(
    token: string,
    tripId: string,
    input: ExpenseCreateInput,
  ): Promise<ExpenseCreateResponse> {
    return request<ExpenseCreateResponse>(
      `/api/v1/trips/${encodeURIComponent(tripId)}/expenses`,
      {
        method: "POST",
        body: JSON.stringify(input),
      },
      token,
    );
  },
};
