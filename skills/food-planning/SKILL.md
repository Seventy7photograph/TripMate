# food-planning

## 目标

按早餐、午餐或晚餐检索真实餐饮 POI，并用 Place Fact 标注营业状态、参考价格和
Evidence。忌口与过敏只生成确认提醒，不假装餐厅已经确认。

## 允许的 Tools

- `search_places`
- `get_place_facts`

## 输入

- `meal`、`city`、可选 `date`。
- `dietary`：忌口、过敏或饮食偏好。
- `budget_minor_per_person`：可选人均预算，整数最小货币单位。
- `limit`：最多 3 家餐厅。

## 输出

- 餐饮 POI、营业状态、参考价格和 Evidence ID。
- 忌口待确认提醒。
- 只包含非事实说明的 `evidence_free_text`。

## 禁止项

- 缺失营业时间时不得填入默认时间。
- 不得把字符串参考价当成实时报价。
- 不得声称餐厅已确认过敏要求。

## 失败回退

无餐厅、无坐标或无 Evidence 时返回明确警告，不生成虚构餐厅。

## 验收样例

1. 午餐搜索返回两家餐厅，营业时间缺失时状态为 `unknown`。
2. 用户标注花生过敏时输出向餐厅确认的提醒，不声称已避免交叉污染。
