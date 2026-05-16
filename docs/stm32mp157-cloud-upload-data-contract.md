# STM32MP157 云端上报信息契约

## 1. 文档目标

本文档说明 STM32MP157 边缘端需要向云端发送的全部信息，覆盖登录、设备与零件标识、检测主记录、`UNet + MobileNetV3-Small` 模型输出、STM32F4 串口上下文、图片对象、COS 上传元数据、断网补传状态和联调验收点。

当前线上联调服务器地址固定为：

| 项目 | 值 |
|---|---|
| 云端 Web/API 根地址 | `http://119.91.65.122` |
| API 前缀 | `http://119.91.65.122/api/v1` |
| 健康检查 | `GET http://119.91.65.122/health` |
| 当前鉴权方式 | 登录接口返回 HttpOnly Cookie，MP157 端用 Cookie 文件保存会话 |
| 对象存储方式 | 后端生成腾讯云 COS 预签名 PUT URL，MP157 直传图片到 COS |
| 云端设备口径 | 只登记 STM32MP157 主控设备，STM32F4 不作为独立云端设备 |

本次硬件字段按联网资料与用户实物说明核对后整理：

| 硬件 | 文档采用的关键口径 | 资料依据 |
|---|---|---|
| LDC1614 涡流/电感检测模块 | TI LDC1614，4 通道，28 位，I2C，2.7V 到 3.6V，传感器频率 1kHz 到 10MHz | [TI LDC1614 产品页](https://www.ti.com/product/LDC1614) |
| HX711 称重模块 | 24 位称重 ADC，通过 `DOUT` 与 `PD_SCK` 串行读数，不按 I2C/SPI 处理 | [HX711 数据手册索引](https://www.digikey.com/en/htmldatasheets/production/1836471/0/0/1/hx711) |
| Emm42_V5.0 传送带电机 | 张大头 Emm42_V5.0 闭环 42 步进电机，用户购买工业套餐，本项目采用串口控制 | [张大头 Emm_V5.0 步进闭环驱动说明](https://blog.csdn.net/zhangdatou666/article/details/132644047) |

## 2. 总体上传链路

```text
STM32MP157 采集图片
  -> 运行 UNet 分割与 MobileNetV3-Small 分类
  -> 汇总 STM32F4 串口传来的传感器和执行器状态
  -> POST /api/v1/records 创建检测主记录
  -> POST /api/v1/uploads/cos/prepare 为每张图片申请上传地址
  -> PUT 图片到 COS
  -> POST /api/v1/records/{record_id}/files 登记图片对象元数据
  -> 前端记录页、详情页、统计页和 AI 复核读取这些数据
```

## 3. 对接前必须准备的信息

这些信息不应该在每次检测里临时猜测，建议写入 MP157 本地配置文件，并允许现场运维修改。

| 配置项 | 要求 | 示例 | 来源与说明 |
|---|---:|---|---|
| `base_url` | 必须 | `http://119.91.65.122` | 云端服务器根地址 |
| `api_prefix` | 必须 | `/api/v1` | 后端固定 API 前缀 |
| `account` | 必须 | `edge_mp157` | 云端给 MP157 分配的登录账号 |
| `password` | 必须 | `<现场配置>` | 云端给 MP157 分配的登录密码，不能写进公开代码 |
| `device_code` | 必须 | `MP157-VIS-01` | 云端设备编码，用来查找本机 `device_id` |
| `device_id` | 必须 | `1` | 云端设备表主键，创建检测记录时必须传 |
| `part_id` | 必须 | `1` | 云端零件表主键，创建检测记录时必须传 |
| `part_code` | 建议 | `PART-RING-001` | 零件编码，主要放在本地日志和 `device_context` 里便于排障 |
| `network_interface` | 建议 | `ppp0` | EC20 PPP 网卡名称，curl 可使用 `--interface ppp0` |
| `f4_uart_device` | 建议 | `/dev/ttySTM1` | MP157 与 STM32F4 通信串口 |
| `f4_baudrate` | 建议 | `115200` | F4 串口波特率 |
| `ldc1614_i2c_bus` | 建议 | `I2C1` | F4 连接 LDC1614 涡流/电感检测模块的 I2C 外设 |
| `ldc1614_i2c_address` | 建议 | `0x2A` | LDC1614 7 位 I2C 地址，按模块 ADDR 引脚配置填写 |
| `hx711_dout_gpio` | 建议 | `PB12` | HX711 数据输出引脚，接 F4 普通 GPIO 输入 |
| `hx711_sck_gpio` | 建议 | `PB13` | HX711 时钟引脚，接 F4 普通 GPIO 输出 |
| `hx711_gain` | 建议 | `128` | HX711 通道 A 常用增益，可按实际接线调整 |
| `conveyor_stepper_driver` | 建议 | `Emm42_V5.0` | 传送带使用的闭环 42 步进电机驱动模块 |
| `conveyor_stepper_package` | 建议 | `industrial` | 用户购买的张大头 Emm42_V5.0 工业套餐，文档按该套餐记录 |
| `conveyor_stepper_control_mode` | 强烈建议 | `uart_serial` | 本项目按串口控制，不按 STEP/DIR 脉冲控制记录 |
| `conveyor_stepper_uart_device` | 强烈建议 | `USART3` | F4 连接 Emm42_V5.0 的串口外设或软件串口名称 |
| `conveyor_stepper_uart_baudrate` | 强烈建议 | `115200` | Emm42_V5.0 串口波特率，按驱动器实际配置填写 |
| `conveyor_stepper_slave_address` | 建议 | `1` | 串口协议中的电机地址，单电机通常固定为 1 |
| `edge_software_version` | 建议 | `edge-1.0.0` | MP157 上传程序版本 |
| `model_bundle_version` | 建议 | `unet-mbv3-20260516` | 本次部署的模型包版本 |

## 4. 当前云端接口清单

| 步骤 | 方法与路径 | 完整地址 | 作用 |
|---:|---|---|---|
| 1 | `POST /api/v1/auth/login` | `http://119.91.65.122/api/v1/auth/login` | 登录云端，保存 Cookie |
| 2 | `GET /api/v1/devices?limit=100` | `http://119.91.65.122/api/v1/devices?limit=100` | 首次联调时按 `device_code` 找 `device_id` |
| 3 | `GET /api/v1/parts?limit=100` | `http://119.91.65.122/api/v1/parts?limit=100` | 首次联调时按 `part_code` 找 `part_id` |
| 4 | `POST /api/v1/records` | `http://119.91.65.122/api/v1/records` | 创建检测主记录 |
| 5 | `POST /api/v1/uploads/cos/prepare` | `http://119.91.65.122/api/v1/uploads/cos/prepare` | 为图片申请 COS 预签名上传地址 |
| 6 | `PUT upload_url` | COS 返回的完整 URL | 上传图片二进制到腾讯云 COS |
| 7 | `POST /api/v1/records/{record_id}/files` | `http://119.91.65.122/api/v1/records/{record_id}/files` | 登记图片对象元数据 |
| 8 | `GET /api/v1/records/{record_id}` | `http://119.91.65.122/api/v1/records/{record_id}` | 联调时确认记录与图片是否入库 |

## 5. 登录请求

### 5.1 请求体

```json
{
  "account": "edge_mp157",
  "password": "<现场配置的密码>"
}
```

| 字段 | 类型 | 要求 | 约束 | 说明 |
|---|---|---:|---|---|
| `account` | string | 必须 | 3 到 128 字符 | 云端账号名或邮箱 |
| `password` | string | 必须 | 1 到 128 字符 | 云端账号密码 |

### 5.2 curl 示例

```bash
curl --interface ppp0 \
  -c /tmp/yunduan_cookie.txt \
  -H "Content-Type: application/json" \
  -X POST "http://119.91.65.122/api/v1/auth/login" \
  -d '{
    "account": "edge_mp157",
    "password": "<现场配置的密码>"
  }'
```

| 参数 | 说明 |
|---|---|
| `-c /tmp/yunduan_cookie.txt` | 保存服务端返回的会话 Cookie |
| `-b /tmp/yunduan_cookie.txt` | 后续请求带上这份 Cookie |
| `--interface ppp0` | 强制走 EC20 PPP 网络；如果现场不是 PPP，可去掉 |

## 6. 设备与零件标识

### 6.1 设备信息

云端设备管理只接受 `device_type=mp157` 的主控设备。STM32F4 的状态通过检测记录的 JSON 上下文字段上报，不要在云端创建设备类型为 `f4` 的档案。

| 字段 | 云端位置 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `device_id` | `POST /records` 顶层字段 | 必须 | `1` | 云端设备主键，检测记录必须关联它 |
| `device_code` | `device_context.device_code` | 建议 | `MP157-VIS-01` | 方便现场按设备编码排查 |
| `device_name` | 云端设备表返回 | 可选 | `一号视觉检测主控` | MP157 端通常不用上报 |
| `firmware_version` | 设备管理接口字段或 `device_context` | 建议 | `mp157-linux-1.0.0` | MP157 系统或边缘程序版本 |
| `ip_address` | 设备管理接口字段或 `device_context.network` | 可选 | `10.64.12.8` | PPP 场景 IP 可能变化，作为排障信息即可 |

### 6.2 零件信息

检测记录必须带 `part_id`。如果 MP157 端只知道零件编码，启动时要先调用 `GET /api/v1/parts?limit=100` 拉取映射。

| 字段 | 云端位置 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `part_id` | `POST /records` 顶层字段 | 必须 | `1` | 云端零件主键 |
| `part_code` | `device_context.part_code` | 建议 | `PART-RING-001` | 边缘端本地记录和排障使用 |
| `part_name` | 云端零件表返回 | 可选 | `轴承端盖` | 通常由云端展示，不要求 MP157 每次上报 |
| `part_category` | 云端零件表返回 | 可选 | `金属件` | 统计分类由云端维护 |

## 7. 检测主记录请求

接口：`POST http://119.91.65.122/api/v1/records`

检测主记录只发送结构化信息，不直接发送图片二进制。图片必须走 COS 上传和文件登记流程。

### 7.1 完整请求示例

```json
{
  "record_no": "MP157-VIS-01-20260516-143012-0001",
  "part_id": 1,
  "device_id": 1,
  "result": "bad",
  "review_status": "pending",
  "surface_result": "bad",
  "backlight_result": "good",
  "eddy_result": "uncertain",
  "defect_type": "scratch",
  "defect_desc": "UNet 分割到疑似划痕区域，MobileNetV3-Small 分类为 scratch，最大置信度 0.91。",
  "confidence_score": 0.91,
  "vision_context": {
    "camera": {
      "camera_id": "usb-camera-0",
      "image_width": 1280,
      "image_height": 720,
      "pixel_format": "RGB888",
      "exposure_us": 8000,
      "gain": 1.5,
      "light_source": "ring-led",
      "trigger_source": "f4_photoelectric"
    },
    "roi": {
      "x": 120,
      "y": 80,
      "w": 1040,
      "h": 560
    },
    "unet": {
      "model_name": "UNet",
      "model_version": "unet-surface-20260516",
      "input_width": 512,
      "input_height": 512,
      "threshold": 0.5,
      "mask_area_px": 3480,
      "mask_area_ratio": 0.0067,
      "max_component_area_px": 2120,
      "component_count": 2,
      "defect_regions": [
        {
          "region_id": 1,
          "x": 312,
          "y": 184,
          "w": 96,
          "h": 35,
          "area_px": 2120,
          "area_ratio": 0.0041,
          "mask_score_mean": 0.86,
          "mask_score_max": 0.97
        }
      ]
    },
    "mobilenetv3_small": {
      "model_name": "MobileNetV3-Small",
      "model_version": "mbv3-small-defect-20260516",
      "input_width": 224,
      "input_height": 224,
      "top1_label": "scratch",
      "top1_score": 0.91,
      "topk": [
        {
          "label": "scratch",
          "score": 0.91
        },
        {
          "label": "stain",
          "score": 0.06
        },
        {
          "label": "dent",
          "score": 0.03
        }
      ]
    },
    "defect_boxes": [
      {
        "x": 312,
        "y": 184,
        "w": 96,
        "h": 35,
        "label": "scratch",
        "score": 0.91,
        "source": "unet_mask_component"
      }
    ]
  },
  "sensor_context": {
    "ec20": {
      "interface": "ppp0",
      "rssi": 18,
      "csq_raw": "18,99",
      "operator": "CMCC",
      "network_registered": true
    },
    "f4_uart": {
      "device": "/dev/ttySTM1",
      "baudrate": 115200,
      "status": "ok",
      "last_frame_seq": 128,
      "last_frame_crc_ok": true,
      "last_frame_at": "2026-05-16T14:30:11.900+08:00"
    },
    "ldc1614_eddy_current": {
      "module_name": "LDC1614电感检测模块",
      "chip_vendor": "TI",
      "chip_model": "LDC1614",
      "interface": "I2C",
      "i2c_bus": "I2C1",
      "i2c_address": "0x2A",
      "channel_count": 4,
      "resolution_bits": 28,
      "supply_voltage_v": 3.3,
      "sensor_excitation_frequency_hz": 1000000,
      "rp_parallel_ohm": 10000,
      "coil_diameter_mm": 18.0,
      "recommended_range_mm": 36.0,
      "channels": [
        {
          "channel": 0,
          "enabled": true,
          "coil_name": "outer_coil_ch0",
          "raw_code": 84231520,
          "baseline_raw_code": 84210000,
          "delta_raw_code": 21520,
          "delta_ratio": 0.0002555,
          "frequency_hz": 1185000,
          "inductance_uh": 12.84,
          "quality": "ok",
          "decision": "metal_detected"
        },
        {
          "channel": 1,
          "enabled": true,
          "coil_name": "outer_coil_ch1",
          "raw_code": 84208000,
          "baseline_raw_code": 84207000,
          "delta_raw_code": 1000,
          "delta_ratio": 0.0000119,
          "frequency_hz": 1186200,
          "inductance_uh": 12.79,
          "quality": "ok",
          "decision": "normal"
        }
      ],
      "overall_decision": "metal_detected"
    },
    "weighing": {
      "module_type": "hx711",
      "module_name": "HX711称重传感器实验套装",
      "dout_gpio": "PB12",
      "sck_gpio": "PB13",
      "gain": 128,
      "sample_rate_hz": 10,
      "raw_adc": 8342210,
      "tare_raw_adc": 8210000,
      "filtered_raw_adc": 8339820,
      "gross_weight_g": 126.2,
      "net_weight_g": 124.8,
      "stable": true,
      "sample_count": 10,
      "stable_window_g": 0.2,
      "calibration_factor": 1024.5,
      "zero_offset": 8210000,
      "capacity_g": 5000,
      "temperature_c": 36.5,
      "overload": false,
      "decision": "pass"
    },
    "conveyor_motor": {
      "motor_type": "closed_loop_stepper",
      "driver_model": "Emm42_V5.0",
      "motor_frame": "42",
      "package_variant": "industrial",
      "control_mode": "uart_serial",
      "uart_device": "USART3",
      "uart_tx_gpio": "PB10",
      "uart_rx_gpio": "PB11",
      "uart_baudrate": 115200,
      "slave_address": 1,
      "command_mode": "speed",
      "running": true,
      "direction": "forward",
      "enabled": true,
      "microstep": 16,
      "steps_per_rev": 200,
      "target_rpm": 180.0,
      "actual_rpm": 177.8,
      "target_speed_mm_s": 120.0,
      "actual_speed_mm_s": 118.5,
      "target_position_steps": 25600,
      "actual_position_steps": 25480,
      "target_position_mm": 420.5,
      "actual_position_mm": 418.6,
      "encoder_count": 15360,
      "position_error_steps": 120,
      "last_command_hex": "01 F6 01 00 B4 00 10 6B",
      "last_response_hex": "01 F6 02 6B",
      "last_response_ok": true,
      "stall_detected": false,
      "over_current": false,
      "over_temperature": false,
      "jam_detected": false,
      "driver_fault": false,
      "fault_code": null,
      "last_action": "move_to_camera"
    },
    "f4_io": {
      "photoelectric_triggered": true,
      "limit_switch_in": false,
      "limit_switch_out": false,
      "emergency_stop": false
    },
    "f4_control_state": {
      "last_command": "capture_and_measure",
      "rejector_action": "none",
      "last_command_seq": 128,
      "alarm_code": null
    }
  },
  "decision_context": {
    "pipeline": "UNet + MobileNetV3-Small",
    "pipeline_version": "unet-mbv3-20260516",
    "decision_rule": "bad when unet mask area ratio >= 0.003 and mobilenet top1 score >= 0.8",
    "overall_threshold": 0.8,
    "unet_threshold": 0.5,
    "classification_threshold": 0.8,
    "cycle_ms": 238,
    "preprocess_ms": 28,
    "unet_inference_ms": 116,
    "mobilenet_inference_ms": 34,
    "postprocess_ms": 60,
    "need_ai_review": true,
    "decision_reason": "mask_area_ratio 超过阈值，且分类 scratch 置信度 0.91。"
  },
  "device_context": {
    "device_code": "MP157-VIS-01",
    "part_code": "PART-RING-001",
    "edge_software_version": "edge-1.0.0",
    "os": "Linux",
    "kernel": "5.10",
    "model_runtime": "onnxruntime",
    "model_bundle_version": "unet-mbv3-20260516",
    "f4_board_code": "F4-CTRL-01",
    "f4_firmware_version": "f4-0.3.2",
    "network": "EC20 PPP",
    "local_record_dir": "/data/detections/MP157-VIS-01-20260516-143012-0001"
  },
  "captured_at": "2026-05-16T14:30:12.000+08:00",
  "detected_at": "2026-05-16T14:30:12.238+08:00"
}
```

### 7.2 顶层字段说明

| 字段 | 类型 | 上报要求 | 后端约束 | 示例 | 说明 |
|---|---|---:|---|---|---|
| `record_no` | string 或 null | 强烈建议 | 最大 64 字符，全平台唯一 | `MP157-VIS-01-20260516-143012-0001` | MP157 本地生成的检测编号；断网补传和人工排查都依赖它 |
| `part_id` | integer | 必须 | `>=1`，必须属于当前公司 | `1` | 云端已有零件 ID |
| `device_id` | integer | 必须 | `>=1`，必须属于当前公司 | `1` | 云端已有 MP157 设备 ID |
| `result` | enum | 必须 | `good` / `bad` / `uncertain` | `bad` | 本次检测最终初判结果 |
| `review_status` | enum | 可选 | `pending` / `reviewed` / `ai_reserved` | `pending` | MP157 初检一般传 `pending` 或不传，后端默认 `pending` |
| `surface_result` | enum 或 null | 建议 | `good` / `bad` / `uncertain` | `bad` | 表面视觉结果，UNet 与 MobileNetV3-Small 的主结果通常落这里 |
| `backlight_result` | enum 或 null | 可选 | `good` / `bad` / `uncertain` | `good` | 背光轮廓检测结果；没有背光检测时传 `null` 或省略 |
| `eddy_result` | enum 或 null | 可选 | `good` / `bad` / `uncertain` | `uncertain` | 涡流或内部检测结果；没有涡流检测时传 `null` 或省略 |
| `defect_type` | string 或 null | 不良时建议 | 最大 128 字符 | `scratch` | 缺陷类型，用于统计缺陷分布 |
| `defect_desc` | string 或 null | 不良时建议 | 文本 | `表面左上区域疑似划痕` | 给人工审核看的缺陷描述 |
| `confidence_score` | number 或 null | 建议 | `0 <= value <= 1` | `0.91` | 最终初判置信度，建议取分类 top1 或融合置信度 |
| `vision_context` | object 或 null | 强烈建议 | JSON 对象 | 见第 8 节 | 视觉采集、UNet、MobileNetV3-Small、缺陷框等信息 |
| `sensor_context` | object 或 null | 建议 | JSON 对象 | 见第 9 节 | EC20、F4 串口、传感器、执行器状态 |
| `decision_context` | object 或 null | 强烈建议 | JSON 对象 | 见第 10 节 | 判定规则、阈值、耗时、是否需要复核 |
| `device_context` | object 或 null | 建议 | JSON 对象 | 见第 11 节 | MP157、F4、软件、模型、网络和本地缓存信息 |
| `captured_at` | ISO datetime | 必须 | 需要带时区 | `2026-05-16T14:30:12.000+08:00` | 相机真正拍到图片的时间，历史记录主排序字段 |
| `detected_at` | ISO datetime 或 null | 建议 | 需要带时区 | `2026-05-16T14:30:12.238+08:00` | 模型完成检测的时间 |
| `uploaded_at` | ISO datetime 或 null | 通常不传 | 需要带时区 | `2026-05-16T14:30:16+08:00` | 主图片上传完成时间；建议由文件登记接口自动回写 |
| `storage_last_modified` | ISO datetime 或 null | 通常不传 | 需要带时区 | `2026-05-16T14:30:16+08:00` | COS 对象最后修改时间；有 COS 响应头时再登记 |

## 8. `vision_context` 视觉与模型输出字段

`vision_context` 是 MP157 上报模型输出的核心位置。云端当前不会强制校验内部结构，但为了前端展示、AI 复核和后续统计稳定，建议固定以下结构。

### 8.1 相机与图像字段

| JSON 路径 | 类型 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `camera.camera_id` | string | 建议 | `usb-camera-0` | 摄像头编号或设备节点 |
| `camera.image_width` | integer | 强烈建议 | `1280` | 原图宽度，像素 |
| `camera.image_height` | integer | 强烈建议 | `720` | 原图高度，像素 |
| `camera.pixel_format` | string | 建议 | `RGB888` | 输入图像格式 |
| `camera.exposure_us` | number | 建议 | `8000` | 曝光时间，微秒 |
| `camera.gain` | number | 建议 | `1.5` | 相机增益 |
| `camera.light_source` | string | 可选 | `ring-led` | 光源类型 |
| `camera.trigger_source` | string | 可选 | `f4_photoelectric` | 触发来源 |
| `roi.x` | integer | 可选 | `120` | ROI 左上角 x |
| `roi.y` | integer | 可选 | `80` | ROI 左上角 y |
| `roi.w` | integer | 可选 | `1040` | ROI 宽度 |
| `roi.h` | integer | 可选 | `560` | ROI 高度 |

### 8.2 UNet 分割输出字段

| JSON 路径 | 类型 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `unet.model_name` | string | 强烈建议 | `UNet` | 固定记录模型结构名称 |
| `unet.model_version` | string | 强烈建议 | `unet-surface-20260516` | 当前 UNet 权重或模型包版本 |
| `unet.input_width` | integer | 建议 | `512` | UNet 输入宽度 |
| `unet.input_height` | integer | 建议 | `512` | UNet 输入高度 |
| `unet.threshold` | number | 强烈建议 | `0.5` | mask 二值化阈值 |
| `unet.mask_area_px` | integer | 强烈建议 | `3480` | 所有缺陷 mask 面积，像素 |
| `unet.mask_area_ratio` | number | 强烈建议 | `0.0067` | mask 面积占 ROI 或整图比例 |
| `unet.max_component_area_px` | integer | 建议 | `2120` | 最大连通域面积 |
| `unet.component_count` | integer | 建议 | `2` | 缺陷连通域数量 |
| `unet.defect_regions[].region_id` | integer | 建议 | `1` | 缺陷区域序号 |
| `unet.defect_regions[].x` | integer | 强烈建议 | `312` | 缺陷框左上角 x，基于原图坐标 |
| `unet.defect_regions[].y` | integer | 强烈建议 | `184` | 缺陷框左上角 y，基于原图坐标 |
| `unet.defect_regions[].w` | integer | 强烈建议 | `96` | 缺陷框宽度 |
| `unet.defect_regions[].h` | integer | 强烈建议 | `35` | 缺陷框高度 |
| `unet.defect_regions[].area_px` | integer | 建议 | `2120` | 单个区域 mask 面积 |
| `unet.defect_regions[].area_ratio` | number | 建议 | `0.0041` | 单个区域面积比例 |
| `unet.defect_regions[].mask_score_mean` | number | 建议 | `0.86` | 区域内平均 mask 置信度 |
| `unet.defect_regions[].mask_score_max` | number | 建议 | `0.97` | 区域内最大 mask 置信度 |

### 8.3 MobileNetV3-Small 分类输出字段

| JSON 路径 | 类型 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `mobilenetv3_small.model_name` | string | 强烈建议 | `MobileNetV3-Small` | 固定记录分类模型结构名称 |
| `mobilenetv3_small.model_version` | string | 强烈建议 | `mbv3-small-defect-20260516` | 当前分类模型版本 |
| `mobilenetv3_small.input_width` | integer | 建议 | `224` | 分类模型输入宽度 |
| `mobilenetv3_small.input_height` | integer | 建议 | `224` | 分类模型输入高度 |
| `mobilenetv3_small.top1_label` | string | 强烈建议 | `scratch` | 分类第一名标签 |
| `mobilenetv3_small.top1_score` | number | 强烈建议 | `0.91` | 分类第一名置信度 |
| `mobilenetv3_small.topk[].label` | string | 建议 | `scratch` | 候选标签 |
| `mobilenetv3_small.topk[].score` | number | 建议 | `0.91` | 候选标签置信度 |

### 8.4 缺陷框字段

`defect_boxes` 用于前端叠加显示，也方便 AI 复核快速定位图片区域。

| JSON 路径 | 类型 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `defect_boxes[].x` | integer | 强烈建议 | `312` | 左上角 x，原图坐标 |
| `defect_boxes[].y` | integer | 强烈建议 | `184` | 左上角 y，原图坐标 |
| `defect_boxes[].w` | integer | 强烈建议 | `96` | 框宽 |
| `defect_boxes[].h` | integer | 强烈建议 | `35` | 框高 |
| `defect_boxes[].label` | string | 强烈建议 | `scratch` | 缺陷标签 |
| `defect_boxes[].score` | number | 建议 | `0.91` | 该框置信度 |
| `defect_boxes[].source` | string | 建议 | `unet_mask_component` | 框来源，例如分割连通域或分类窗口 |

## 9. `sensor_context` 传感器与 STM32F4 字段

`sensor_context` 用于放 EC20 网络状态、F4 串口帧、LDC1614 涡流/电感检测、称重采样、传送带电机控制和普通 IO 状态。它不要求云端预先建 F4 设备。

F4 在本系统里的职责建议固定为三类：

| F4 职责 | 建议 JSON 块 | 说明 |
|---|---|---|
| 涡流/电感检测 | `ldc1614_eddy_current` | 记录 TI LDC1614 4 通道电感检测模块的配置、原始码、基线、差值和通道判定 |
| 称重检测 | `weighing` | 记录称重 ADC 原始值、去皮值、毛重、净重、稳定状态和称重判定 |
| 传送带控制 | `conveyor_motor` / `f4_control_state` | 记录 Emm42_V5.0 工业套餐闭环 42 步进电机的串口配置、运行速度、位置、编码器、卡滞、驱动故障和最近控制命令 |

### 9.1 EC20 与 F4 串口基础字段

| JSON 路径 | 类型 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `ec20.interface` | string | 建议 | `ppp0` | EC20 PPP 网卡名 |
| `ec20.rssi` | integer | 建议 | `18` | 从 `AT+CSQ` 解析出的信号值 |
| `ec20.csq_raw` | string | 可选 | `18,99` | 原始 CSQ 返回 |
| `ec20.operator` | string | 可选 | `CMCC` | 运营商 |
| `ec20.network_registered` | boolean | 建议 | `true` | 蜂窝网络是否注册成功 |
| `f4_uart.device` | string | 建议 | `/dev/ttySTM1` | MP157 串口设备 |
| `f4_uart.baudrate` | integer | 建议 | `115200` | 串口波特率 |
| `f4_uart.status` | string | 强烈建议 | `ok` | `ok` / `timeout` / `crc_error` / `disconnected` |
| `f4_uart.last_frame_seq` | integer | 建议 | `128` | 最近一帧序号 |
| `f4_uart.last_frame_crc_ok` | boolean | 建议 | `true` | 最近一帧 CRC 是否正确 |
| `f4_uart.last_frame_at` | ISO datetime | 建议 | `2026-05-16T14:30:11.900+08:00` | 最近收到 F4 数据的时间 |

### 9.2 LDC1614 涡流/电感检测字段

图中涡流模块可按 `TI LDC1614` 记录：4 通道、最高 28 位分辨率、I2C 接口、2.7V 到 3.6V 供电、传感器激励频率 1kHz 到 10MHz。图中建议的感应范围是大于线圈直径的 2 倍，因此文档里同时记录 `coil_diameter_mm` 和 `recommended_range_mm`，方便后续排查检测距离是否合理。

| JSON 路径 | 类型 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `ldc1614_eddy_current.module_name` | string | 建议 | `LDC1614电感检测模块` | 模块名称 |
| `ldc1614_eddy_current.chip_vendor` | string | 建议 | `TI` | 芯片品牌 |
| `ldc1614_eddy_current.chip_model` | string | 强烈建议 | `LDC1614` | 芯片型号 |
| `ldc1614_eddy_current.interface` | string | 强烈建议 | `I2C` | 模块通信接口 |
| `ldc1614_eddy_current.i2c_bus` | string | 建议 | `I2C1` | F4 使用的 I2C 外设 |
| `ldc1614_eddy_current.i2c_address` | string | 建议 | `0x2A` | LDC1614 7 位地址，按实际 ADDR 引脚配置填写 |
| `ldc1614_eddy_current.channel_count` | integer | 强烈建议 | `4` | LDC1614 通道数量 |
| `ldc1614_eddy_current.resolution_bits` | integer | 强烈建议 | `28` | 转换分辨率 |
| `ldc1614_eddy_current.supply_voltage_v` | number | 建议 | `3.3` | 模块供电电压，允许范围 2.7V 到 3.6V |
| `ldc1614_eddy_current.sensor_excitation_frequency_hz` | integer | 建议 | `1000000` | LC 传感器激励频率，图中范围 1kHz 到 10MHz |
| `ldc1614_eddy_current.rp_parallel_ohm` | number | 可选 | `10000` | Rp 等效并联电阻，图中参考范围 1KΩ 到 100KΩ |
| `ldc1614_eddy_current.coil_diameter_mm` | number | 建议 | `18.0` | 外接检测线圈直径 |
| `ldc1614_eddy_current.recommended_range_mm` | number | 建议 | `36.0` | 建议感应范围，按大于线圈直径 2 倍记录 |
| `ldc1614_eddy_current.channels[].channel` | integer | 强烈建议 | `0` | LDC1614 通道号，0 到 3 |
| `ldc1614_eddy_current.channels[].enabled` | boolean | 建议 | `true` | 该通道是否启用 |
| `ldc1614_eddy_current.channels[].coil_name` | string | 建议 | `outer_coil_ch0` | 线圈或安装位置名称 |
| `ldc1614_eddy_current.channels[].raw_code` | integer | 强烈建议 | `84231520` | 28 位原始转换值或拼接后的原始码 |
| `ldc1614_eddy_current.channels[].baseline_raw_code` | integer | 强烈建议 | `84210000` | 空载或标准件基线原始码 |
| `ldc1614_eddy_current.channels[].delta_raw_code` | integer | 强烈建议 | `21520` | 当前值与基线差值 |
| `ldc1614_eddy_current.channels[].delta_ratio` | number | 建议 | `0.0002555` | 差值比例，便于跨设备比较 |
| `ldc1614_eddy_current.channels[].frequency_hz` | number | 建议 | `1185000` | 换算后的谐振频率 |
| `ldc1614_eddy_current.channels[].inductance_uh` | number | 可选 | `12.84` | 按 LC 参数换算出的电感量 |
| `ldc1614_eddy_current.channels[].quality` | string | 建议 | `ok` | `ok` / `saturated` / `open_coil` / `noise_high` |
| `ldc1614_eddy_current.channels[].decision` | string | 建议 | `metal_detected` | 单通道判定，例如 `normal` / `metal_detected` / `abnormal` |
| `ldc1614_eddy_current.overall_decision` | string | 强烈建议 | `metal_detected` | 涡流模块综合判定 |

### 9.3 HX711 称重模块字段

你当前称重模块使用的是 HX711 称重传感器实验套装。HX711 通常不是 I2C 或 SPI，而是由 F4 使用 `DOUT` 和 `SCK` 两根 GPIO 读取 24 位称重 ADC 数据；上报时既要记录换算后的重量，也要保留原始码、去皮基线、滤波值和标定系数，便于后续追溯称重偏差。

| JSON 路径 | 类型 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `weighing.module_type` | string | 强烈建议 | `hx711` | 固定标识当前称重模块类型 |
| `weighing.module_name` | string | 建议 | `HX711称重传感器实验套装` | 模块名称，便于现场确认硬件 |
| `weighing.dout_gpio` | string | 强烈建议 | `PB12` | HX711 `DOUT` 数据输出脚连接到 F4 的 GPIO |
| `weighing.sck_gpio` | string | 强烈建议 | `PB13` | HX711 `SCK` 时钟脚连接到 F4 的 GPIO |
| `weighing.gain` | integer | 强烈建议 | `128` | HX711 增益，常见值为 128、64 或 32 |
| `weighing.sample_rate_hz` | integer | 建议 | `10` | HX711 输出速率，常见 10Hz 或 80Hz |
| `weighing.raw_adc` | integer | 强烈建议 | `8342210` | 当前 HX711 24 位原始读数，按符号扩展后的整数记录 |
| `weighing.tare_raw_adc` | integer | 强烈建议 | `8210000` | 去皮基线原始值 |
| `weighing.filtered_raw_adc` | integer | 建议 | `8339820` | 均值、中值或低通滤波后的原始值 |
| `weighing.gross_weight_g` | number | 建议 | `126.2` | 毛重，单位 g |
| `weighing.net_weight_g` | number | 强烈建议 | `124.8` | 净重，单位 g |
| `weighing.stable` | boolean | 强烈建议 | `true` | 称重是否稳定 |
| `weighing.sample_count` | integer | 建议 | `10` | 本次均值或滤波使用的采样数量 |
| `weighing.stable_window_g` | number | 建议 | `0.2` | 判定稳定时允许的重量波动窗口 |
| `weighing.calibration_factor` | number | 建议 | `1024.5` | 标定系数，便于追溯称重换算 |
| `weighing.zero_offset` | integer | 建议 | `8210000` | 零点偏移值，可与 `tare_raw_adc` 一致 |
| `weighing.capacity_g` | number | 建议 | `5000` | 称重传感器量程，单位 g |
| `weighing.temperature_c` | number | 可选 | `36.5` | 称重模块或环境温度 |
| `weighing.overload` | boolean | 建议 | `false` | 是否超过称重范围 |
| `weighing.decision` | string | 建议 | `pass` | 称重判定，例如 `pass` / `underweight` / `overweight` / `unstable` |

### 9.4 传送带电机与 F4 控制字段

你当前传送带电机使用的是张大头 `Emm42_V5.0` 闭环 42 步进电机工业套餐，并且采用串口控制。因此 MP157 不需要把它描述成普通占空比电机，也不要只上传一个占空比数值；F4 应把串口配置、控制模式、目标/实际速度、目标/实际位置、编码器反馈、跟随误差、串口命令响应和故障状态一起放进 `conveyor_motor`。

| JSON 路径 | 类型 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `conveyor_motor.motor_type` | string | 强烈建议 | `closed_loop_stepper` | 固定标识为闭环步进电机 |
| `conveyor_motor.driver_model` | string | 强烈建议 | `Emm42_V5.0` | 张大头闭环步进驱动型号 |
| `conveyor_motor.motor_frame` | string | 建议 | `42` | 42 系列步进电机 |
| `conveyor_motor.package_variant` | string | 强烈建议 | `industrial` | 用户购买的是工业套餐 |
| `conveyor_motor.control_mode` | string | 强烈建议 | `uart_serial` | 本项目采用串口控制 |
| `conveyor_motor.uart_device` | string | 强烈建议 | `USART3` | F4 连接驱动器的串口外设 |
| `conveyor_motor.uart_tx_gpio` | string | 建议 | `PB10` | F4 串口 TX 引脚，按实际接线填写 |
| `conveyor_motor.uart_rx_gpio` | string | 建议 | `PB11` | F4 串口 RX 引脚，按实际接线填写 |
| `conveyor_motor.uart_baudrate` | integer | 强烈建议 | `115200` | 串口波特率，必须与驱动器配置一致 |
| `conveyor_motor.slave_address` | integer | 建议 | `1` | 串口协议中的电机地址 |
| `conveyor_motor.command_mode` | string | 建议 | `speed` | 最近使用的控制模式，例如 `speed` / `position` / `stop` / `home` |
| `conveyor_motor.running` | boolean | 强烈建议 | `true` | 传送带电机是否正在运行 |
| `conveyor_motor.direction` | string | 建议 | `forward` | 运行方向，例如 `forward` / `reverse` / `stop` |
| `conveyor_motor.enabled` | boolean | 强烈建议 | `true` | 驱动器是否处于使能状态 |
| `conveyor_motor.microstep` | integer | 建议 | `16` | 当前细分设置，按驱动器参数填写 |
| `conveyor_motor.steps_per_rev` | integer | 建议 | `200` | 电机一圈基础步数，1.8 度步进电机通常为 200 |
| `conveyor_motor.target_rpm` | number | 建议 | `180.0` | 串口下发的目标转速 |
| `conveyor_motor.actual_rpm` | number | 建议 | `177.8` | 驱动器反馈或 F4 估算的实际转速 |
| `conveyor_motor.target_speed_mm_s` | number | 建议 | `120.0` | 目标线速度 |
| `conveyor_motor.actual_speed_mm_s` | number | 建议 | `118.5` | 实测或估算线速度 |
| `conveyor_motor.target_position_steps` | integer | 建议 | `25600` | 位置模式下的目标步数，速度模式也可记录最近目标位置 |
| `conveyor_motor.actual_position_steps` | integer | 建议 | `25480` | 闭环反馈或 F4 估算的实际步数 |
| `conveyor_motor.target_position_mm` | number | 建议 | `420.5` | 目标输送位置 |
| `conveyor_motor.actual_position_mm` | number | 建议 | `418.6` | 实际输送位置 |
| `conveyor_motor.encoder_count` | integer | 建议 | `15360` | 编码器累计计数或驱动器反馈位置计数 |
| `conveyor_motor.position_error_steps` | integer | 强烈建议 | `120` | 目标位置与实际位置的跟随误差 |
| `conveyor_motor.last_command_hex` | string | 建议 | `01 F6 01 00 B4 00 10 6B` | F4 最近一次发给驱动器的串口命令帧，便于排查协议问题 |
| `conveyor_motor.last_response_hex` | string | 建议 | `01 F6 02 6B` | 驱动器最近一次串口响应帧 |
| `conveyor_motor.last_response_ok` | boolean | 强烈建议 | `true` | 最近一次串口响应是否正确 |
| `conveyor_motor.stall_detected` | boolean | 强烈建议 | `false` | 是否检测到堵转或失步 |
| `conveyor_motor.over_current` | boolean | 建议 | `false` | 驱动器是否过流 |
| `conveyor_motor.over_temperature` | boolean | 建议 | `false` | 驱动器是否过温 |
| `conveyor_motor.jam_detected` | boolean | 强烈建议 | `false` | 是否检测到卡滞 |
| `conveyor_motor.driver_fault` | boolean | 强烈建议 | `false` | 电机驱动器是否报错 |
| `conveyor_motor.fault_code` | string 或 null | 建议 | `null` | 驱动器故障码，没有故障传 `null` |
| `conveyor_motor.last_action` | string | 建议 | `move_to_camera` | 最近动作，例如 `feed_in`、`move_to_camera`、`move_to_weighing`、`reject` |
| `f4_io.photoelectric_triggered` | boolean | 建议 | `true` | 光电开关触发状态 |
| `f4_io.limit_switch_in` | boolean | 可选 | `false` | 入口限位状态 |
| `f4_io.limit_switch_out` | boolean | 可选 | `false` | 出口限位状态 |
| `f4_io.emergency_stop` | boolean | 强烈建议 | `false` | 急停状态 |
| `f4_control_state.last_command` | string | 建议 | `capture_and_measure` | MP157 最近下发给 F4 的业务命令 |
| `f4_control_state.rejector_action` | string | 建议 | `none` | 剔除动作：`none` / `reject` / `pass` |
| `f4_control_state.last_command_seq` | integer | 建议 | `128` | MP157 下发给 F4 的最近命令序号 |
| `f4_control_state.alarm_code` | string 或 null | 建议 | `null` | F4 报警码，没有报警传 `null` |

## 10. `decision_context` 判定逻辑字段

`decision_context` 用于解释为什么本次检测最终是 `good`、`bad` 或 `uncertain`。后续 AI 复核会读取这里的信息。

| JSON 路径 | 类型 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `pipeline` | string | 强烈建议 | `UNet + MobileNetV3-Small` | 检测流水线名称 |
| `pipeline_version` | string | 强烈建议 | `unet-mbv3-20260516` | 模型组合版本 |
| `decision_rule` | string | 强烈建议 | `bad when ...` | 判定规则描述 |
| `overall_threshold` | number | 建议 | `0.8` | 最终阈值 |
| `unet_threshold` | number | 建议 | `0.5` | UNet mask 阈值 |
| `classification_threshold` | number | 建议 | `0.8` | 分类置信度阈值 |
| `cycle_ms` | integer | 强烈建议 | `238` | 从触发到判定完成总耗时 |
| `preprocess_ms` | integer | 建议 | `28` | 预处理耗时 |
| `unet_inference_ms` | integer | 建议 | `116` | UNet 推理耗时 |
| `mobilenet_inference_ms` | integer | 建议 | `34` | MobileNetV3-Small 推理耗时 |
| `postprocess_ms` | integer | 建议 | `60` | 后处理耗时 |
| `need_ai_review` | boolean | 建议 | `true` | 是否建议云端 AI 或人工复核 |
| `decision_reason` | string | 建议 | `mask_area_ratio 超过阈值...` | 给人看的判定原因 |

## 11. `device_context` 边缘设备字段

| JSON 路径 | 类型 | 上报要求 | 示例 | 说明 |
|---|---|---:|---|---|
| `device_code` | string | 强烈建议 | `MP157-VIS-01` | MP157 云端设备编码 |
| `part_code` | string | 建议 | `PART-RING-001` | 零件编码 |
| `edge_software_version` | string | 强烈建议 | `edge-1.0.0` | MP157 上传程序版本 |
| `os` | string | 可选 | `Linux` | 操作系统 |
| `kernel` | string | 可选 | `5.10` | Linux 内核版本 |
| `model_runtime` | string | 建议 | `onnxruntime` | 推理运行时，例如 ONNX Runtime、TFLite、NCNN |
| `model_bundle_version` | string | 强烈建议 | `unet-mbv3-20260516` | 当前模型包版本 |
| `f4_board_code` | string | 建议 | `F4-CTRL-01` | F4 板卡编号 |
| `f4_firmware_version` | string | 建议 | `f4-0.3.2` | F4 固件版本 |
| `network` | string | 建议 | `EC20 PPP` | 网络接入方式 |
| `local_record_dir` | string | 建议 | `/data/detections/...` | MP157 本地缓存目录 |

## 12. 结果枚举与缺陷类型建议

### 12.1 检测结果枚举

| 值 | 含义 | 使用场景 |
|---|---|---|
| `good` | 合格 | UNet 未检出明显缺陷，分类结果为正常或置信度低于缺陷阈值 |
| `bad` | 不合格 | 分割区域和分类置信度满足不良规则 |
| `uncertain` | 待确认 | 图像质量差、传感器异常、模型置信度处在灰区或 F4 数据不完整 |

### 12.2 审核状态枚举

| 值 | 含义 | MP157 上报建议 |
|---|---|---:|
| `pending` | 待人工或 AI 复核 | 建议默认传这个，或者省略让后端默认 |
| `reviewed` | 已复核 | 不建议 MP157 初检时传 |
| `ai_reserved` | AI 预留状态 | 不建议 MP157 初检时传 |

### 12.3 缺陷类型建议

云端当前把 `defect_type` 当字符串保存，建议 MP157 先固定英文小写编码，前端或报表再映射中文。

| 缺陷编码 | 中文含义 | 典型来源 |
|---|---|---|
| `scratch` | 划痕 | MobileNetV3-Small 分类 top1 |
| `dent` | 凹坑 | MobileNetV3-Small 分类 top1 |
| `stain` | 污渍 | MobileNetV3-Small 分类 top1 |
| `deformation` | 变形 | 背光或轮廓检测 |
| `edge_break` | 缺边 | UNet mask 靠近边缘 |
| `foreign_body` | 异物 | UNet 分割 + 分类 |
| `unknown` | 未知缺陷 | UNet 检出但分类置信度不足 |

## 13. 图片文件与 COS 元数据

### 13.1 图片类型

| 图片 | `file_kind` | 上传要求 | 建议文件名 | 作用 |
|---|---|---:|---|---|
| 原图 | `source` | 强烈建议 | `source.jpg` | 留档、人工复核、AI 复核 |
| 标注图 | `annotated` | 强烈建议 | `annotated.jpg` | 画出缺陷框、mask 边界、判定文字，前端详情页优先看 |
| 缩略图 | `thumbnail` | 建议 | `thumbnail.jpg` | 列表或统计预览，节省 4G 流量 |

### 13.2 图片规格建议

| 项目 | 建议 |
|---|---|
| 图片格式 | JPEG |
| `Content-Type` | `image/jpeg` |
| 原图分辨率 | 保持检测原始分辨率，例如 `1280x720` 或 `1920x1080` |
| 标注图分辨率 | 与原图一致 |
| 缩略图宽度 | 320 到 480 像素 |
| 原图 JPEG 质量 | 80 到 90 |
| 缩略图 JPEG 质量 | 65 到 75 |
| 标注图内容 | 缺陷框、mask 轮廓、缺陷标签、置信度、记录编号 |

## 14. COS 上传准备请求

接口：`POST http://119.91.65.122/api/v1/uploads/cos/prepare`

### 14.1 请求体

```json
{
  "record_id": 123,
  "file_kind": "source",
  "file_name": "source.jpg",
  "content_type": "image/jpeg"
}
```

| 字段 | 类型 | 上报要求 | 后端约束 | 说明 |
|---|---|---:|---|---|
| `record_id` | integer 或 null | 建议 | `>=1` | 已创建的检测记录 ID；传它后后端会用记录编号生成 COS 路径 |
| `record_no` | string 或 null | 可选 | 最大 64 字符 | 没有 `record_id` 时可传记录编号；正常流程建议传 `record_id` |
| `file_kind` | enum | 必须 | `source` / `annotated` / `thumbnail` | 图片类型 |
| `file_name` | string | 必须 | 1 到 255 字符 | 原始文件名，后端会取 basename |
| `content_type` | string | 强烈建议 | 最大 128 字符 | JPEG 传 `image/jpeg` |

### 14.2 响应体

```json
{
  "enabled": true,
  "provider": "cos",
  "bucket_name": "your-bucket-1250000000",
  "region": "ap-guangzhou",
  "object_key": "detections/MP157-VIS-01-20260516-143012-0001/source/abc_source.jpg",
  "upload_url": "https://your-bucket-1250000000.cos.ap-guangzhou.myqcloud.com/...",
  "method": "PUT",
  "headers": {
    "Content-Type": "image/jpeg"
  },
  "expires_in_seconds": 3600,
  "message": "COS 预签名地址生成成功。"
}
```

| 字段 | MP157 处理方式 |
|---|---|
| `enabled` | 必须为 `true` 才能真实 PUT 图片；`false` 表示后端 COS 配置未完成或签名失败 |
| `upload_url` | 作为 `curl -X PUT` 的完整目标地址 |
| `headers.Content-Type` | PUT 时必须带同样的值，否则签名可能不匹配 |
| `bucket_name` | 文件登记时原样回传 |
| `region` | 文件登记时原样回传 |
| `object_key` | 文件登记时原样回传 |
| `expires_in_seconds` | 过期后不要复用 URL，需要重新 prepare |

## 15. PUT 图片到 COS

```bash
curl --interface ppp0 \
  -X PUT "<prepare 返回的 upload_url>" \
  -H "Content-Type: image/jpeg" \
  --data-binary "@/data/detections/MP157-VIS-01-20260516-143012-0001/source.jpg" \
  -D /tmp/source_upload_headers.txt
```

| 项目 | 期望 |
|---|---|
| HTTP 状态码 | 通常为 `200` |
| 响应头 `ETag` | 建议保存，文件登记时填入 `etag` |
| 响应头 `Last-Modified` | 如果能取到，转换成 ISO 时间后填入 `storage_last_modified` |
| 失败 `403` | 多数是 URL 过期、Content-Type 不一致、签名不匹配 |
| 失败 `5xx` | 可以重试同一个 URL；如果接近过期，重新 prepare |

## 16. 文件对象登记请求

接口：`POST http://119.91.65.122/api/v1/records/{record_id}/files`

### 16.1 请求体

```json
{
  "file_kind": "source",
  "storage_provider": "cos",
  "bucket_name": "your-bucket-1250000000",
  "region": "ap-guangzhou",
  "object_key": "detections/MP157-VIS-01-20260516-143012-0001/source/abc_source.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 245678,
  "etag": "\"9b2cf535f27731c974343645a3985328\"",
  "uploaded_at": "2026-05-16T14:30:16.000+08:00",
  "storage_last_modified": "2026-05-16T14:30:16.000+08:00"
}
```

### 16.2 字段说明

| 字段 | 类型 | 上报要求 | 后端约束 | 来源 | 说明 |
|---|---|---:|---|---|---|
| `file_kind` | enum | 必须 | `source` / `annotated` / `thumbnail` | MP157 本地文件类型 | 文件用途 |
| `storage_provider` | enum | 可选 | 当前只能是 `cos` | 固定值 | 不传时后端默认 `cos` |
| `bucket_name` | string | 必须 | 1 到 128 字符 | prepare 响应 | COS 存储桶 |
| `region` | string | 必须 | 1 到 64 字符 | prepare 响应 | COS 地域 |
| `object_key` | string | 必须 | 1 到 255 字符 | prepare 响应 | COS 对象路径 |
| `content_type` | string 或 null | 建议 | 最大 128 字符 | 本地文件 MIME | JPEG 传 `image/jpeg` |
| `size_bytes` | integer 或 null | 建议 | `>=0` | 本地 `stat` | 文件大小 |
| `etag` | string 或 null | 建议 | 最大 128 字符 | COS PUT 响应头 | 用于校验对象 |
| `uploaded_at` | ISO datetime 或 null | 建议 | 需要带时区 | MP157 PUT 成功时间 | 不传时后端使用当前服务器时间 |
| `storage_last_modified` | ISO datetime 或 null | 可选 | 需要带时区 | COS 响应头 | 有响应头再传 |

登记 `annotated` 或 `source` 成功后，后端会更新检测主记录的 `uploaded_at`。如果登记的是 `annotated`，它会优先作为主结果图时间。

## 17. 时间字段要求

所有传给后端的时间都必须是带时区的 ISO 8601 字符串。

| 字段 | 谁生成 | 含义 | 示例 |
|---|---|---|---|
| `captured_at` | MP157 | 相机采集到图片的时间 | `2026-05-16T14:30:12.000+08:00` |
| `detected_at` | MP157 | UNet + MobileNetV3-Small 完成判定时间 | `2026-05-16T14:30:12.238+08:00` |
| `uploaded_at` | MP157 或后端 | 图片 PUT 到 COS 成功或文件登记成功时间 | `2026-05-16T14:30:16.000+08:00` |
| `storage_last_modified` | COS | COS 对象最后修改时间 | `2026-05-16T14:30:16.000+08:00` |
| `f4_uart.last_frame_at` | MP157 | 最近收到 F4 串口帧的时间 | `2026-05-16T14:30:11.900+08:00` |

不要发送没有时区的字符串，例如 `2026-05-16T14:30:12`。如果 MP157 本地使用中国时间，建议统一发送 `+08:00`；如果使用 UTC，发送 `Z` 或 `+00:00`。

## 18. record_no 生成规则

建议格式：

```text
<device_code>-<YYYYMMDD>-<HHMMSS>-<sequence>
```

示例：

```text
MP157-VIS-01-20260516-143012-0001
```

| 组成 | 说明 |
|---|---|
| `device_code` | 设备编码，便于肉眼识别来源 |
| 日期时间 | 使用 `captured_at` 对应的本地时间 |
| `sequence` | 同一秒内递增序号，至少 4 位 |

注意：后端当前会检查 `record_no` 全平台唯一。断网补传时必须复用同一个 `record_no`，不要每次重试都生成新编号。

## 19. MP157 本地缓存文件建议

每条记录一个目录：

```text
/data/detections/
└── MP157-VIS-01-20260516-143012-0001/
    ├── record.json
    ├── source.jpg
    ├── annotated.jpg
    ├── thumbnail.jpg
    ├── model_result.json
    ├── f4_context.json
    ├── upload_state.json
    └── upload.log
```

| 文件 | 保存要求 | 内容 |
|---|---:|---|
| `record.json` | 必须 | `POST /records` 请求体，断网后原样重放 |
| `source.jpg` | 必须 | 原图 |
| `annotated.jpg` | 强烈建议 | 标注图 |
| `thumbnail.jpg` | 建议 | 缩略图 |
| `model_result.json` | 建议 | UNet 和 MobileNetV3-Small 原始输出，便于离线排查 |
| `f4_context.json` | 建议 | F4 最近状态帧和解析值 |
| `upload_state.json` | 必须 | 云端 record_id、各图片上传和登记状态 |
| `upload.log` | 建议 | 上传过程日志 |

`upload_state.json` 示例：

```json
{
  "record_no": "MP157-VIS-01-20260516-143012-0001",
  "record_id": 123,
  "record_created": true,
  "files": {
    "source": {
      "prepared": true,
      "uploaded": true,
      "registered": true,
      "bucket_name": "your-bucket-1250000000",
      "region": "ap-guangzhou",
      "object_key": "detections/MP157-VIS-01-20260516-143012-0001/source/abc_source.jpg",
      "etag": "\"9b2cf535f27731c974343645a3985328\""
    },
    "annotated": {
      "prepared": false,
      "uploaded": false,
      "registered": false,
      "bucket_name": null,
      "region": null,
      "object_key": null,
      "etag": null
    }
  },
  "last_error": null,
  "updated_at": "2026-05-16T14:30:16.000+08:00"
}
```

## 20. 断网补传状态机

| 状态 | 已完成动作 | 失败后怎么恢复 |
|---|---|---|
| `LOCAL_READY` | 本地图片和 `record.json` 已保存 | 等网络恢复后从创建记录开始 |
| `RECORD_CREATED` | 后端已返回 `record_id` | 保存 `record_id`，继续图片 prepare |
| `SOURCE_PREPARED` | 原图已拿到 `upload_url` | 如果 URL 过期，重新 prepare |
| `SOURCE_UPLOADED` | 原图已 PUT 到 COS | 补调文件登记接口 |
| `SOURCE_REGISTERED` | 原图元数据已入库 | 继续标注图或缩略图 |
| `ANNOTATED_REGISTERED` | 标注图已入库 | 继续缩略图或完成 |
| `DONE` | 全部必需图片已登记 | 可按策略清理本地大图 |

重试建议：

| 场景 | 建议处理 |
|---|---|
| 4G 不通 | 不创建新记录，只保留本地缓存 |
| 登录失败 | 停止上传，记录错误，等待账号或网络修复 |
| `record_no_exists` | 不要新建编号；查询或人工确认该记录是否已上传 |
| `record_not_found` | 检查 `record_id` 是否写错或云端记录是否被删除 |
| COS prepare 返回 `enabled=false` | 不要 PUT；记录错误，通知云端检查 COS 配置 |
| PUT COS 返回 `403` | 重新 prepare，确认 `Content-Type` 完全一致 |
| 文件登记失败 | 保留 object_key、bucket、region、etag，恢复后补登记 |

## 21. 最小可跑通请求

第一阶段只要让云端能看到一条记录和一张原图即可。

### 21.1 最小检测记录

```json
{
  "record_no": "MP157-VIS-01-20260516-143012-0001",
  "part_id": 1,
  "device_id": 1,
  "result": "bad",
  "review_status": "pending",
  "surface_result": "bad",
  "defect_type": "scratch",
  "defect_desc": "UNet + MobileNetV3-Small 初检疑似划痕。",
  "confidence_score": 0.91,
  "vision_context": {
    "unet": {
      "model_name": "UNet",
      "model_version": "unet-surface-20260516",
      "threshold": 0.5,
      "mask_area_px": 3480,
      "mask_area_ratio": 0.0067
    },
    "mobilenetv3_small": {
      "model_name": "MobileNetV3-Small",
      "model_version": "mbv3-small-defect-20260516",
      "top1_label": "scratch",
      "top1_score": 0.91
    },
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
  "decision_context": {
    "pipeline": "UNet + MobileNetV3-Small",
    "pipeline_version": "unet-mbv3-20260516",
    "cycle_ms": 238,
    "need_ai_review": true
  },
  "device_context": {
    "device_code": "MP157-VIS-01",
    "edge_software_version": "edge-1.0.0",
    "model_bundle_version": "unet-mbv3-20260516"
  },
  "captured_at": "2026-05-16T14:30:12.000+08:00",
  "detected_at": "2026-05-16T14:30:12.238+08:00"
}
```

### 21.2 最小文件登记

```json
{
  "file_kind": "source",
  "storage_provider": "cos",
  "bucket_name": "your-bucket-1250000000",
  "region": "ap-guangzhou",
  "object_key": "detections/MP157-VIS-01-20260516-143012-0001/source/abc_source.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 245678,
  "etag": "\"9b2cf535f27731c974343645a3985328\"",
  "uploaded_at": "2026-05-16T14:30:16.000+08:00"
}
```

## 22. 完整 curl 联调顺序

### 22.1 健康检查

```bash
curl --interface ppp0 "http://119.91.65.122/health"
```

期望返回：

```json
{"status":"ok"}
```

### 22.2 登录

```bash
curl --interface ppp0 \
  -c /tmp/yunduan_cookie.txt \
  -H "Content-Type: application/json" \
  -X POST "http://119.91.65.122/api/v1/auth/login" \
  -d '{"account":"edge_mp157","password":"<现场配置的密码>"}'
```

### 22.3 查询设备

```bash
curl --interface ppp0 \
  -b /tmp/yunduan_cookie.txt \
  "http://119.91.65.122/api/v1/devices?limit=100"
```

### 22.4 查询零件

```bash
curl --interface ppp0 \
  -b /tmp/yunduan_cookie.txt \
  "http://119.91.65.122/api/v1/parts?limit=100"
```

### 22.5 创建检测记录

```bash
curl --interface ppp0 \
  -b /tmp/yunduan_cookie.txt \
  -H "Content-Type: application/json" \
  -X POST "http://119.91.65.122/api/v1/records" \
  --data-binary "@/data/detections/MP157-VIS-01-20260516-143012-0001/record.json"
```

从响应中保存：

| 返回字段 | 用途 |
|---|---|
| `id` | 后续 prepare 和 files 接口使用，记为 `record_id` |
| `record_no` | 本地核对是否与请求一致 |
| `files` | 新建后通常为空数组 |

### 22.6 为原图申请上传地址

```bash
curl --interface ppp0 \
  -b /tmp/yunduan_cookie.txt \
  -H "Content-Type: application/json" \
  -X POST "http://119.91.65.122/api/v1/uploads/cos/prepare" \
  -d '{
    "record_id": 123,
    "file_kind": "source",
    "file_name": "source.jpg",
    "content_type": "image/jpeg"
  }'
```

### 22.7 PUT 原图到 COS

```bash
curl --interface ppp0 \
  -X PUT "<prepare 返回的 upload_url>" \
  -H "Content-Type: image/jpeg" \
  --data-binary "@/data/detections/MP157-VIS-01-20260516-143012-0001/source.jpg" \
  -D /tmp/source_upload_headers.txt
```

### 22.8 登记原图对象

```bash
curl --interface ppp0 \
  -b /tmp/yunduan_cookie.txt \
  -H "Content-Type: application/json" \
  -X POST "http://119.91.65.122/api/v1/records/123/files" \
  -d '{
    "file_kind": "source",
    "storage_provider": "cos",
    "bucket_name": "your-bucket-1250000000",
    "region": "ap-guangzhou",
    "object_key": "detections/MP157-VIS-01-20260516-143012-0001/source/abc_source.jpg",
    "content_type": "image/jpeg",
    "size_bytes": 245678,
    "etag": "\"9b2cf535f27731c974343645a3985328\"",
    "uploaded_at": "2026-05-16T14:30:16.000+08:00"
  }'
```

## 23. 云端错误响应格式

后端业务错误会返回结构化 JSON：

```json
{
  "code": "record_not_found",
  "message": "检测记录不存在。",
  "details": null,
  "request_id": "..."
}
```

| HTTP 状态 | 常见 `code` | 可能原因 | MP157 处理 |
|---:|---|---|---|
| 401 | `missing_token` 或登录相关错误 | 未登录、Cookie 过期 | 重新登录后重试 |
| 403 | 权限不足 | 账号无当前公司权限 | 停止重试，通知云端配置账号 |
| 404 | `part_not_found` | `part_id` 不存在或不属于当前公司 | 刷新零件映射，必要时人工处理 |
| 404 | `device_not_found` | `device_id` 不存在或不属于当前公司 | 刷新设备映射，确认设备未被删除 |
| 404 | `record_not_found` | 文件登记使用的 `record_id` 不存在 | 检查本地状态文件 |
| 409 | `record_no_exists` | 相同 `record_no` 已入库 | 不要生成新编号；按补传逻辑确认是否已成功 |
| 422 | 请求校验失败 | 字段类型、枚举或时间格式错误 | 修正本地请求体 |
| 5xx | 服务端或 COS 集成异常 | 云端异常 | 指数退避重试，保留本地缓存 |

## 24. MP157 端实现检查清单

| 检查项 | 必须程度 | 通过标准 |
|---|---:|---|
| PPP 网络可用 | 必须 | `curl --interface ppp0 http://119.91.65.122/health` 返回 `{"status":"ok"}` |
| 设备 ID 已缓存 | 必须 | 本地 `device_code` 能映射到云端 `device_id` |
| 零件 ID 已缓存 | 必须 | 本地 `part_code` 能映射到云端 `part_id` |
| 记录编号稳定 | 必须 | 同一检测样本断网补传仍使用同一个 `record_no` |
| 时间带时区 | 必须 | 所有 datetime 都类似 `2026-05-16T14:30:12.000+08:00` |
| 模型输出完整 | 强烈建议 | `vision_context.unet` 与 `vision_context.mobilenetv3_small` 均有版本、阈值、关键结果 |
| 判定规则可解释 | 强烈建议 | `decision_context` 写明阈值、耗时和判定原因 |
| LDC1614 涡流字段完整 | 强烈建议 | `sensor_context.ldc1614_eddy_current` 有芯片型号、I2C 信息、4 通道原始码、基线、差值和综合判定 |
| HX711 称重字段完整 | 强烈建议 | `sensor_context.weighing` 有 `hx711` 类型、DOUT/SCK 引脚、增益、原始码、去皮值、净重、稳定状态和标定系数 |
| 传送带控制字段完整 | 强烈建议 | `sensor_context.conveyor_motor` 有 Emm42_V5.0 驱动型号、工业套餐、串口控制模式、串口参数、电机地址、命令模式、目标/实际转速、目标/实际位置、编码器、跟随误差、串口命令响应、卡滞、驱动故障和最近动作 |
| F4 状态入上下文 | 建议 | F4 串口、普通 IO、报警码和最近控制命令在 `sensor_context` 中可见 |
| 图片走 COS | 必须 | 不把图片二进制塞进 `/records` 请求 |
| 文件登记补偿 | 必须 | PUT 成功但登记失败时，本地能保存 object_key 后续补登记 |
| Cookie 续期 | 必须 | 401 后能重新登录 |

## 25. 不要发送或不要这样做

| 不建议做法 | 原因 |
|---|---|
| 把腾讯云 `COS_SECRET_ID` / `COS_SECRET_KEY` 放到 MP157 | 边缘端泄露后会暴露整个存储桶权限 |
| 把图片 base64 放进 `POST /records` | 当前接口不接收图片二进制，会导致请求巨大且无法进入 COS 流程 |
| 给 STM32F4 单独创建设备并上报 `device_type=f4` | 当前云端设备管理只允许 MP157 主控设备 |
| 发送无时区时间 | 云端和前端会产生排序、统计和延迟计算偏差 |
| 每次重试都生成新的 `record_no` | 会造成重复记录，无法判断同一检测样本是否已经上传 |
| 复用过期的 COS `upload_url` | 预签名 URL 有时效，过期必须重新 prepare |
| 忽略 `Content-Type` 一致性 | prepare 签名时的 `Content-Type` 必须和 PUT 时一致 |
