# MP157 使用 EC20 PPP 上传图片与检测信息到云端方案

## 1. 方案结论

本项目的 MP157 边缘端建议采用“EC20 负责 PPP 拨号上网，MP157 使用 HTTP 接口和 curl 上传数据”的方式接入云端。

核心原则是：**图片走腾讯云 COS，对象元数据和检测信息走云端后端 API**。MP157 不直接保存腾讯云永久密钥，只向后端申请一次性 COS 预签名上传地址，然后用 `curl -X PUT` 把图片传到 COS。

设备口径需要固定：**云端设备管理只登记 STM32MP157 主控设备**。STM32F4 不单独作为云端设备建档；F4 的传感器、执行器和控制状态通过串口传给 MP157，再由 MP157 放进检测记录的上下文字段一起上传。

| 项目 | 推荐做法 | 原因 |
|---|---|---|
| 4G 联网 | EC20 通过 PPP 拨号生成 `ppp0` 网卡 | 你当前已经能 PPP 上网并使用 `curl`，最适合继续沿用 |
| 图片上传 | MP157 先向后端申请 COS 预签名 URL，再用 curl 直传 COS | 图片不经过后端转发，省服务器带宽和内存 |
| 检测信息上传 | MP157 调用后端 `/api/v1/records` 创建检测记录 | 数据进入 MySQL，便于前端查询、统计和 AI 复核 |
| 图片与记录绑定 | 图片上传成功后调用 `/api/v1/records/{record_id}/files` 登记对象元数据 | 云端知道这张图片属于哪条检测记录 |
| F4 数据归属 | F4 串口数据放入 MP157 检测记录上下文 | 避免把 F4 当成独立云端设备，统计和删除都以 MP157 为主线 |
| 断网处理 | 本地保存待上传队列，恢复 4G 后补传 | PPP 网络不稳定时不丢检测数据 |

## 2. 整体数据链路

```text
摄像头/检测算法 + F4 串口数据
    |
    | 1. 生成原图、标注图、缩略图、检测结果 JSON 和 F4 上下文
    v
MP157 本地缓存目录
    |
    | 2. EC20 PPP 拨号成功，Linux 出现 ppp0 网卡
    v
MP157 curl 调云端后端
    |
    | 3. 创建检测记录，拿到 record_id
    v
后端 FastAPI + MySQL
    |
    | 4. 为每张图片生成 COS 预签名 PUT URL
    v
MP157 curl PUT 图片到腾讯云 COS
    |
    | 5. 上传成功后登记文件对象元数据
    v
前端记录页 / 详情页 / 统计页 / AI 复核
```

## 3. EC20 PPP 上网层怎么用

### 3.1 MP157 与 EC20 的职责划分

| 层级 | 负责内容 | 说明 |
|---|---|---|
| EC20 模块 | SIM 入网、4G 无线链路、PPP 数据通道 | 模块本身负责蜂窝网络接入 |
| MP157 Linux | 启动 `pppd`、获取 `ppp0`、配置默认路由和 DNS | Linux 把 EC20 当作拨号网络设备 |
| 上传程序 | 使用 `curl` 或 libcurl 访问 HTTPS 接口 | 只要 `curl https://...` 能通，业务层就不用关心 4G 细节 |

### 3.2 PPP 拨号成功后的检查

拨号完成后，MP157 上至少检查这几项：

```bash
ip addr show ppp0
ip route
cat /etc/resolv.conf
ping -I ppp0 -c 3 8.8.8.8
curl --interface ppp0 -I https://cloud.tencent.com
```

| 检查项 | 成功表现 | 失败时重点看 |
|---|---|---|
| `ppp0` | 能看到 `inet` 地址 | EC20 串口、APN、SIM 卡状态 |
| 默认路由 | 默认出口指向 `ppp0` | 是否还有以太网或 Wi-Fi 抢默认路由 |
| DNS | 能解析域名 | `/etc/resolv.conf` 或运营商 DNS |
| HTTPS | `curl` 能访问公网 HTTPS | 系统时间、CA 证书、信号质量 |

