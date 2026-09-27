# 意绘（YiHui）

**意绘** 是一个面向本地工作流的 AI 图像生成与管理工具。它将多 Provider 生图、历史记录、素材管理、节点与标签整理、备份恢复等能力集中在一个本地 Web 界面中。

当前版本：**V0.73**

## 核心功能

- **文生图 / 图生图**：通过配置的 Provider 调用不同图像生成服务。
- **多 Provider 管理**：统一管理 Base URL、模型、调用方式、API Key、代理和生成参数。
- **生图记录管理**：保留提示词、Provider、模型、尺寸、输入图、输出图和执行状态等记录。
- **节点与标签**：通过层级节点、标签、搜索和筛选整理生成内容。
- **图片浏览**：支持原图、缩略图、列表/卡片视图以及本地图片路径读取。
- **数据安全**：支持手动备份、自动备份、JSON/ZIP 导出、恢复预览与恢复。
- **维护工具**：支持路径替换、缩略图缓存清理、失败历史清理等。

## 运行环境

项目主要面向 Windows 本地使用，启动器会优先寻找可用的 Python 环境。

主要依赖：

- Python 3
- Flask 3.0.3
- OpenAI Python SDK 1.99.9
- Pillow 10+
- pytest 8.3.4

完整依赖见 app/requirements.txt。

## 快速开始

### 1. 安装依赖

在仓库根目录执行：

    python -m pip install -r app/requirements.txt

### 2. 准备本地配置

仓库提供脱敏后的配置示例：

    config/AIImageManager.config.example.json

复制为：

    config/AIImageManager.config.json

然后在本地填写需要使用的 Provider、模型和 API Key。

> config/AIImageManager.config.json 已被 .gitignore 排除，不应提交到 Git。

### 3. 启动意绘

Windows 下可以直接双击：

    app/Open-YiHui.cmd

也可以手动启动：

    cd app
    python app.py --open

默认地址：

    http://127.0.0.1:8787/

## 目录结构

    YiHui/
    ├─ app/                  # 主程序、前端、后端与测试
    │  ├─ backend/
    │  ├─ frontend/
    │  ├─ tests/
    │  ├─ app.py
    │  ├─ Open-YiHui.cmd
    │  ├─ requirements.txt
    │  └─ VERSION
    ├─ files/                # 生图调用脚本
    ├─ config/
    │  └─ AIImageManager.config.example.json
    ├─ VERSION_V0.73.txt     # 当前版本标记
    ├─ README.md
    ├─ LICENSE
    └─ .gitignore

以下目录主要由程序运行时生成，并默认不进入 Git：

    backup/
    cache/
    data/
    export/
    generated/
    logs/
    temp/

## 数据与兼容性

软件的用户可见品牌已经统一为 **意绘 / YiHui**。

为兼容已有数据，部分内部文件名和持久化标识仍保留原有名称，例如：

    config/AIImageManager.config.json
    data/AIImageManager.data.sqlite
    AIImageManager.uiState.v1

这些名称属于兼容层，不代表当前产品品牌。

## API Key 与安全

真实 API Key 只应保存在本地配置或本地环境变量中。

请不要将以下内容提交到 Git：

- config/AIImageManager.config.json
- 本地数据库
- 备份文件
- 导出文件
- 日志
- 生图结果
- 任何包含真实 API Key 的脚本或截图

仓库中的 config/AIImageManager.config.example.json 用于展示配置结构，API Key 字段应保持为空。

## 测试

运行完整测试：

    cd app
    python -m pytest -q

发布新版本前建议至少完成：

1. 全量 pytest。
2. 本地服务启动与首页访问。
3. 设置读取/保存。
4. 节点、标签和实例的增删改查。
5. 生图主链路。
6. 备份、导出和恢复闭环。

## 版本

当前版本：

    V0.73

程序版本由 app/VERSION、后端版本常量、前端静态资源版本和根目录版本标记共同保持一致。

## License

本项目采用 **Apache License 2.0**。

完整许可证文本见 LICENSE。
