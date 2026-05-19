#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成崩铁2026人气评选事件复盘可视化HTML"""

events = [
    {"date": "05-04", "time": "12:00", "icon": "🚀", "title": "活动启动", "desc": "官方发布公告帖，初始期待极高（👍44777）", "type": "start"},
    {"date": "05-05", "time": "12:39", "icon": "📊", "title": "第一阶段开始", "desc": "第一阶段投票正式开启（👍16327）", "type": "phase"},
    {"date": "05-16", "time": "20:26", "icon": "🔥", "title": "最终阶段开始", "desc": "最终阶段正式启动（👍3977）", "type": "phase"},
    {"date": "05-17", "time": "01:19", "icon": "⚠️", "title": "危机爆发", "desc": "投票网页出现大规模故障，绝大多数IP无法投票，但白厄/流萤票数异常暴涨（约70分钟）", "type": "crisis"},
    {"date": "05-17", "time": "02:28", "icon": "🔧", "title": "故障恢复", "desc": "网页服务恢复，但玩家质疑为何恢复后票数不校准", "type": "crisis"},
    {"date": "05-17", "time": "22:56", "icon": "📢", "title": "官方首次回应", "desc": "「列车广播」发帖承认网页遭恶意攻击（👍553，最高赞）", "type": "response"},
    {"date": "05-18", "time": "全天", "icon": "📊", "title": "玩家自发整理证据", "desc": "社区玩家整理票数异常增长对比图，「人工队」说法广泛传播", "type": "reaction"},
    {"date": "05-19", "time": "15:00", "icon": "📞", "title": "玩家投诉", "desc": "玩家拨打米哈游客服电话（400-666-6312）投诉投票不公", "type": "reaction"},
    {"date": "05-19", "time": "23:00", "icon": "😡", "title": "舆情高峰", "desc": "负面评论达到峰值，玩家要求撤换版主、官方道歉", "type": "reaction"},
    {"date": "05-20", "time": "00:00", "icon": "🏁", "title": "投票结束", "desc": "最终结果公布，白厄/流萤/星期日断层领先，大量玩家表示不认结果", "type": "end"},
]

dot_class_map = {
    "start": "dot-start",
    "phase": "dot-phase",
    "crisis": "dot-crisis",
    "response": "dot-response",
    "reaction": "dot-reaction",
    "end": "dot-end",
}
card_class_map = {
    "crisis": "crisis",
    "response": "response",
    "reaction": "reaction",
}

timeline_html = ""
for e in events:
    dc = dot_class_map.get(e["type"], "dot-start")
    cc = card_class_map.get(e["type"], "")
    timeline_html += f"""
    <div class="event">
      <div class="event-dot {dc}">{e["icon"]}</div>
      <div class="event-card {cc}">
        <div class="event-date">05/{e["date"]} {e["time"]}</div>
        <div class="event-title">{e["title"]}</div>
        <div class="event-desc">{e["desc"]}</div>
      </div>
    </div>
"""

