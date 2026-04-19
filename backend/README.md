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
