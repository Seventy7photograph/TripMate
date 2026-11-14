# TripMate 视觉原型

视觉基线：方案 1 的象牙色编辑式行程工作台，结合方案 3 的左侧导航和 sea-glass 选中态。

执行状态：

- Web 原型：ACTIVE，可用于视觉迭代和 Web 生产设计参考。
- App 原型：FROZEN，只作为视觉参考，不得继续开发或扩展。
- App 生产工程：未创建，必须等待用户明确命令。

## Web 原型

- 目录：`prototypes/web`
- 本地地址：`http://localhost:4173`
- 启动：`npm run dev -- --host 0.0.0.0 --port 4173 --strictPort`
- 技术：React 19、Vite、MapLibre GL、Lucide、DM Serif Display、Manrope

## App 原型

- 目录：`prototypes/mobile`
- 本地地址：`http://localhost:4174`
- 启动：`npm run dev -- --host 0.0.0.0 --port 4174 --strictPort`
- 技术：Product Design mobile runtime、React 19、TypeScript、MapLibre GL、Lucide
- 状态：FROZEN。不是生产 App，也未解锁 App Track。

## 当前已实现

- 桌面和移动端导航
- 日期切换
- 真实 MapLibre 地图和路线标记
- 行程点位选择
- 预算视图
- 偏好设置
- AI 调整请求、Draft 确认和应用
- 桌面与移动响应式布局

## 验证状态

- Web 生产构建：通过
- App TypeScript 与生产构建：通过
- Mobile runtime 完整性：通过
- Sites 打包测试：Web 4/4、App 4/4
- 浏览器视觉 QA：待执行