html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>崩铁2026人气评选事件复盘</title>
<style>
  * {{ margin:0; padding:0; box-sizing: border-box; }}
  body {{ font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #0a0b27; color: #e0e0e0; min-height: 100vh; line-height: 1.6; }}
  .header {{ background: linear-gradient(135deg, #1a1a4e 0%, #2d1b69 100%); padding: 40px 20px; text-align: center; border-bottom: 2px solid #6c5ce7; }}
  .header h1 {{ font-size: 2em; color: #fff; margin-bottom: 10px; }}
  .header p {{ color: #a29bfe; font-size: 1.1em; }}
  .container {{ max-width: 1000px; margin: 0 auto; padding: 30px 20px; }}

  .sentiment-bar {{ display: flex; gap: 0; height: 60px; border-radius: 12px; overflow: hidden; margin: 20px 0; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }}
  .sentiment-bar > div {{ display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 1.1em; color: #fff; }}
  .pos {{ background: linear-gradient(135deg, #00b894, #00cec9); }}
  .neg {{ background: linear-gradient(135deg, #e17055, #d63031); }}
  .neu {{ background: linear-gradient(135deg, #636e72, #b2bec3); }}

  .timeline {{ position: relative; padding: 20px 0; }}
  .timeline::before {{ content: ''; position: absolute; left: 30px; top: 0; bottom: 0; width: 3px; background: linear-gradient(180deg, #6c5ce7, #a29bfe, #fd79a8); border-radius: 2px; }}

  .event {{ position: relative; padding: 0 0 30px 70px; }}
  .event-dot {{ position: absolute; left: 19px; top: 4px; width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; box-shadow: 0 0 10px rgba(108,92,231,0.5); z-index: 1; }}
  .dot-start {{ background: #6c5ce7; border: 2px solid #a29bfe; }}
  .dot-phase {{ background: #0984e3; border: 2px solid #74b9ff; }}
  .dot-crisis {{ background: #e17055; border: 2px solid #fab1a0; box-shadow: 0 0 15px rgba(225,112,85,0.6); }}
  .dot-response {{ background: #00b894; border: 2px solid #55efc4; }}
  .dot-reaction {{ background: #fdcb6; border: 2px solid #ffeaa7; }}
  .dot-end {{ background: #fd79a8; border: 2px solid #fab1a0; }}

  .event-card {{ background: #1e1e3f; border-radius: 12px; padding: 16px 20px; border-left: 4px solid #6c5ce7; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }}
  .event-card.crisis {{ border-left-color: #e17055; background: #2d1a1a; }}
  .event-card.response {{ border-left-color: #00b894; }}
  .event-card.reaction {{ border-left-color: #fdcb6; }}
  .event-date {{ color: #a29bfe; font-size: 0.85em; font-weight: bold; margin-bottom: 4px; }}
  .event-title {{ color: #fff; font-size: 1.1em; font-weight: bold; margin-bottom: 6px; }}
  .event-desc {{ color: #b2bec3; font-size: 0.95em; }}

  .conflict-box {{ background: #1e1e3f; border-radius: 16px; padding: 24px; margin: 20px 0; border: 1px solid #6c5ce7; }}
  .conflict-title {{ text-align: center; color: #fd79a8; font-size: 1.3em; font-weight: bold; margin-bottom: 20px; }}
  .conflict-rows {{ display: flex; gap: 20px; flex-wrap: wrap; }}
  .conflict-side {{ flex: 1; min-width: 250px; background: #16213e; border-radius: 12px; padding: 16px; }}
  .conflict-side h3 {{ color: #a29bfe; margin-bottom: 10px; font-size: 1em; }}
  .conflict-side ul {{ list-style: none; padding: 0; }}
  .conflict-side li {{ color: #b2bec3; padding: 6px 0; border-bottom: 1px solid #2d1b69; font-size: 0.9em; }}
  .vs {{ display: flex; align-items: center; justify-content: center; font-size: 2em; color: #fd79a8; font-weight: bold; padding: 10px 0; }}

  .score-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
  .score-card {{ background: #1e1e3f; border-radius: 12px; padding: 16px; text-align: center; border: 1px solid #333; }}
  .score-card h4 {{ color: #a29bfe; margin-bottom: 8px; }}
  .score-stars {{ font-size: 1.5em; margin: 8px 0; }}
  .score-card p {{ color: #b2bec3; font-size: 0.85em; text-align: left; }}

  .phase-cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 20px 0; }}
  .phase-card {{ flex: 1; min-width: 180px; background: #1e1e3f; border-radius: 12px; padding: 14px; border-top: 3px solid #6c5ce7; }}
  .phase-card h4 {{ color: #fff; font-size: 0.95em; margin-bottom: 6px; }}
  .phase-card .emoji {{ font-size: 1.2em; }}
  .phase-card p {{ color: #b2bec3; font-size: 0.8em; margin: 4px 0; }}

  h2 {{ color: #a29bfe; margin: 30px 0 15px; font-size: 1.3em; border-left: 4px solid #6c5ce7; padding-left: 12px; }}
  .section-box {{ background: #1a1a3e; border-radius: 12px; padding: 20px; margin: 15px 0; }}

  .footer {{ text-align: center; padding: 30px; color: #636e72; font-size: 0.85em; border-top: 1px solid #2d1b69; }}
</style>
</head>
<body>

<div class="header">
  <h1>🚂 崩铁 2026 人气评选事件复盘</h1>
  <p>2026-05-04 ～ 2026-05-20 | 专业运营视角</p>
</div>

<div class="container">

  <h2>📊 舆情情感分布（"投票"关键词，05-05~05-20）</h2>
  <div class="section-box">
    <div class="sentiment-bar">
      <div class="pos" style="width:10.6%">正面 10.6%</div>
      <div class="neg" style="width:16.0%">负面 16.0%</div>
      <div class="neu" style="width:73.4%">中性 73.4%</div>
    </div>
    <p style="color:#b2bec3;font-size:0.9em;">⚠️ 负面占比 16% 已达黄色预警线。负面热评最高点赞 👍115，影响力远超数量占比。</p>
  </div>

  <h2>🕐 事件时间线</h2>
  <div class="timeline">
    {timeline_html}
  </div>

  <h2>⚡ 事件根本矛盾</h2>
  <div class="conflict-box">
    <div class="conflict-title">根本矛盾 = 玩家对「公平」的期待 &nbsp; vs. &nbsp; 官方对「可控」的需求</div>
    <div class="conflict-rows">
      <div class="conflict-side">
        <h3>🙋 玩家视角</h3>
        <ul>
          <li>• "我认真参与了，结果被后台操作了"</li>
          <li>• "我的投票算什么？"</li>
          <li>• 期待：透明、公正、可监督</li>
          <li>• 底线：至少给我一个解释</li>
        </ul>
      </div>
      <div class="vs">VS</div>
      <div class="conflict-side">
        <h3>🏛️ 官方视角（推测）</h3>
        <ul>
          <li>• "活动热度要维持，票数不够要补"</li>
          <li>• "但不能明说，所以要'控盘'"</li>
          <li>• 需求：可控、美观、不出乱子</li>
          <li>• 现实：控盘被看到了，信誉崩塌</li>
        </ul>
      </div>
    </div>
    <p style="color:#fd79a8;margin-top:15px;text-align:center;font-weight:bold;">🔴 激化点：「控盘」被玩家看到了 → 信任崩塌 → 舆情反噬</p>
  </div>

  <h2>📝 官方决策复盘评分</h2>
  <div class="score-grid">
    <div class="score-card">
      <h4>⏱️ 响应速度</h4>
      <div class="score-stars">⭐⭐</div>
      <p>05-17凌晨危机，当晚22:56才回应，黄金4小时完全浪费。期间社区谣言填补真空。</p>
    </div>
    <div class="score-card">
      <h4>🔍 透明度</h4>
      <div class="score-stars">⭐</div>
      <p>未解释异常票数，未公布校准方案，最终结果公信力为零，大量玩家表示"不认结果"。</p>
    </div>
    <div class="score-card">
      <h4>💚 诚意</h4>
      <div class="score-stars">⭐⭐</div>
      <p>承认了故障，但未道歉、未处理异常票数、未重办，实质性补救为零。</p>
    </div>
    <div class="score-card">
      <h4>💬 社区沟通</h4>
      <div class="score-stars">⭐</div>
      <p>几乎无对话，只有公告。版主完全缺位，未起到"玩家与官方桥梁"作用。</p>
    </div>
  </div>

  <h2>👥 玩家群体行为分析</h2>
  <div class="section-box">
    <div class="phase-cards">
      <div class="phase-card" style="border-top-color:#6c5ce7;">
        <h4>😊 期待期<br><small>05-04 ~ 05-16</small></h4>
        <p class="emoji">📈 积极参与投票</p>
        <p>初始公告帖 👍44777，历史级高赞，说明玩家期待极高。</p>
      </div>
      <div class="phase-card" style="border-top-color:#e17055;">
        <h4>😡 愤怒期<br><small>05-17 凌晨~晚</small></h4>
        <p class="emoji">🔥 截图取证、发帖质疑</p>
        <p>发现无法投票但"有人能投"；社区形成"人工队"共识性叙事。</p>
      </div>
      <div class="phase-card" style="border-top-color:#fdcb6;">
        <h4>📑 组织期<br><small>05-18 ~ 05-19</small></h4>
        <p class="emoji">📑 整理数据、号召投诉</p>
        <p>自发整理票数对比图；拨打客服电话；要求官方道歉和撤换版主。</p>
      </div>
      <div class="phase-card" style="border-top-color:#fd79a8;">
        <h4>🚨 抗争期<br><small>05-20</small></h4>
        <p class="emoji">🏴 不认结果、要求重办</p>
        <p>结果公布后大规模质疑；"这个结果我们不认哦"成为热评。</p>
      </div>
    </div>
    <p style="color:#b2bec3;margin-top:15px;font-size:0.9em;">💡 玩家行为特征：<strong>有证据、有组织、有诉求</strong>（不是情绪化谩骂，而是理性维权）</p>
  </div>

  <h2>💡 关键教训（给未来运营）</h2>
  <div class="section-box">
    <p style="color:#55efc4;margin:8px 0;">✅ <strong>短期补救</strong>：官方需要出面道歉 + 公布票数校准方案（否则信任无法重建）</p>
    <p style="color:#74b9ff;margin:8px 0;">🔧 <strong>中期改进</strong>：投票机制 redesign（绑定账号+活跃门槛+实时公开票数+异常票自动标记）</p>
    <p style="color:#a29bfe;margin:8px 0;">🤝 <strong>长期信任</strong>：官方要从"发公告"变成"对话"（版主应是桥梁，不是防火墙）</p>
    <p style="color:#fd79a8;margin:8px 0;">🔴 <strong>根本启示</strong>：在今天，玩家比官方想象的更有组织、更讲证据、更在意公平。"控盘"成本极高，因为社区会自己"破案"。</p>
  </div>

</div>

<div class="footer">
  <p>崩铁舆情分析 Agent · 2026-05-20 · 专业运营复盘</p>
  <p>数据来源：米游社板块52 实时采集 + 官方公告帖评论分析</p>
</div>

</body>
</html>
"""

output_path = "/Users/chu/python/player_sentiment/2026人气评选事件复盘_可视化.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"✅ 可视化HTML已生成：{output_path}")
