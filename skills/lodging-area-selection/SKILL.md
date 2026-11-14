# lodging-area-selection

## 目标

比较住宿区域与交通锚点，输出适合进一步筛选的区域建议。该 Skill 不返回酒店房态、
库存、可订承诺或虚构房价。

## 允许的 Tools

- `search_places`
- `get_route_matrix`

## 输入

- `city`、`preferences`。
- `budget_minor_per_night`：可选预算。
- `limit`：2 到 3 个区域锚点。

## 输出

- 区域锚点、地址、区域 Evidence ID。
- 区域间交通 Evidence ID。
- 房态和可订能力免责声明。

## 禁止项

- 不得编造酒店、房价、空房、库存或取消政策。
- 不得把区域推荐当作已预订。

## 失败回退

少于两个可用于比较的区域锚点时回退 `existing_itinerary_graph`。

## 验收样例

1. 泉州“地铁、安静”偏好返回两个交通锚点和区域比较。
2. 输出明确说明仅比较区域与交通，不提供酒店房态。