### 3.3 EC20 常用 AT 状态检查

如果 PPP 拨不上，先从 AT 串口检查模块状态：

| AT 指令 | 用途 | 期望结果 |
|---|---|---|
| `AT` | 确认串口通信 | `OK` |
| `AT+CPIN?` | 检查 SIM 卡 | `READY` |
| `AT+CSQ` | 检查信号质量 | 第一个数建议大于 10 |
| `AT+CREG?` / `AT+CEREG?` | 检查网络注册 | 返回已注册状态 |
| `AT+CGDCONT?` | 检查 PDP/APN | APN 与 SIM 卡运营商匹配 |

PPP 常见拨号号一般为 `*99#`，APN 需要按 SIM 卡运营商配置。已经能使用 `curl` 时，说明这层基本打通，后续重点是业务上传流程。

## 4. 云端接口分工

当前仓库后端已经有这几个接口：

| 目的 | 方法与路径 | MP157 什么时候调用 |
|---|---|---|
| 查询 MP157 设备 ID | `GET /api/v1/devices?limit=100` | 首次联调或本地配置丢失时，用设备编码确认云端 `device_id` |
| 创建检测记录 | `POST /api/v1/records` | 每检测完一个零件后先调用 |
| 申请 COS 上传地址 | `POST /api/v1/uploads/cos/prepare` | 每张图片上传前调用一次 |
| 登记图片对象 | `POST /api/v1/records/{record_id}/files` | 每张图片 PUT 到 COS 成功后调用 |
| 查看单条详情 | `GET /api/v1/records/{record_id}` | 调试或本地确认上传结果时调用 |

后端接口当前通过登录会话鉴权。MP157 可以先用 `/api/v1/auth/login` 登录，保存后端返回的 Cookie，再带 Cookie 调用后续接口。量产时更推荐新增设备专用 Token 接口，但现阶段用 Cookie 足够联调。

注意：

- `POST /api/v1/records` 里的 `device_id` 必须是云端已有的 MP157 设备 ID。
- 不要为 F4 调用设备创建接口，也不要发送 `device_type=f4`。当前云端服务会拒绝非 `mp157` 设备类型。
- F4 通过串口传来的值应进入 `sensor_context`、`decision_context` 或 `device_context`，随检测记录保存。

## 5. MP157 应该发送什么

### 5.1 检测主记录

检测主记录只放结构化信息，不直接塞图片二进制。

```json
{
  "record_no": "MP157-20260502-153012-0001",
  "part_id": 1,
  "device_id": 1,
  "result": "bad",
  "review_status": "pending",
  "surface_result": "bad",
  "backlight_result": "good",
  "eddy_result": "uncertain",
  "defect_type": "scratch",
  "defect_desc": "表面左上区域疑似划痕，面积约 12.5 mm2。",
  "confidence_score": 0.91,
  "vision_context": {
    "camera": "usb-camera-0",
    "image_width": 1280,
    "image_height": 720,
    "exposure_us": 8000,
    "gain": 1.5,
    "defect_boxes": [
      {
        "x": 312,
        "y": 184,
        "w": 96,
        "h": 35,
        "label": "scratch",
        "score": 0.91
      }
    ]
  },
  "sensor_context": {
    "ec20_rssi": 18,
    "ppp_interface": "ppp0",
    "f4_uart_status": "ok",
    "f4_sensor_values": {
      "eddy_value": 0.42,
      "photoelectric_triggered": true,
      "temperature_c": 36.5
    },
    "f4_control_state": {
      "motor_running": false,
      "rejector_action": "none",
      "last_command_seq": 128
    }
  },
  "decision_context": {
    "algorithm": "opencv-surface-v1",
    "threshold": 0.72,
    "cycle_ms": 238,
    "need_ai_review": true
  },
  "device_context": {
    "device_code": "MP157-VIS-01",
    "f4_board_code": "F4-CTRL-01",
    "f4_firmware_version": "f4-0.3.2",
    "software_version": "edge-0.1.0",
    "network": "EC20 PPP",
    "local_image_path": "/data/detections/20260502/source.jpg"
  },
  "captured_at": "2026-05-02T15:30:12+08:00",
  "detected_at": "2026-05-02T15:30:12.238+08:00"
}
```

