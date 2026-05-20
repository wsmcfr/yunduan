# Backend MVP

## 作用

该目录用于存放云端 MVP 后端服务，基于：

- FastAPI
- SQLAlchemy
- Alembic
- MySQL
- 腾讯云 COS

## 当前范围

- 用户登录
- 零件管理
- 设备管理
- 检测记录
- 人工审核
- 统计接口
- COS 上传接口预留
- AI 复核接口预留

## 启动前需要配置

复制 `.env.example` 为 `.env`，并填写数据库、JWT、COS 参数。

## 初始化建议

1. 安装依赖：`pip install -e .`
2. 执行迁移：`alembic upgrade head`
3. 初始化默认管理员：`python -m src.scripts.seed_default_admin`

## 2026-05-20 MP157 零件归一与板端回写总结

### 本次后端修改了什么

| 文件 | 作用 | 修改原因 |
|---|---|---|
| `backend/src/services/part_identity.py` | 集中维护 MP157 零件显示名和分类归一规则。 | 历史训练标签 `gasket` 实际代表“波形垫圈”，不能按英文词面显示成“垫片”；`washer`、`splitwasher`、`wave_washer` 也要稳定映射到真实零件。 |
| `backend/src/services/part_service.py` | 列出零件时统一修正历史显示名和分类。 | 避免数据库里旧名称或旧分类直接泄漏到零件管理页。 |
| `backend/src/services/record_service.py` | 创建检测记录时按 `part_code` 复用或自动创建真实零件。 | 好坏结果不能变成两个零件；`gasket_good/gasket_bad` 应归到同一个“波形垫圈”，`washer_good` 才是另一个“平垫圈”。 |
| `backend/tests/test_part_service.py` | 覆盖零件列表和归一规则。 | 防止后续又把 `gasket` 显示为“垫片”。 |
| `backend/tests/test_record_service.py` | 覆盖检测记录自动创建和复用零件。 | 防止模型标签后缀 `_good/_bad` 被误当作零件编码。 |
| `backend/tests/test_detection_record_model.py` | 覆盖检测记录模型字段和设备上下文。 | 确认原始模型标签可以留在 `device_context.class_label`，真实零件仍由 `records.part_id` 表示。 |

### 关键业务规则

| 输入 | 后端应保存/返回的真实零件 | 分类 | 说明 |
|---|---|---|---|
| `gasket`、`gasket_good`、`gasket_bad` | 波形垫圈 | 垫圈类 | 历史训练命名错误，但业务上就是波形垫圈。 |
| `wave_washer` | 波形垫圈 | 垫圈类 | 新命名可以和旧 `gasket` 指向同类实物。 |
| `washer`、`washer_good`、`washer_bad` | 平垫圈 | 垫圈类 | 平垫圈是独立零件，不应并入波形垫圈。 |
| `splitwasher`、`splitwasher_good`、`splitwasher_bad` | 弹性垫圈 | 垫圈类 | 弹性垫圈是独立零件。 |

### 怎么测试

在云端后端目录执行：

```powershell
cd D:\yunfuwu\backend
python -m pytest tests/test_part_service.py tests/test_record_service.py tests/test_detection_record_model.py -q
```

完整回归可以执行：

```powershell
cd D:\yunfuwu\backend
python -m pytest tests -q
```

生产服务验证：

```bash
systemctl status yunduan-backend nginx
systemctl status yunduan-board-review-tunnel-check.timer
ss -ltnp | grep 127.0.0.1:18081
curl -i --max-time 5 http://127.0.0.1:18081/api/v1/review-result
tail -n 80 /var/log/yunduan-board-review-tunnel-check.log
```

`curl` 返回板端 HTTP `404` 属于正常连通性检查，因为该接口业务写入使用 `POST`。如果云端按钮回写失败，先看 `board_sync_error`，再分别检查设备 `board_review_url`、`board_review_token`、云端 `18081` 监听和板端 `/mnt/sdcard/images/upload_history.json` 中是否存在对应 `record_id/record_no`。
