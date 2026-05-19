#!/bin/bash
# 崩铁玩家舆情分析系统 - 启动脚本
# 用法: ./start_app.sh [start|stop|restart|status]

APP_DIR="/Users/chu/python/player_sentiment"
PID_FILE="/tmp/streamlit_sentiment.pid"
LOG_FILE="/tmp/streamlit_sentiment.log"
PORT=8504
STREAMLIT="/Users/chu/.workbuddy/binaries/python/envs/default/bin/streamlit"
APP_FILE="$APP_DIR/sentiment_agent_app.py"

case "$1" in
  start)
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
      echo "❌ 服务已在运行中 (PID: $(cat $PID_FILE))"
    else
      echo "🚀 启动崩铁舆情分析服务..."
      cd "$APP_DIR"
      nohup "$STREAMLIT" run "$APP_FILE" \
        --server.port $PORT \
        --server.headless true \
        --server.runOnSave false \
        --browser.gatherUsageStats false \
        > "$LOG_FILE" 2>&1 &
      echo $! > "$PID_FILE"
      sleep 3
      if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "✅ 服务启动成功！"
        echo "   URL: http://localhost:$PORT"
        echo "   日志: $LOG_FILE"
        echo "   PID: $(cat $PID_FILE)"
      else
        echo "❌ 启动失败，请查看日志: $LOG_FILE"
      fi
    fi
    ;;
  stop)
    if [ -f "$PID_FILE" ]; then
      PID=$(cat "$PID_FILE")
      echo "🛑 停止服务 (PID: $PID)..."
      kill $PID 2>/dev/null
      rm -f "$PID_FILE"
      echo "✅ 服务已停止"
    else
      pkill -f "streamlit run sentiment_agent_app" 2>/dev/null && echo "✅ 服务已停止" || echo "⚠️ 服务未运行"
    fi
    ;;
  restart)
    $0 stop
    sleep 2
    $0 start
    ;;
  status)
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
      PID=$(cat "$PID_FILE")
      echo "✅ 服务运行中 (PID: $PID)"
      echo "   URL: http://localhost:$PORT"
      # 检查HTTP响应
      HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT 2>/dev/null)
      echo "   HTTP状态: $HTTP_CODE"
    else
      echo "❌ 服务未运行"
    fi
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