字段说明：

| 字段 | 是否建议发送 | 说明 |
|---|---|---|
| `record_no` | 必须建议 | MP157 本地生成唯一编号，断网补传时用于去重排查 |
| `part_id` | 必须 | 云端已有的零件 ID |
| `device_id` | 必须 | 云端已有的 MP157 设备 ID，不能填 F4 |
| `result` | 必须 | `good`、`bad`、`uncertain` 三选一 |
| `surface_result` | 建议 | 表面视觉检测结果 |
| `backlight_result` | 建议 | 背光轮廓检测结果 |
| `eddy_result` | 可选 | 涡流/内部检测结果，没有就不传 |
| `defect_type` | 不良时建议 | 如 `scratch`、`dent`、`deformation`、`stain` |
| `defect_desc` | 不良时建议 | 给人看的缺陷描述 |
| `confidence_score` | 建议 | 0 到 1 的置信度 |
| `vision_context` | 建议 | 图像尺寸、曝光、检测框、算法输出 |
| `sensor_context` | 可选 | EC20 信号、F4 串口状态、涡流值、光电传感器状态、执行器状态等 |
| `decision_context` | 建议 | 算法版本、阈值、耗时、是否建议 AI 复核 |
| `device_context` | 建议 | MP157 设备编号、F4 板卡编号、软件版本、本地缓存路径、网络类型 |
| `captured_at` | 必须 | 相机拍到图片的时间，业务排序以它为准 |
| `detected_at` | 建议 | 算法完成判定的时间 |
| `uploaded_at` | 通常不传 | 图片上传成功后由文件登记接口回写更准确；只有需要保留边缘端历史上传时间时才传 |

### 5.2 图片文件

建议每次检测最多准备三类图片：

| 图片类型 | `file_kind` | 建议文件名 | 用途 |
|---|---|---|---|
| 原图 | `source` | `source.jpg` | 留档、AI 复核、人工复查 |
| 标注图 | `annotated` | `annotated.jpg` | 前端详情页优先展示，展示缺陷框和文字 |
| 缩略图 | `thumbnail` | `thumbnail.jpg` | 列表页快速加载，节省 4G 流量 |

图片建议：

| 项目 | 建议值 |
|---|---|
| 格式 | JPEG |
| 原图分辨率 | 按检测需要保存，例如 1280x720 或 1920x1080 |
| 标注图 | 与原图同尺寸，画缺陷框、中心线、结果文字 |
| 缩略图 | 320 到 480 像素宽 |
| JPEG 质量 | 原图 85 左右，缩略图 70 左右 |
| Content-Type | `image/jpeg` |

## 6. 一次完整上传流程

以下示例假设：

| 变量 | 示例 |
|---|---|
| 后端地址 | `https://api.example.com` |
| 当前线上联调地址 | `http://119.91.65.122` |
| Cookie 文件 | `/tmp/cloud_cookie.txt` |
| 原图路径 | `/data/detections/MP157-20260502-153012-0001/source.jpg` |
| 标注图路径 | `/data/detections/MP157-20260502-153012-0001/annotated.jpg` |

### 6.1 登录云端后端

```bash
curl --interface ppp0 \
  -c /tmp/cloud_cookie.txt \
  -H "Content-Type: application/json" \
  -X POST "https://api.example.com/api/v1/auth/login" \
  -d '{
    "account": "edge_mp157",
    "password": "替换成真实密码"
  }'
```

