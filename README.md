# 梦眠阁 (Dream-Sleep) — AI 智能睡眠管理

> 主力端：微信小程序 | Flutter APP（暂停维护）
> 轻量化改造后：API Only，已移除 Web SPA

专注睡眠改善，基于 CBT-I 认知行为疗法。

## 快速启动

`ash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
`

## 项目结构

`
backend/          # FastAPI 后端（23 个活跃 Router）
miniprogram/      # 微信小程序（32+ 页面）
flutter/          # Flutter APP（暂停维护）
docs/             # 文档（PRD / 功能文档 / 设计规范 / 原型）
deploy/           # Nginx + Docker 部署配置
`

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | FastAPI + SQLAlchemy + MySQL |
| AI | DeepSeek API |
| 小程序 | 微信原生框架 |
| APP | Flutter（暂停维护） |

详见 [功能文档](docs/功能文档.md)
