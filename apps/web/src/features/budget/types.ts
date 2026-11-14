// 文件说明：前端功能模块：types。
export type ExpenseCategory =
  | "transport"
  | "lodging"
  | "food"
  | "tickets"
  | "shopping"
  | "activities"
  | "other";

export interface Expense {
  id: string;
  trip_id: string;
  payer_id: string;
  category: ExpenseCategory;
  amount_minor: number;
  currency: string;
  expense_date: string;
  note: string | null;
  created_at: string;
}

export interface BudgetCategory {
  category: ExpenseCategory;
  estimated_minor: number;
  actual_minor: number;
}

export interface BudgetIssue {
  code: string;
  severity: "info" | "warning" | "error" | "fatal";
  message: string;
  overage_minor: number;
}

export interface BudgetSummary {
  trip_id: string;
  version: number;
  currency: string;
  budget_minor: number | null;
  estimated_minor: number;
  total_minor: number;
  per_person_minor: number;
  remaining_minor: number | null;
  estimated_remaining_minor: number | null;
  categories: BudgetCategory[];
  issues: BudgetIssue[];
  expenses: Expense[];
}

export interface ExpenseCreateInput {
  expected_version: number;
  category: ExpenseCategory;
  amount_minor: number;
  currency: string;
  expense_date: string;
  note?: string | null;
}

export interface ExpenseCreateResponse {
  version: number;
  expense: Expense;
}
