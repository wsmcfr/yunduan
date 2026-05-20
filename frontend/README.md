# Frontend MVP

## 作用

该目录用于存放云端 MVP 前端服务，基于 Vue 3、Vite、TypeScript 和 Element Plus，负责检测记录、零件管理、设备管理、统计看板和人工复核界面。

## 2026-05-20 MP157 零件显示与详情长文本总结

### 本次前端修改了什么

| 文件 | 作用 | 修改原因 |
|---|---|---|
| `frontend/src/features/parts/partCategories.ts` | 归一零件分类、构建分类卡片、维护旧模型编码到中文零件名的显示规则。 | `gasket` 历史训练名实际代表“波形垫圈”，不能显示成“垫片”；`垫片/垫圈/washer-family` 这类旧分类统一显示为“垫圈类”。 |
| `frontend/src/pages/PartsPage.vue` | 零件页先显示分类入口，再显示分类下的具体零件类型和样本入口。 | “垫圈类”是分类，不是一个零件；波形垫圈、平垫圈、弹性垫圈仍应是独立零件。 |
| `frontend/src/services/mappers/commonMappers.ts` | API DTO 转前端模型时归一 `partCategory`。 | 避免详情页、列表页、统计筛选和零件页显示不同分类名称。 |
| `frontend/src/features/parts/partCategories.test.ts` | 覆盖分类归一和分组逻辑。 | 防止后续把 `gasket` 又显示成“垫片”，或把不同垫圈零件合并成一个零件。 |
| `frontend/src/pages/managementPages.test.ts` | 覆盖管理页交互和分组展示。 | 确认分类入口不会破坏原有零件列表、筛选和跳转。 |

### 显示规则

| 输入编码/分类 | 前端显示 | 说明 |
|---|---|---|
| `gasket`、`gasket_good`、`gasket_bad` | 波形垫圈 | 历史训练命名错误，业务上不是“垫片”。 |
| `washer` | 平垫圈 | 平垫圈是独立零件。 |
| `splitwasher` | 弹性垫圈 | 弹性垫圈是独立零件。 |
| `垫片`、`垫圈`、`washer-family`、`washer_family` | 垫圈类 | 这些只是分类显示名，不代表具体零件。 |

## 长文本显示要求

云端记录详情、复核原因、板端同步错误和模型诊断文字可能很长。列表或卡片中可以显示摘要，但完整文本必须能在详情页、弹窗或抽屉中滚动读完，不能只靠表格省略号或浏览器 tooltip。

| 场景 | 正确处理 |
|---|---|
| 云端复核原因很长 | 卡片显示摘要，详情弹窗/详情页显示完整原因。 |
| 板端同步失败原因很长 | 状态区显示简短错误，详情位置保留完整 `board_sync_error`。 |
| 模型原始输出/UNet 提示很长 | 页面给操作员可读摘要，诊断详情保留完整文本。 |

## 怎么测试

在云端前端目录执行：

```powershell
cd D:\yunfuwu\frontend
npm test -- partCategories managementPages
```

完整前端回归可以执行：

```powershell
cd D:\yunfuwu\frontend
npm test
```

人工验收建议：

| 测试目标 | 执行位置 | 操作 | 预期输出/现象 | 失败时排查 |
|---|---|---|---|---|
| 零件分类显示 | 浏览器 `/parts` | 打开零件管理页 | 能看到“垫圈类”分类入口；进入后仍能看到波形垫圈、平垫圈、弹性垫圈等具体零件。 | 查 `partCategories.ts` 和后端返回的 `part_code/category`。 |
| 历史命名修正 | 浏览器 `/parts` | 查看 `gasket` 相关零件 | 显示“波形垫圈”，不显示“垫片”。 | 查前端归一函数和后端 `part_identity.py` 是否同时生效。 |
| 分类跳转 | 浏览器 `/parts` | 点击分类样本入口或具体零件样本入口 | 分类跳转按“垫圈类”筛选，具体零件跳转按对应零件筛选。 | 查路由 query 是否同时区分 `category` 和 `part`。 |
| 长文本可读 | 检测记录详情页 | 打开包含长复核原因或长同步错误的记录 | 摘要不挤坏布局，完整文本能在详情区域滚动读完。 | 查页面是否只使用 `show-overflow-tooltip` 而没有详情承载面。 |