说明：

| 参数 | 作用 |
|---|---|
| `--interface ppp0` | 强制走 EC20 PPP 网络 |
| `-c /tmp/cloud_cookie.txt` | 保存后端登录 Cookie |
| `account/password` | 云端给 MP157 分配的账号 |

### 6.2 创建检测记录

```bash
curl --interface ppp0 \
  -b /tmp/cloud_cookie.txt \
  -H "Content-Type: application/json" \
  -X POST "https://api.example.com/api/v1/records" \
  -d '{
    "record_no": "MP157-20260502-153012-0001",
    "part_id": 1,
    "device_id": 1,
    "result": "bad",
    "review_status": "pending",
    "surface_result": "bad",
    "backlight_result": "good",
    "defect_type": "scratch",
    "defect_desc": "表面左上区域疑似划痕。",
    "confidence_score": 0.91,
    "vision_context": {
      "image_width": 1280,
      "image_height": 720,
      "defect_boxes": [
        {"x": 312, "y": 184, "w": 96, "h": 35, "label": "scratch", "score": 0.91}
      ]
    },
    "sensor_context": {
      "ec20_rssi": 18,
      "ppp_interface": "ppp0",
      "f4_uart_status": "ok",
      "f4_sensor_values": {
        "eddy_value": 0.42,
        "photoelectric_triggered": true,
        "temperature_c": 36.5
      },
      "f4_control_state": {
        "motor_running": false,
        "rejector_action": "none",
        "last_command_seq": 128
      }
    },
    "decision_context": {
      "algorithm": "opencv-surface-v1",
      "cycle_ms": 238,
      "need_ai_review": true
    },
    "device_context": {
      "device_code": "MP157-VIS-01",
      "f4_board_code": "F4-CTRL-01",
      "f4_firmware_version": "f4-0.3.2",
      "software_version": "edge-0.1.0",
      "network": "EC20 PPP"
    },
    "captured_at": "2026-05-02T15:30:12+08:00",
    "detected_at": "2026-05-02T15:30:12.238+08:00"
  }'
```

后端会返回检测记录详情，其中最重要的是：

| 返回字段 | 后续用途 |
|---|---|
| `id` | 后续申请 COS 上传和登记文件时使用 |
| `record_no` | COS 对象路径里也会使用，便于排查 |

### 6.3 为图片申请 COS 预签名上传地址

原图：

```bash
curl --interface ppp0 \
  -b /tmp/cloud_cookie.txt \
  -H "Content-Type: application/json" \
  -X POST "https://api.example.com/api/v1/uploads/cos/prepare" \
  -d '{
    "record_id": 123,
    "file_kind": "source",
    "file_name": "source.jpg",
    "content_type": "image/jpeg"
  }'
```

标注图：

```bash
curl --interface ppp0 \
  -b /tmp/cloud_cookie.txt \
  -H "Content-Type: application/json" \
  -X POST "https://api.example.com/api/v1/uploads/cos/prepare" \
  -d '{
    "record_id": 123,
    "file_kind": "annotated",
    "file_name": "annotated.jpg",
    "content_type": "image/jpeg"
  }'
```

后端返回示例：

```json
{
  "enabled": true,
  "provider": "cos",
  "bucket_name": "your-bucket-1250000000",
  "region": "ap-guangzhou",
  "object_key": "detections/MP157-20260502-153012-0001/source/xxxxxxxx_source.jpg",
  "upload_url": "https://your-bucket-1250000000.cos.ap-guangzhou.myqcloud.com/...",
  "method": "PUT",
  "headers": {
    "Content-Type": "image/jpeg"
  },
  "expires_in_seconds": 3600,
  "message": "COS 预签名地址生成成功。"
}
```

注意：

