# 崩铁玩家舆情分析 Agent - CloudRun 部署镜像
FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖（streamlit 需要）
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码和数据文件
COPY sentiment_agent_app.py .
COPY data/ ./data/

# 暴露 Streamlit 默认端口
EXPOSE 8501

# CloudRun 传入 PORT 环境变量，streamlit 需要与之对齐
# 同时禁用自动浏览器打开
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

CMD ["sh", "-c", "streamlit run sentiment_agent_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true --browser.gatherUsageStats false"]
