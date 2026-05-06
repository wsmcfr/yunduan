# 云端 MVP 前后端规划

## 1. 目标

本阶段目标是先落地一套可扩展的云端 MVP：

1. 先把服务端骨架搭起来
2. 把数据库表结构、时间字段和 API 契约定死
3. 把前端路由和页面外壳搭好
4. AI 大模型复核先只预留接口，不做真实接入

## 2. 技术选型

| 层 | 方案 |
|---|---|
| 前端 | Vue 3 + Vite + TypeScript + Element Plus + Pinia + Vue Router |
| 后端 | FastAPI + SQLAlchemy + Alembic + MySQL |
| 对象存储 | 腾讯云 COS |
| 鉴权 | JWT |
| 部署 | Docker Compose / Nginx |

## 3. 前后端职责划分

### 3.1 服务端职责

| 模块 | 职责 |
|---|---|
| 认证模块 | 用户登录、用户身份识别、权限字段返回 |
| 零件模块 | 零件类型、零件编码、启停状态维护 |
| 设备模块 | STM32MP157 主控设备档案与在线状态维护；F4 数据通过串口进入 MP157 后随检测记录上报 |
| 检测记录模块 | 保存检测主记录、时间字段、判定结果 |
| 文件模块 | 保存 COS 对象信息、结果图和原图信息 |
| 人工审核模块 | 记录人工审核结果 |
| 统计模块 | 统计良率、缺陷分布、每日趋势 |
| COS 接口 | 预留上传准备接口和对象元数据记录 |
| AI 复核接口 | 先预留接口，不做真实调用 |

### 3.2 前端职责

| 页面 | 职责 |
|---|---|
| 登录页 | 登录和鉴权入口 |
| 仪表盘 | 概览统计、最近记录、设备状态 |
| 检测记录页 | 按条件筛选检测记录 |
| 检测详情页 | 查看单条记录、时间字段、图片、审核结果 |
| 零件管理页 | 管理零件类型 |
| 设备管理页 | 管理 MP157 主控设备信息、状态和删除确认 |
| 统计页 | 每日趋势、缺陷分布 |
| 设置页 | 系统基础设置预留 |

## 4. 数据流

```text
MP157 -> 后端 records 接口 -> MySQL 写入主记录
MP157/后端 -> COS -> 返回对象信息
后端 -> file_objects 表 -> 保存 object_key / uploaded_at / storage_last_modified
前端 -> records/statistics/devices/parts 接口 -> 展示和审核
```

## 5. 时间字段约定

| 字段 | 含义 | 排序用途 |
|---|---|---|
| `captured_at` | 真正拍到检测图片的时间 | 历史记录主排序字段 |
| `detected_at` | 模型完成判定的时间 | 分析检测耗时 |
| `uploaded_at` | 图片或结果图上传到云端成功时间 | 分析同步延迟 |
| `storage_last_modified` | COS 对象最后修改时间 | 作为 COS 校验值 |

规则：

1. 历史记录默认按 `captured_at DESC`
2. 后端接口同时支持 `captured_at` 和 `uploaded_at` 范围过滤
3. `storage_last_modified` 不作为主业务排序字段

## 6. 数据库表

### 6.1 users

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `username` | 登录名 |
| `password_hash` | 密码哈希 |
| `display_name` | 展示名称 |
| `role` | `admin` / `operator` / `reviewer` |
| `is_active` | 是否启用 |
| `last_login_at` | 最近登录时间 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### 6.2 parts

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `part_code` | 零件编码 |
| `name` | 零件名称 |
| `category` | 分类 |
| `description` | 描述 |
| `is_active` | 是否启用 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### 6.3 devices

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `device_code` | 设备编码 |
| `name` | 设备名称 |
| `device_type` | 固定为 `mp157`；F4 不单独作为云端设备建档 |
| `status` | `online` / `offline` / `fault` |
| `firmware_version` | 固件版本 |
| `ip_address` | IP 地址 |
| `last_seen_at` | 最近心跳时间 |
| `record_count` | 该 MP157 关联的检测记录数量，用于删除前确认 |
| `image_count` | 该 MP157 关联的文件元数据数量，用于删除前确认 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### 6.4 detection_records

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `record_no` | 检测记录编号 |
| `part_id` | 关联零件 |
| `device_id` | 关联设备 |
| `result` | `good` / `bad` / `uncertain` |
| `review_status` | `pending` / `reviewed` / `ai_reserved` |
| `surface_result` | 表面结果 |
| `backlight_result` | 背光结果 |
| `eddy_result` | 涡流结果 |
| `defect_type` | 缺陷类型 |
| `defect_desc` | 缺陷说明 |
| `confidence_score` | 置信度 |
| `captured_at` | 拍照时间 |
| `detected_at` | 检测完成时间 |
| `uploaded_at` | 主结果图上传完成时间 |
| `storage_last_modified` | COS 最后修改时间 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

