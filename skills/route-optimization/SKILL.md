# route-optimization

## 目标

根据已确认地点的坐标和交通方式计算真实路线，为每日行程提供距离、时长、折线、Provider 和查询时间。

## 允许的 Tools

- `get_route`

## 输入

- `origin`：起点经纬度和坐标系，必填。
- `destination`：终点经纬度和坐标系，必填。
- `mode`：`driving`、`walking`、`bicycling`、`bus`、`subway` 或 `flight`。
- `city`：可选城市上下文。

## 输出

- `distance_m`：距离，单位米。
- `duration_s`：预计耗时，单位秒。
- `polyline`：Provider 返回的路线几何，可为空。
- `source`：Provider、查询时间、freshness 和置信度。

## 使用条件

- 两个相邻地点都有真实坐标。
- 用户选择或确认了交通方式。
- 跨城方案缺少真实班次或航线时，只能返回明确未确认状态。

## 禁止项

- 不得用直线距离冒充道路路线。
- 无坐标时不得绘制假路线。
- 不得编造航班、车次、票价或余票。

## 失败回退

Provider 超时、限流或单段失败时保留其他成功路段，并明确标记失败段；整体不可用时回退 `existing_itinerary_graph`。

## 验收样例

1. 重庆洪崖洞到解放碑步行，返回 live 距离、时长和折线。
2. 泉州开元寺到西街骑行，返回 Provider 来源和查询时间。
3. 缺少终点坐标时拒绝计算并提示补充，不生成推测路线。
