# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

周报平台块导出工具 — 从 ATE Lab 周报平台 (`note.kxsz.net`) 将指定容器块下的所有子块批量导出为 PDF 文件。

## 项目结构

- `config.ini.example` — 配置文件模板，提交到仓库；使用前复制为 `config.ini` 并填写真实值
- `config.ini` — 实际配置文件（含敏感 Token），已在 `.gitignore` 中，不提交
- `.gitignore` — 排除 `config.ini`
- `get_blocks.py` — 主脚本，单文件实现所有逻辑
- `README.md` — 使用说明

## 架构

脚本为单文件无第三方依赖设计（仅使用 Python 标准库），流程如下：

1. **初始化** — 读取 `config.ini`，调用 API 自动获取 `uid`（`/api/user/getUserInfo`）和 `space_id`（`/api/note/team/list`）
2. **获取块列表** — 通过 `POST /api/note/block/list` 获取容器块的子块 ID 和标题
3. **导出测试** — 先导出第一个子块验证 Token 有效性
4. **批量导出** — 循环调用 `POST /api/note/blockExport` 导出剩余子块为 PDF，间隔 1 秒防限流

## 运行

```bash
# 首次使用
cp config.ini.example config.ini
# 编辑 config.ini 填写 TOKEN 和 BLOCK_LINK

python get_blocks.py
```

## 关键约定

- 输出目录自动命名为 `{容器标题}_pdfs/`
- PDF 文件名按 `{序号}_{标题}.pdf` 格式，序号从 01 开始
- 标题中的特殊字符会被过滤，长度限制 60 字符
