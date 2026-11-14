# safety-briefing

## 目标

根据天气、海拔、同行人群和路线事实生成旅行安全提醒。阈值规则是产品规则，
不是医疗诊断；所有外部事实必须引用 Evidence ID。

## 允许的 Tools

- `get_weather`
- `get_altitude`
- `get_route`

## 输入

- `dates`、`party`。
- 可选 `city`、`altitude_m`、经纬度。

## 输出

- `level`：`low`、`moderate`、`warning` 或 `high`。
- 安全提醒、天气摘要、Evidence ID。
- 不替代医疗意见的免责声明。

## 规则

- 海拔达到 2500 米触发高海拔提醒。
- 海拔达到 3500 米提升为高风险。
- 儿童、老人、孕期或慢性病人群需要额外关注。

## 禁止项

- 不得诊断疾病或建议自行用药。
- 不得猜测未提供的海拔、天气或道路状态。

## 验收样例

1. 3200 米返回 `warning` 或 `high`，并包含高海拔提醒。
2. 所有输出包含“不替代医疗意见”。