| 字段 | MP157 怎么用 |
|---|---|
| `enabled` | 必须为 `true` 才能真实上传 COS |
| `upload_url` | `curl -X PUT` 的目标地址 |
| `headers.Content-Type` | PUT 图片时必须带同样的 `Content-Type` |
| `object_key` | 上传成功后登记到后端 |
| `bucket_name` / `region` | 上传成功后登记到后端 |

### 6.4 使用 curl PUT 图片到 COS

```bash
curl --interface ppp0 \
  -X PUT "预签名 upload_url" \
  -H "Content-Type: image/jpeg" \
  --data-binary "@/data/detections/MP157-20260502-153012-0001/source.jpg" \
  -D /tmp/source_upload_headers.txt
```

成功判断：

| 项目 | 说明 |
|---|---|
| HTTP 状态码 | 一般为 `200` |
| `ETag` 响应头 | 保存下来，后续登记文件元数据 |
| 失败状态 | `403` 多半是签名过期或请求头不一致，`5xx` 可以重试 |

使用预签名 URL 时，`PUT` 请求里的 `Content-Type` 必须和申请上传地址时一致，否则 COS 可能拒绝请求。

### 6.5 上传成功后登记文件对象

```bash
curl --interface ppp0 \
  -b /tmp/cloud_cookie.txt \
  -H "Content-Type: application/json" \
  -X POST "https://api.example.com/api/v1/records/123/files" \
  -d '{
    "file_kind": "source",
    "storage_provider": "cos",
    "bucket_name": "your-bucket-1250000000",
    "region": "ap-guangzhou",
    "object_key": "detections/MP157-20260502-153012-0001/source/xxxxxxxx_source.jpg",
    "content_type": "image/jpeg",
    "size_bytes": 245678,
    "etag": "\"9b2cf535f27731c974343645a3985328\"",
    "uploaded_at": "2026-05-02T15:30:16+08:00"
  }'
```

标注图也按同样方式登记，只是 `file_kind` 改为 `annotated`，`object_key` 使用标注图那次 prepare 返回的值。

登记成功后，后端会把图片对象挂到检测记录下面。前端打开检测详情时，后端会生成可预览地址。

## 7. 推荐的本地缓存结构

MP157 端建议每条检测记录一个目录：

```text
/data/detections/
└── MP157-20260502-153012-0001/
    ├── record.json
    ├── source.jpg
    ├── annotated.jpg
    ├── thumbnail.jpg
    ├── upload_state.json
    └── upload.log
```

| 文件 | 用途 |
|---|---|
| `record.json` | 检测主记录请求体，断网后可以重放 |
| `source.jpg` | 原图 |
| `annotated.jpg` | 标注图 |
| `thumbnail.jpg` | 缩略图 |
| `upload_state.json` | 记录 `record_id`、每张图片是否已上传、COS object_key |
| `upload.log` | 保存上传过程日志，便于现场排障 |

`upload_state.json` 示例：

```json
{
  "record_no": "MP157-20260502-153012-0001",
  "record_id": 123,
  "record_created": true,
  "files": {
    "source": {
      "uploaded": true,
      "registered": true,
      "object_key": "detections/MP157-20260502-153012-0001/source/xxxxxxxx_source.jpg",
      "etag": "\"9b2cf535f27731c974343645a3985328\""
    },
    "annotated": {
      "uploaded": false,
      "registered": false,
      "object_key": null,
      "etag": null
    }
  }
}
```

## 8. 断网与重试策略

EC20 PPP 在现场可能遇到信号弱、基站切换、SIM 欠费、DNS 异常等问题，所以 MP157 上传程序不要把“检测”和“上传”强绑定。

