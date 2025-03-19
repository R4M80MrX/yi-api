# 周易占卜API

这是一个基于FastAPI的周易占卜API服务，提供卦象生成和解读功能。

## 功能特点

- 自动生成卦象
- 基于AI的卦象解读
- 待办事项管理
- 占卜历史记录

## 技术栈

- FastAPI
- Python 3.8+
- DashScope API (通义千问)
- SQLite (用于数据存储)

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/R4M80MrX/yi-api.git
cd yi-api
```

2. 创建虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 设置环境变量：
```bash
cp .env.example .env
# 编辑.env文件，添加你的DASHSCOPE_API_KEY
```

## 运行

```bash
uvicorn main:app --reload
```

服务将在 http://localhost:3002 运行

## API文档

访问 http://localhost:3002/docs 查看完整的API文档

## 许可证

MIT 