### 6.5 file_objects

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `detection_record_id` | 关联检测记录 |
| `file_kind` | `source` / `annotated` / `thumbnail` |
| `storage_provider` | 默认 `cos` |
| `bucket_name` | 存储桶名称 |
| `region` | 存储区域 |
| `object_key` | COS 对象路径 |
| `content_type` | 文件类型 |
| `size_bytes` | 文件大小 |
| `etag` | 文件 etag |
| `uploaded_at` | 上传完成时间 |
| `storage_last_modified` | COS 对象最后修改时间 |
| `created_at` | 创建时间 |

### 6.6 review_records

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `detection_record_id` | 关联检测记录 |
| `reviewer_id` | 人工审核用户，可空 |
| `review_source` | `manual` / `ai_reserved` |
| `decision` | `good` / `bad` / `uncertain` |
| `defect_type` | 审核判定缺陷类型 |
| `comment` | 备注 |
| `reviewed_at` | 审核时间 |
| `created_at` | 创建时间 |

## 7. API 规划

### 7.1 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/auth/login` | 用户登录 |
| `GET` | `/api/v1/auth/me` | 获取当前用户 |

### 7.2 零件管理

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/parts` | 获取零件列表 |
| `POST` | `/api/v1/parts` | 创建零件 |
| `PUT` | `/api/v1/parts/{id}` | 更新零件 |

### 7.3 设备管理

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/devices` | 获取设备列表 |
| `POST` | `/api/v1/devices` | 创建设备 |
| `PUT` | `/api/v1/devices/{id}` | 更新设备 |
| `DELETE` | `/api/v1/devices/{id}` | 彻底删除设备及其关联检测记录、审核记录、文件元数据和对象存储文件 |

### 7.4 检测记录

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/records` | 获取检测记录列表 |
| `POST` | `/api/v1/records` | 创建检测记录 |
| `GET` | `/api/v1/records/{id}` | 获取检测记录详情 |
| `POST` | `/api/v1/records/{id}/files` | 绑定或登记文件对象 |

### 7.5 人工审核

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/records/{id}/manual-review` | 提交人工审核结果 |
| `GET` | `/api/v1/records/{id}/reviews` | 获取审核记录 |

### 7.6 统计

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/v1/statistics/summary` | 获取统计概览 |
| `GET` | `/api/v1/statistics/daily-trend` | 获取每日趋势 |
| `GET` | `/api/v1/statistics/defect-distribution` | 获取缺陷分布 |

### 7.7 COS 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/uploads/cos/prepare` | 预留 COS 上传准备接口 |

### 7.8 AI 预留接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/records/{id}/ai-review` | 当前返回预留状态，不做真实调用 |

## 8. 前端页面骨架规划

| 路由 | 页面文件 | 说明 |
|---|---|---|
| `/login` | `LoginPage.vue` | 登录页 |
| `/dashboard` | `DashboardPage.vue` | 仪表盘 |
| `/records` | `RecordsPage.vue` | 检测记录页 |
| `/records/:id` | `RecordDetailPage.vue` | 检测详情页 |
| `/parts` | `PartsPage.vue` | 零件管理页 |
| `/devices` | `DevicesPage.vue` | 设备管理页 |
| `/statistics` | `StatisticsPage.vue` | 统计页 |
| `/settings` | `SettingsPage.vue` | 设置页 |

## 9. 第一阶段实施顺序

| 顺序 | 内容 |
|---|---|
| 1 | 搭 `backend/` 骨架、配置、数据库、迁移 |
| 2 | 落模型、Schema、Repository、Service、Route |
| 3 | 落 `frontend/` 路由与页面壳 |
| 4 | 再逐步接真实 COS 和前端业务页面 |