| 场景 | 处理方式 |
|---|---|
| 检测时没有 4G 网络 | 先保存本地目录和 `record.json`，状态标为待上传 |
| 创建记录失败 | 保留本地记录，稍后重试同一个 `record_no` |
| COS 预签名过期 | 重新调用 `/uploads/cos/prepare`，不要复用旧 URL |
| PUT COS 中断 | 重新 PUT 同一张图片；如果对象路径变化，以最后成功登记的为准 |
| 文件已传 COS 但登记失败 | 保存 `bucket_name`、`region`、`object_key`、`etag`，恢复后补调 `/records/{record_id}/files` |
| 连续失败 | 指数退避，例如 5 秒、15 秒、60 秒、5 分钟 |

重试状态建议按这个顺序推进：

```text
LOCAL_READY
  -> RECORD_CREATED
  -> SOURCE_UPLOADED
  -> SOURCE_REGISTERED
  -> ANNOTATED_UPLOADED
  -> ANNOTATED_REGISTERED
  -> DONE
```

## 9. MP157 上传程序伪代码

```c
/*
 * 函数作用：
 *   上传一条检测记录及其图片到云端。
 *
 * 主要流程：
 *   1. 检查 EC20 PPP 网络是否可用。
 *   2. 创建检测主记录，拿到 record_id。
 *   3. 为每张图片申请 COS 预签名上传地址。
 *   4. 使用 curl/libcurl 通过 PUT 上传图片到 COS。
 *   5. 上传成功后登记图片对象元数据。
 *   6. 每完成一步都写入本地状态文件，断电或断网后可以继续补传。
 *
 * 参数：
 *   record_dir：本地检测记录目录，里面包含 record.json 和图片文件。
 *
 * 返回值：
 *   0 表示全部上传完成；非 0 表示仍需稍后重试。
 */
int upload_detection_record(const char *record_dir)
{
    /*
     * 这里先确认 ppp0 可用，避免在无网状态下反复请求后端。
     * 实际实现可以用 ping、HTTP healthcheck 或 netlink 检查路由状态。
     */
    if (!is_ppp0_network_ready()) {
        return RETRY_LATER;
    }

    /*
     * 如果本地还没有 record_id，说明检测主记录没有创建成功。
     * 创建时使用 record_no 作为业务唯一编号，方便断网重试和人工排查。
     */
    if (!state_has_record_id(record_dir)) {
        int record_id = create_cloud_record(record_dir);
        if (record_id <= 0) {
            return RETRY_LATER;
        }
        save_record_id_to_state(record_dir, record_id);
    }

    /*
     * 原图、标注图、缩略图逐个上传。
     * 每张图片独立申请预签名 URL，因为不同 file_kind 会生成不同 COS object_key。
     */
    if (!upload_and_register_file(record_dir, "source", "source.jpg")) {
        return RETRY_LATER;
    }
    if (!upload_and_register_file(record_dir, "annotated", "annotated.jpg")) {
        return RETRY_LATER;
    }
    if (file_exists(record_dir, "thumbnail.jpg")) {
        if (!upload_and_register_file(record_dir, "thumbnail", "thumbnail.jpg")) {
            return RETRY_LATER;
        }
    }

    /*
     * 全部图片登记完成后才标记 DONE。
     * 后续可以按策略删除本地大图，只保留 record.json 和 upload_state.json。
     */
    mark_upload_done(record_dir);
    return 0;
}
```

## 10. 安全注意事项

| 风险 | 建议 |
|---|---|
| 腾讯云永久密钥泄露 | 不要把 `COS_SECRET_ID`、`COS_SECRET_KEY` 放到 MP157 |
| 预签名 URL 泄露 | URL 有时效，建议 1 小时以内；上传完成后不要打印完整 URL 到公开日志 |
| 后端账号泄露 | 给 MP157 单独建低权限账号，只允许本公司设备上传 |
| MP157 设备被云端删除 | 设备管理页删除 MP157 会同步删除该设备关联的检测记录、审核记录、文件元数据和 COS 对象；边缘端本地缓存不要依赖云端记录长期保留 |
| 设备时间不准 | PPP 联网后先 NTP 同步，否则 HTTPS 证书和业务时间都可能异常 |
| 4G 流量过大 | 默认传 JPEG，列表用缩略图，必要时只上传不良品原图 |
| 私有桶访问 | 前端不要自己拼 COS URL，统一由后端生成预览 URL |

## 11. 推荐配置

### 11.1 后端 `.env`

后端需要配置 COS 参数：

```dotenv
COS_SECRET_ID=替换为腾讯云 SecretId
COS_SECRET_KEY=替换为腾讯云 SecretKey
COS_REGION=ap-guangzhou
COS_BUCKET=your-bucket-1250000000
COS_PUBLIC_BASE_URL=
COS_SIGNED_URL_EXPIRE_SECONDS=3600
```

### 11.2 MP157 本地配置

```ini
[network]
interface=ppp0
healthcheck_url=https://api.example.com/health

[cloud]
base_url=https://api.example.com
account=edge_mp157
password=替换成真实密码
device_code=MP157-VIS-01
device_id=1

[f4]
board_code=F4-CTRL-01
uart_device=/dev/ttySTM1
baudrate=115200

[upload]
root_dir=/data/detections
retry_initial_seconds=5
retry_max_seconds=300
upload_source=true
upload_annotated=true
upload_thumbnail=true
jpeg_quality=85
```

## 12. 联调顺序

| 步骤 | 验证命令或动作 | 通过标准 |
|---|---|---|
| 1 | `ip addr show ppp0` | 有 IP 地址 |
| 2 | `curl --interface ppp0 https://api.example.com/health` | 返回 `{"status":"ok"}` |
| 3 | 登录 `/api/v1/auth/login` | Cookie 文件写入成功 |
| 4 | 调 `/api/v1/devices?limit=100` | 找到本机 `device_code` 对应的 MP157 `id` |
| 5 | 创建 `/api/v1/records` | 返回 `id` 和 `record_no`，且 `device_id` 指向 MP157 |
| 6 | 调 `/api/v1/uploads/cos/prepare` | 返回 `enabled: true` 和 `upload_url` |
| 7 | `curl -X PUT upload_url --data-binary @source.jpg` | HTTP 200，返回 ETag |
| 8 | 调 `/api/v1/records/{record_id}/files` | 返回文件对象和 `preview_url` |
| 9 | 前端打开检测详情页 | 能看到检测信息、图片和 F4 上下文 |

## 13. 最小可跑通版本

最小版本只需要传两样东西：

| 类型 | 内容 |
|---|---|
| 检测信息 | `record_no`、`part_id`、MP157 的 `device_id`、`result`、`captured_at` |
| 图片 | 至少一张 `source.jpg`，上传后按 `file_kind=source` 登记 |

也就是说，第一阶段不必一次做全。先让 MP157 用 EC20 PPP 跑通：

```text
登录后端
  -> 创建检测记录
  -> 申请 source.jpg 上传地址
  -> curl PUT source.jpg 到 COS
  -> 登记 source 文件对象
  -> 前端详情页能看到图片
```

这条链路跑通后，再逐步加标注图、缩略图、缺陷框 JSON、EC20 信号质量、断网补传队列。

F4 串口数据不影响最小链路跑通。最小链路稳定后，再把 F4 的传感器值、控制状态、串口状态补进 `sensor_context` 和 `device_context`。

## 14. 参考资料

- [Quectel EC2x/EG2x/EG9x/EM05 Series PPP Application Note](https://quectel.com/content/uploads/2024/02/Quectel_EC2xEG2xEG9xEM05_Series_PPP_Application_Note_V1.1-4.pdf)：说明 EC20 所属 EC2x 系列在 Linux PPP 场景下的拨号思路与 PPP 数据链路。
- [腾讯云 COS 生成预签名 URL 文档](https://cloud.tencent.cn/document/product/436/35153)：说明通过预签名 URL 授权临时上传对象，适合边缘设备不持有永久密钥的场景。
