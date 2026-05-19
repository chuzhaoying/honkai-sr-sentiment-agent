"""
崩坏星穹铁道 · 玩家舆情分析 Agent
===================================
数据来源：https://www.miyoushe.com/sr/home/52
  - 热门帖子 (type=hot)
  - 最新发布 (type=1)
  - 最新回复 (type=2)

采集内容：标题 + 正文 + 评论
分析功能：自动分类 + 情感分析 + 舆情报告

启动：streamlit run sentiment_agent_app.py
"""

import os
import re
import json
import time
import glob
import subprocess
import sys
import random
from datetime import datetime, timedelta, date, timezone

import pandas as pd
import requests
import streamlit as st

# 北京时间（UTC+8）时区，用于统一转换米游社时间戳
CST8 = timezone(timedelta(hours=8))

def ts_to_cst8(ts):
    """将米游社时间戳（秒）转换为北京时间字符串 YYYY-MM-DD HH:MM:SS"""
    if not ts:
        return ""
    # 米游社 created_at 是 UTC+8 的 Unix 时间戳
    return datetime.fromtimestamp(int(ts), tz=CST8).strftime("%Y-%m-%d %H:%M:%S")

# ─────────────────────────────────────────
# 页面设置
# ─────────────────────────────────────────
st.set_page_config(
    page_title="崩铁舆情分析 Agent",
    page_icon="🚂",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
# miyoushe 爬虫脚本目录（本地模式使用，云端部署时不依赖）
MIYOUSHE_DIR = os.path.join(BASE_DIR, "miyoushe")
# 检测是否在云端运行（CloudRun 会设置 PORT 环境变量）
IS_CLOUD = os.environ.get("PORT") is not None

# ─────────────────────────────────────────
# 米游社 API 采集（内置，云端也可用）
# ─────────────────────────────────────────
MIYOUSHE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://www.miyoushe.com/sr/home/52",
    "Origin": "https://www.miyoushe.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def _extract_text(content_raw):
    """清理正文：去除 HTML 标签"""
    if not content_raw:
        return ""
    return re.sub(r'<[^>]+>', '', str(content_raw)).strip()


def fetch_latest_posts(pages_per_sort=5):
    """从米游社 API 实时拉取最新帖子（热门+最新发布+最新回复）"""
    all_posts = []
    gids, forum_id, page_size = 6, 52, 20
    sort_modes = {2: "热门", 1: "最新发布", 3: "最新回复"}
    has_error = False

    for sort_type, sort_name in sort_modes.items():
        last_id = None
        for _ in range(pages_per_sort):
            try:
                params = {"forum_id": forum_id, "gids": gids,
                          "page_size": page_size, "sort_type": sort_type}
                if last_id:
                    params["last_id"] = last_id
                r = requests.get(
                    "https://bbs-api.miyoushe.com/post/wapi/getForumPostList",
                    headers=MIYOUSHE_HEADERS, params=params, timeout=10)
                r.raise_for_status()
                data = r.json()
                if data.get("retcode") != 0:
                    has_error = True
                    break
                post_list = data["data"]["list"]
                if not post_list:
                    break
                for item in post_list:
                    post = item.get("post", {})
                    user = item.get("user", {})
                    stat = item.get("stat", {})
                    all_posts.append({
                        "帖子ID": post.get("post_id", ""),
                        "标题": post.get("subject", ""),
                        "正文": _extract_text(post.get("content", ""))[:3000],
                        "作者": user.get("nickname", ""),
                        "发布时间": ts_to_cst8(post.get("created_at", 0)),
                        "点赞数": stat.get("like_num", 0),
                        "评论数": stat.get("reply_num", 0),
                        "浏览数": stat.get("view_num", 0),
                        "排序方式": sort_name,
                    })
                last_id = data["data"].get("last_id")
                if not last_id:
                    break
                time.sleep(0.5 + random.random() * 1.5)
            except requests.exceptions.Timeout:
                has_error = True
                break
            except requests.exceptions.RequestException:
                has_error = True
                break
            except Exception:
                has_error = True
                break

    if all_posts:
        df = pd.DataFrame(all_posts)
        df = df.drop_duplicates(subset=["帖子ID"], keep="first")
        df["_fetch_error"] = has_error
        return df
    return pd.DataFrame()


def fetch_post_comments(post_id, max_comments=30):
    """拉取单篇帖子的评论"""
    comments = []
    last_id = None
    headers = MIYOUSHE_HEADERS.copy()
    headers["Referer"] = f"https://www.miyoushe.com/sr/article/{post_id}"
    try:
        while True:
            params = {"post_id": post_id, "gids": 6,
                      "page_size": min(max_comments, 50), "order_type": 2}
            if last_id:
                params["last_id"] = last_id
            r = requests.get(
                "https://bbs-api.miyoushe.com/post/wapi/getPostReplies",
                headers=headers, params=params, timeout=10)
            data = r.json()
            if data.get("retcode") != 0:
                break
            reply_list = data["data"].get("list", [])
            if not reply_list:
                break
            for item in reply_list:
                reply = item.get("reply", {})
                user = item.get("user", {})
                stat = item.get("stat", {})
                raw = reply.get("content", "")
                clean = clean_comment(raw)
                if not clean:
                    continue
                comments.append({
                    "帖子ID": post_id,
                    "评论ID": reply.get("reply_id", ""),
                    "评论内容": clean,
                    "评论者": user.get("nickname", ""),
                    "评论时间": ts_to_cst8(reply.get("created_at", 0)),
                    "点赞数": stat.get("like_num", 0),
                })
            if data["data"].get("is_last", True):
                break
            last_id = data["data"].get("last_id")
            if not last_id:
                break
            time.sleep(0.3 + random.random())
    except Exception:
        pass
    return comments


def fetch_latest_comments(posts_df, max_posts=30, max_per_post=20):
    """从最新帖子中采集评论"""
    if posts_df.empty:
        return pd.DataFrame()
    target = posts_df[posts_df["评论数"] >= 1].nlargest(max_posts, "评论数")
    all_comments = []
    for _, row in target.iterrows():
        cmts = fetch_post_comments(str(row["帖子ID"]), max_per_post)
        all_comments.extend(cmts)
        time.sleep(0.3 + random.random())
    if all_comments:
        return pd.DataFrame(all_comments)
    return pd.DataFrame()


# ─────────────────────────────────────────
# 分类体系（基于崩铁社区实际话题）
# ─────────────────────────────────────────
CATEGORY_RULES = {
    "🎮 角色讨论": {
        "keywords": ["角色", "强度", "拉胯", "刮痧", "人权卡", "T0", "T1", "配队",
                     "阵容", "深渊", "忘却之庭", "虚构叙事", "命座", "专武", "光锥",
                     "练度", "输出", "辅助", "生存", "奶妈", "盾", "上", "流萤",
                     "银狼", "花火", "卡芙卡", "景元", "刃", "藿藿", "符玄", "知更鸟",
                     "丹恒", "停云", "黄泉", "砂金", "星期日", "绯英", "欢愉"],
        "color": "#3498db",
    },
    "📖 剧情体验": {
        "keywords": ["主线", "剧情", "活动剧情", "人物塑造", "编剧", "文案", "演出",
                     "CG", "支线", "人设", "刀子", "糖", "CP", "塑造", "伏笔",
                     "新艾利都", "匹诺康尼", "仙舟", "雅利洛", "星核猎手"],
        "color": "#9b59b6",
    },
    "💰 商业化/抽卡": {
        "keywords": ["抽卡", "保底", "定价", "性价比", "骗氪", "逼氪", "氪金", "白嫖",
                     "月卡", "礼包", "池子", "卡池", "歪了", "零氪", "微氪", "重氪",
                     "大保底", "小保底", "星琼", "专票", "抽到", "出货", "沉船",
                     "攒票", "星芒", "抽不抽", "值不值得"],
        "color": "#e67e22",
    },
    "🔧 玩法/攻略": {
        "keywords": ["模拟宇宙", "活动玩法", "肝度", "攻略", "新玩法", "活动",
                     "速通", "遗器", "词条", "主词条", "副词条", "搭配", "配装",
                     "材料", "养成", "培养", "命途", "记忆", "虚无", "存护",
                     "巡猎", "丰饶", "毁灭", "智识", "同谐"],
        "color": "#27ae60",
    },
    "🐛 技术问题": {
        "keywords": ["BUG", "bug", "闪退", "卡顿", "优化", "发烫", "耗电", "黑屏",
                     "掉帧", "延迟", "服务器", "炸服", "登不上", "更新失败", "崩了",
                     "Crash", "卡死", "加载", "网络", "断线"],
        "color": "#e74c3c",
    },
    "🎨 创作/同人": {
        "keywords": ["画", "同人", "cos", "cosplay", "绘画", "约稿", "稿件", "手绘",
                     "产粮", "二创", "剪辑", "视频", "MMD", "表情包", "P图",
                     "手办", "周边", "谷子", "吧唧", "立牌", "透卡", "纪念册"],
        "color": "#1abc9c",
    },
    "📢 社区/官方": {
        "keywords": ["节奏", "争议", "公关", "回应", "声明", "道歉", "延期",
                     "带节奏", "水军", "控评", "竞品", "鸣潮", "绝区零", "原神",
                     "前瞻", "直播", "版本", "更新", "维护", "补偿", "福利",
                     "兑换码", "官方", "投票", "评选"],
        "color": "#95a5a6",
    },
    "💬 日常/闲聊": {
        "keywords": ["签到", "日常", "打卡", "攒票", "回归", "萌新", "提问", "求助",
                     "分享", "展示", "欧皇", "非酋", "出货", "沉船"],
        "color": "#f39c12",
    },
}

# 情感词库
POSITIVE_WORDS = [
    "好评", "太棒了", "良心", "爱了", "封神", "yyds", "绝了", "满分",
    "感动", "惊喜", "宝藏", "好玩", "有趣", "精美", "用心了", "诚意",
    "太香了", "香", "太好了", "终于", "等到了", "满意", "舒服", "爽",
    "赚了", "血赚", "友好", "大方", "给力", "值得", "值了", "必抽",
    "稳了", "喜欢", "好看", "好听", "完美", "优秀", "强", "厉害",
    "牛", "棒", "感谢", "支持", "期待", "推荐", "不错", "好评",
    "超赞", "绝美", "神作", "良心", "吹爆", "太强了",
]

NEGATIVE_WORDS = [
    "垃圾", "坑", "骗氪", "逼氪", "数值膨胀", "长草", "无聊", "退坑", "失望",
    "恶心", "坑爹", "割韭菜", "敷衍", "摆烂", "离谱", "劝退", "吃相难看",
    "拉胯", "寄了", "麻了", "水", "换皮", "暗改", "歪了", "退钱", "血亏",
    "没诚意", "优化差", "闪退", "卡顿", "发烫", "不玩了", "润了", "跑路",
    "差", "烂", "丑", "弱", "废物", "骗人", "虚假", "假的",
    "崩溃", "BUG", "bug", "闪退", "延迟", "卡", "挂了", "服务器",
    "骗", "割", "贵", "死", "完蛋", "滚", "恶心", "吐了",
    "不懂", "不吐不快", "真的无语", "太离谱", "无法理解", "搞不懂",
]


def classify_content(text):
    """对内容进行分类，返回 (分类名, 匹配关键词数, 颜色)"""
    if not text or not isinstance(text, str):
        return ("💬 日常/闲聊", 0, "#f39c12")

    scores = {}
    for cat_name, rule in CATEGORY_RULES.items():
        score = sum(1 for kw in rule["keywords"] if kw in text)
        if score > 0:
            scores[cat_name] = (score, rule["color"])

    if scores:
        best = max(scores.items(), key=lambda x: x[1][0])
        return (best[0], best[1][0], best[1][1])
    return ("💬 日常/闲聊", 0, "#f39c12")


def analyze_sentiment(text):
    """情感分析：positive / negative / neutral"""
    if not text or not isinstance(text, str):
        return "neutral"
    pos = sum(1 for w in POSITIVE_WORDS if w in text)
    neg = sum(1 for w in NEGATIVE_WORDS if w in text)
    if pos > neg:
        return "positive"
    elif neg > pos:
        return "negative"
    return "neutral"


def clean_comment(raw_content):
    """清洗评论：去除表情包标记 _(xxx) 和 HTML 标签"""
    if not raw_content or not isinstance(raw_content, str):
        return ""
    text = str(raw_content)
    # 去除表情包标记
    while True:
        idx = text.find("_(")
        if idx == -1:
            break
        end_idx = text.find(")", idx)
        if end_idx == -1:
            break
        text = text[:idx] + text[end_idx + 1:]
    text = re.sub(r"<[^>]+>", "", text)
    text = " ".join(text.split())
    return text.strip() if len(text.strip()) >= 2 else ""


# ─────────────────────────────────────────
# 数据加载
# ─────────────────────────────────────────
@st.cache_data(ttl=600)
def load_all_data():
    """加载 data/ 下所有 xlsx + 实时采集最新帖子"""
    result = {}
    os.makedirs(DATA_DIR, exist_ok=True)
    xlsx_files = glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
    for path in xlsx_files:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            result[name] = pd.read_excel(path)
        except Exception:
            result[name] = pd.DataFrame()

    # 实时拉取最新帖子（合并到本地数据）
    fetch_error = False
    try:
        live_posts = fetch_latest_posts(pages_per_sort=5)
        if not live_posts.empty:
            fetch_error = live_posts.iloc[0].get("_fetch_error", False) if "_fetch_error" in live_posts.columns else False
            # 移除内部标记列
            if "_fetch_error" in live_posts.columns:
                live_posts = live_posts.drop(columns=["_fetch_error"])
            # 与本地帖子合并去重
            if "miyoushe_posts" in result and not result["miyoushe_posts"].empty:
                combined = pd.concat([result["miyoushe_posts"], live_posts], ignore_index=True)
                combined = combined.drop_duplicates(subset=["帖子ID"], keep="first")
                result["miyoushe_posts"] = combined
            else:
                result["miyoushe_posts"] = live_posts
    except requests.exceptions.Timeout:
        fetch_error = True
    except Exception:
        fetch_error = True

    # 将 fetch_error 标记存到 result 中，供 UI 显示
    result["_fetch_error"] = fetch_error
    return result


@st.cache_data(ttl=600)
def build_analysis_df(raw):
    """构建带分类和情感标注的统一分析表"""
    rows = []

    # ── 帖子 ──
    for src_name, key_col in [("miyoushe_posts", "帖子ID"), ("miyoushe_post_list", "帖子ID")]:
        if src_name in raw and not raw[src_name].empty:
            df = raw[src_name]
            for _, r in df.iterrows():
                title = str(r.get("标题", "") or "")
                if title in ("nan", "None", ""):
                    title = ""
                body = str(r.get("正文", "") or "")
                if body in ("nan", "None"):
                    body = ""
                content = f"{title} {body}".strip()
                if len(content) < 5:
                    continue
                rows.append({
                    "类型": "帖子",
                    "标题": title,
                    "正文": body,
                    "内容": content,
                    "作者": str(r.get("作者", "") or ""),
                    "时间": r.get("发布时间", ""),
                    "点赞数": int(r.get("点赞数", 0) or 0),
                    "评论数": int(r.get("评论数", 0) or 0),
                    "浏览数": int(r.get("浏览数", 0) or 0),
                    "排序": str(r.get("排序方式", "")),
                    "ID": str(r.get(key_col, "")),
                })

    # ── 评论 ──
    if "miyoushe_comments" in raw and not raw["miyoushe_comments"].empty:
        df = raw["miyoushe_comments"]
        for _, r in df.iterrows():
            content = clean_comment(r.get("评论内容", ""))
            if not content:
                continue
            rows.append({
                "类型": "评论",
                "标题": "",
                "正文": "",
                "内容": content,
                "作者": str(r.get("评论者", "") or ""),
                "时间": r.get("评论时间", ""),
                "点赞数": int(r.get("点赞数", 0) or 0),
                "评论数": 0,
                "浏览数": 0,
                "排序": "",
                "ID": str(r.get("评论ID", "")),
            })

    # ── 搜索结果 ──
    if "miyoushe_search_results" in raw and not raw["miyoushe_search_results"].empty:
        df = raw["miyoushe_search_results"]
        for _, r in df.iterrows():
            title = str(r.get("标题", "") or "")
            desc = str(r.get("摘要", "") or "")
            content = f"{title} {desc}".strip()
            if len(content) < 5:
                continue
            rows.append({
                "类型": "搜索",
                "标题": title,
                "正文": desc,
                "内容": content,
                "作者": str(r.get("作者", "") or ""),
                "时间": r.get("发布时间", ""),
                "点赞数": int(r.get("点赞数", 0) or 0),
                "评论数": int(r.get("评论数", 0) or 0),
                "浏览数": 0,
                "排序": "",
                "ID": str(r.get("帖子ID", "")),
            })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # 去重
    before = len(df)
    df = df.drop_duplicates(subset=["内容"], keep="first")
    after = len(df)

    # 时间解析
    df["时间"] = pd.to_datetime(df["时间"], errors="coerce")
    df = df.dropna(subset=["时间"])

    # 分类 + 情感分析
    classify_result = df["内容"].apply(classify_content)
    df["分类"] = classify_result.apply(lambda x: x[0])
    df["匹配度"] = classify_result.apply(lambda x: x[1])
    df["情感"] = df["内容"].apply(analyze_sentiment)

    df = df.sort_values("时间", ascending=False).reset_index(drop=True)
    return df


def apply_filters(df, start_date, end_date, keywords, category_filter, sort_filter, type_filter):
    """多维过滤"""
    if df.empty:
        return df

    # 时间
    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1)
    df = df[(df["时间"] >= start_dt) & (df["时间"] < end_dt)]

    # 关键词
    if keywords.strip():
        kw_list = [k.strip() for k in re.split(r"[,，\s]+", keywords) if k.strip()]
        if kw_list:
            mask = df["内容"].apply(lambda x: any(kw in str(x) for kw in kw_list))
            df = df[mask]

    # 分类
    if category_filter and category_filter != "全部分类":
        df = df[df["分类"] == category_filter]

    # 排序方式
    if sort_filter and sort_filter != "全部排序":
        df = df[df["排序"] == sort_filter]

    # 类型
    if type_filter and type_filter != "全部类型":
        df = df[df["类型"] == type_filter]

    return df.reset_index(drop=True)


# ─────────────────────────────────────────
# 报告生成
# ─────────────────────────────────────────
def generate_report(df, keywords, start_date, end_date):
    """生成 Markdown 舆情报告"""
    total = len(df)
    if total == 0:
        return "⚠️ 所选条件下没有数据。"

    posts = df[df["类型"] == "帖子"]
    comments = df[df["类型"] == "评论"]

    pos = (df["情感"] == "positive").sum()
    neg = (df["情感"] == "negative").sum()
    neu = (df["情感"] == "neutral").sum()
    pos_pct = pos / total * 100
    neg_pct = neg / total * 100

    category_counts = df["分类"].value_counts()

    lines = [
        f"# 🚂 崩坏星穹铁道 · 玩家舆情分析报告",
        f"",
        f"> **数据来源**：米游社板块52 (sr/home/52)  ",
        f"> **统计时间**：{start_date} ～ {end_date}  ",
        f"> **关键词筛选**：{keywords if keywords.strip() else '全量'}  ",
        f"> **生成时间（北京时间）**：{datetime.now(CST8).strftime('%Y-%m-%d %H:%M')}",
        f"",
        f"---",
        f"",
        f"## 一、数据概览",
        f"",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 总数据量 | **{total}** 条 |",
        f"| 帖子数 | {len(posts)} 条 |",
        f"| 评论数 | {len(comments)} 条 |",
        f"| 正面声音 | {pos} 条（{pos_pct:.1f}%）|",
        f"| 负面声音 | {neg} 条（{neg_pct:.1f}%）|",
        f"| 中性讨论 | {neu} 条（{neu/total*100:.1f}%）|",
        f"",
    ]

    # 风险等级
    if neg_pct >= 40:
        risk = "🔴 高风险 — 负面情绪突出，需重点关注"
    elif neg_pct >= 25:
        risk = "🟡 中等关注 — 存在一定负面声音"
    else:
        risk = "🟢 整体健康 — 玩家情绪稳定"

    lines += [f"**舆情风险：{risk}**", f"", f"---", f"", f"## 二、内容分类分布", f""]
    for cat, cnt in category_counts.items():
        bar = "█" * min(cnt, 30)
        pct = cnt / total * 100
        lines.append(f"- **{cat}**：{bar} {cnt} 条（{pct:.1f}%）")

    # 各分类情感
    lines += ["", "---", "", "## 三、各分类情感分析", ""]
    for cat in category_counts.index[:6]:
        sub = df[df["分类"] == cat]
        sub_pos = (sub["情感"] == "positive").sum()
        sub_neg = (sub["情感"] == "negative").sum()
        sub_total = len(sub)
        lines.append(f"### {cat}")
        lines.append(f"- 数据量：{sub_total} 条 | 正面：{sub_pos}（{sub_pos/sub_total*100:.0f}%）| 负面：{sub_neg}（{sub_neg/sub_total*100:.0f}%）")

    # 负面热点
    lines += ["", "---", "", "## 四、负面热点 TOP 10", ""]
    top_neg = df[df["情感"] == "negative"].nlargest(10, "点赞数")
    if top_neg.empty:
        lines.append("✅ 所选范围内暂无负面讨论。")
    else:
        for i, (_, row) in enumerate(top_neg.iterrows(), 1):
            tag = "帖子" if row["类型"] == "帖子" else "评论"
            title = row["标题"] if row["标题"] else ""
            snippet = str(row["内容"])[:100].replace("\n", " ")
            lines.append(f"{i}. **[{row['分类']}]** [{tag}] {title} {'| ' + snippet if not title else ''}… （👍{int(row['点赞数'])}）")

    # 正面亮点
    lines += ["", "---", "", "## 五、正面声音 TOP 5", ""]
    top_pos = df[df["情感"] == "positive"].nlargest(5, "点赞数")
    if top_pos.empty:
        lines.append("（暂无正面讨论）")
    else:
        for i, (_, row) in enumerate(top_pos.iterrows(), 1):
            snippet = str(row["内容"])[:100].replace("\n", " ")
            lines.append(f"{i}. **[{row['分类']}]** {snippet}… （👍{int(row['点赞数'])}）")

    # 建议
    lines += ["", "---", "", "## 六、运营建议", ""]
    suggestions = []
    if neg_pct >= 30:
        neg_top = df[df["情感"] == "negative"]["分类"].value_counts().index[0] if not df[df["情感"] == "negative"].empty else "未知"
        suggestions.append(f"1. **重点关注「{neg_top}」**：该分类负面声音最集中，建议专项回应。")

    tech_cat = "🐛 技术问题"
    if tech_cat in category_counts and category_counts[tech_cat] >= 3:
        suggestions.append("2. **技术问题需优先处理**：玩家反馈 BUG/卡顿/闪退较多，建议排查并发布公告。")

    biz_cat = "💰 商业化/抽卡"
    if biz_cat in category_counts:
        suggestions.append("3. **关注商业化讨论**：抽卡/定价相关讨论活跃，可考虑发布概率公示或福利活动。")

    if pos_pct >= 40:
        suggestions.append("4. **利用正面口碑**：玩家好评较多，可提炼用于二创素材或社区推广。")

    if not suggestions:
        suggestions.append("1. 整体舆情健康，保持现有运营节奏。")
        suggestions.append("2. 建议每周定期运行报告，追踪版本更新后的舆情变化。")

    lines += suggestions
    lines += ["", "---", "", "*本报告由崩铁舆情分析 Agent 自动生成*"]
    return "\n".join(lines)


# ─────────────────────────────────────────
# 一键采集按钮（仅本地模式）
# ─────────────────────────────────────────
def run_collector():
    """在后台运行采集脚本"""
    step1 = os.path.join(MIYOUSHE_DIR, "step1_get_post_list.py")
    if os.path.exists(step1):
        proc = subprocess.Popen(
            [sys.executable, step1],
            cwd=MIYOUSHE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return proc
    return None


def run_comment_collector():
    """运行评论采集"""
    step2 = os.path.join(MIYOUSHE_DIR, "step2_get_post_detail.py")
    if os.path.exists(step2):
        proc = subprocess.Popen(
            [sys.executable, step2],
            cwd=MIYOUSHE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return proc
    return None


# ─────────────────────────────────────────
# 纯规则问答
# ─────────────────────────────────────────
def rule_answer(question, df):
    total = len(df)
    pos = (df["情感"] == "positive").sum()
    neg = (df["情感"] == "negative").sum()
    cat_counts = df["分类"].value_counts()
    q = question.lower()

    if any(w in q for w in ["负面", "差评", "问题", "吐槽"]):
        top_neg = df[df["情感"] == "negative"].nlargest(5, "点赞数")
        if top_neg.empty:
            return "✅ 当前范围内没有明显负面声音！"
        lines = ["🔴 **负面热点 TOP 5：**\n"]
        for i, (_, r) in enumerate(top_neg.iterrows(), 1):
            snippet = str(r["内容"])[:80]
            lines.append(f"{i}. [{r['分类']}] {snippet}… (👍{int(r['点赞数'])})")
        neg_cat = df[df["情感"] == "negative"]["分类"].value_counts().index[0] if not df[df["情感"] == "negative"].empty else "无"
        lines.append(f"\n📌 负面最集中在**「{neg_cat}」**，占比 {neg/total*100:.0f}%。")
        return "\n".join(lines)

    elif any(w in q for w in ["话题", "讨论", "分类", "热点"]):
        lines = ["📈 **玩家当前最关注的话题：**\n"]
        for cat, cnt in cat_counts.items():
            pct = cnt / total * 100
            lines.append(f"- **{cat}**：{cnt} 条 ({pct:.0f}%)")
        return "\n".join(lines)

    elif any(w in q for w in ["简报", "总结", "概况"]):
        neg_cat = df[df["情感"] == "negative"]["分类"].value_counts().index[0] if not df[df["情感"] == "negative"].empty else "无"
        return f"""📊 **舆情简报**

- 当前共 **{total}** 条（帖子 {len(df[df['类型']=='帖子'])} + 评论 {len(df[df['类型']=='评论'])}）
- 情感分布：正面 {pos/total*100:.0f}% / 负面 {neg/total*100:.0f}% / 中性 {(total-pos-neg)/total*100:.0f}%
- 最热分类：**{cat_counts.index[0]}**（{cat_counts.iloc[0]} 条）
- 负面集中在：**{neg_cat}**
- {'🔴 需重点关注' if neg/total >= 0.3 else '🟢 整体健康'}"""

    elif any(w in q for w in ["运营", "建议", "怎么做"]):
        lines = ["💡 **运营建议：**\n"]
        neg_cat = df[df["情感"] == "negative"]["分类"].value_counts().index[0] if not df[df["情感"] == "negative"].empty else None
        if neg_cat:
            lines.append(f"1. 「{neg_cat}」负面声音最多，建议专项回应")
        if "🐛 技术问题" in cat_counts and cat_counts.get("🐛 技术问题", 0) >= 3:
            lines.append("2. BUG/卡顿反馈较多，建议优先修复")
        lines.append("3. 定期运行报告追踪舆情变化")
        return "\n".join(lines)

    else:
        return f"""📊 当前数据（共 {total} 条）：
- 正面：{pos}（{pos/total*100:.0f}%）/ 负面：{neg}（{neg/total*100:.0f}%）
- 最热分类：{cat_counts.index[0] if len(cat_counts) > 0 else '暂无'}"""


# ─────────────────────────────────────────
# 主页面
# ─────────────────────────────────────────
def main():
    # ── 侧边栏 ─────────────────────────────
    with st.sidebar:
        st.markdown("## 🚂 崩铁舆情分析 Agent")
        st.caption("数据来源：米游社板块52")
        st.markdown("---")

        # 时间范围（始终以北京时间为准）
        st.markdown("### 📅 时间范围")
        date_preset = st.selectbox("快速选择", ["最近7天", "最近30天", "最近3天", "全部数据", "自定义"], index=1)
        # 获取北京时间今天（不受服务器时区影响）
        today = datetime.now(CST8).date()
        if date_preset == "最近3天":
            default_start = today - timedelta(days=3)
        elif date_preset == "最近7天":
            default_start = today - timedelta(days=7)
        elif date_preset == "最近30天":
            default_start = today - timedelta(days=30)
        elif date_preset == "全部数据":
            default_start = date(2020, 1, 1)
        else:
            default_start = today - timedelta(days=7)

        if date_preset == "自定义":
            start_date = st.date_input("开始日期", value=default_start)
            end_date = st.date_input("结束日期", value=today)
        else:
            start_date = default_start
            end_date = today
            st.caption(f"📆 {start_date} ～ {end_date}")

        st.markdown("---")

        # 关键词
        st.markdown("### 🔍 关键词")
        keywords = st.text_input("输入关键词（逗号隔开）", placeholder="如：数值膨胀, 逼氪, 剧情")

        st.markdown("---")

        # 分类过滤
        all_categories = ["全部分类"] + list(CATEGORY_RULES.keys())
        category_filter = st.selectbox("分类筛选", all_categories)

        # 排序方式
        sort_filter = st.selectbox("排序方式", ["全部排序", "热门", "最新发布", "最新回复"])

        # 类型
        type_filter = st.selectbox("内容类型", ["全部类型", "帖子", "评论"])

        st.markdown("---")

        # 采集按钮（本地模式显示，云端模式隐藏）
        if not IS_CLOUD:
            st.markdown("### 📡 数据采集")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("📥 采集帖子", use_container_width=True):
                    st.cache_data.clear()
                    proc = run_collector()
                    if proc:
                        st.session_state["collector_pid"] = proc.pid
                        st.session_state["collector_start"] = time.time()
                        st.success("帖子采集中...")
                        st.rerun()

            with col_b:
                if st.button("💬 采集评论", use_container_width=True):
                    st.cache_data.clear()
                    proc = run_comment_collector()
                    if proc:
                        st.session_state["commentor_pid"] = proc.pid
                        st.session_state["commentor_start"] = time.time()
                        st.success("评论采集中...")
                        st.rerun()

            # 采集状态
            if "collector_pid" in st.session_state:
                elapsed = time.time() - st.session_state.get("collector_start", time.time())
                if elapsed > 120:
                    st.info("采集可能已完成，点击下方刷新")
                else:
                    st.spinner(f"帖子采集中... ({elapsed:.0f}s)")

            if "commentor_pid" in st.session_state:
                elapsed = time.time() - st.session_state.get("commentor_start", time.time())
                if elapsed > 300:
                    st.info("评论采集可能已完成，点击下方刷新")
                else:
                    st.spinner(f"评论采集中... ({elapsed:.0f}s)")
            st.markdown("---")

        if st.button("🔄 刷新数据", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.caption("🌐 数据自动从米游社实时获取")

    # ── 主区域（4个Tab） ─────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 概览与报告", "🏷️ 分类浏览", "📋 数据明细", "💬 对话问答"
    ])

    # 加载数据
    raw = load_all_data()
    # 读取并在 raw 中移除内部标记
    fetch_err = raw.pop("_fetch_error", False) if isinstance(raw, dict) else False
    if fetch_err:
        st.warning("⚠️ 实时数据获取超时，当前展示本地缓存数据（可能不含今日新帖）")
    analysis_df = build_analysis_df(raw)
    filtered_df = apply_filters(analysis_df, start_date, end_date, keywords, category_filter, sort_filter, type_filter)

    # ─────────── TAB 1：概览 ───────────────
    with tab1:
        st.markdown(f"### 📊 舆情概览  `{start_date} ～ {end_date}`")

        if filtered_df.empty:
            st.warning("⚠️ 所选时间范围内没有数据，请尝试扩大时间范围。")
        else:
            total = len(filtered_df)
            posts = len(filtered_df[filtered_df["类型"] == "帖子"])
            comments = len(filtered_df[filtered_df["类型"] == "评论"])
            pos = (filtered_df["情感"] == "positive").sum()
            neg = (filtered_df["情感"] == "negative").sum()

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("📝 总量", total)
            c2.metric("📰 帖子", posts)
            c3.metric("😊 正面", f"{pos} ({pos/total*100:.0f}%)")
            c4.metric("😤 负面", f"{neg} ({neg/total*100:.0f}%)")
            c5.metric("💬 评论", comments)

            st.markdown("---")

            col_l, col_r = st.columns(2)

            with col_l:
                st.markdown("#### 🥧 情感分布")
                try:
                    import plotly.graph_objects as go
                    fig = go.Figure(data=[go.Pie(
                        labels=["正面 😊", "负面 😤", "中性 😐"],
                        values=[pos, neg, total - pos - neg],
                        hole=0.4,
                        marker=dict(colors=["#2ecc71", "#e74c3c", "#95a5a6"]),
                    )])
                    fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
                    st.plotly_chart(fig, use_container_width=True)
                except ImportError:
                    st.info("pip install plotly")

            with col_r:
                st.markdown("#### 🏷️ 分类分布")
                cat_counts = filtered_df["分类"].value_counts().head(8)
                try:
                    import plotly.graph_objects as go
                    colors = [CATEGORY_RULES.get(c.strip().split(" ", 1)[-1] if " " in c else c, {}).get("color", "#3498db")
                              for c in cat_counts.index]
                    fig2 = go.Figure(go.Bar(
                        x=cat_counts.values.tolist(),
                        y=cat_counts.index.tolist(),
                        orientation="h",
                        marker_color=colors,
                    ))
                    fig2.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10),
                                       yaxis=dict(autorange="reversed"))
                    st.plotly_chart(fig2, use_container_width=True)
                except ImportError:
                    st.bar_chart(cat_counts)

            st.markdown("---")
            st.markdown("#### 📄 舆情分析报告")
            report = generate_report(filtered_df, keywords, start_date, end_date)
            st.markdown(report)
            st.download_button(
                "⬇️ 下载报告（Markdown）",
                data=report.encode("utf-8"),
                file_name=f"崩铁舆情报告_{start_date}_{end_date}.md",
                mime="text/markdown",
            )

    # ─────────── TAB 2：分类浏览 ───────────
    with tab2:
        st.markdown("### 🏷️ 内容分类浏览")
        if filtered_df.empty:
            st.info("暂无数据。")
        else:
            categories = ["全部分类"] + list(filtered_df["分类"].unique())
            selected_cat = st.radio("选择分类", categories, horizontal=True)

            display = filtered_df if selected_cat == "全部分类" else filtered_df[filtered_df["分类"] == selected_cat]
            st.caption(f"显示 {len(display)} / {len(filtered_df)} 条")

            for cat in (display["分类"].unique() if selected_cat == "全部分类" else [selected_cat]):
                cat_df = display[display["分类"] == cat]
                st.markdown(f"#### {cat} ({len(cat_df)} 条)")

                # 帖子
                cat_posts = cat_df[cat_df["类型"] == "帖子"].head(10)
                for _, r in cat_posts.iterrows():
                    sentiment_icon = {"positive": "😊", "negative": "😤", "neutral": "😐"}.get(r["情感"], "😐")
                    with st.expander(f"{sentiment_icon} [{r['标题'][:50]}]  👍{int(r['点赞数'])}  💬{int(r['评论数'])}"):
                        st.markdown(f"**正文**：{r['正文'][:500]}")
                        st.caption(f"👤 {r['作者']} | 🕐 {r['时间']} | 📊 {r['排序']}")

                # 评论
                cat_comments = cat_df[cat_df["类型"] == "评论"].head(10)
                if not cat_comments.empty:
                    st.markdown("**💬 热门评论：**")
                    for _, r in cat_comments.iterrows():
                        sentiment_icon = {"positive": "😊", "negative": "😤", "neutral": "😐"}.get(r["情感"], "😐")
                        st.markdown(f"{sentiment_icon} [{r['作者']}] {r['内容'][:100]}…  👍{int(r['点赞数'])}")

                st.markdown("---")

    # ─────────── TAB 3：数据明细 ───────────
    with tab3:
        st.markdown("### 📋 数据明细")
        if filtered_df.empty:
            st.info("暂无数据。")
        else:
            # 过滤
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                sentiment_f = st.selectbox("情感", ["全部", "正面 😊", "负面 😤", "中性 😐"])
            with f_col2:
                type_f = st.selectbox("类型", ["全部", "帖子", "评论"])

            label_map = {"全部": None, "正面 😊": "positive", "负面 😤": "negative", "中性 😐": "neutral"}
            display = filtered_df.copy()
            if label_map[sentiment_f]:
                display = display[display["情感"] == label_map[sentiment_f]]
            if type_f != "全部":
                display = display[display["类型"] == type_f]

            st.caption(f"显示 {len(display)} / {len(filtered_df)} 条")

            def color_row(val):
                if val == "positive":
                    return "background-color: #d4edda; color: #155724"
                elif val == "negative":
                    return "background-color: #f8d7da; color: #721c24"
                return ""

            show_cols = ["时间", "类型", "标题", "内容", "分类", "情感", "点赞数", "评论数", "作者"]
            available = [c for c in show_cols if c in display.columns]
            styled = display[available].style.map(color_row, subset=["情感"])
            st.dataframe(styled, use_container_width=True, height=600)

            csv = display[available].to_csv(index=False, encoding="utf-8-sig")
            st.download_button("⬇️ 下载 CSV", data=csv.encode("utf-8-sig"),
                               file_name=f"崩铁舆情_{start_date}_{end_date}.csv", mime="text/csv")

    # ─────────── TAB 4：对话问答 ───────────
    with tab4:
        st.markdown("### 💬 舆情对话问答")
        if filtered_df.empty:
            st.warning("暂无数据，请先选择有时间范围的数据。")
        else:
            if "messages" not in st.session_state:
                st.session_state.messages = []

            quick_qs = ["当前最突出的负面问题是什么？", "玩家在讨论哪些话题？",
                        "哪方面需要运营关注？", "给我一份简报"]
            q_cols = st.columns(4)
            for i, q in enumerate(quick_qs):
                if q_cols[i].button(q, key=f"q_{i}"):
                    st.session_state.messages.append({"role": "user", "content": q})

            st.markdown("---")
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if prompt := st.chat_input("输入你的舆情问题…"):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    with st.spinner("分析中…"):
                        answer = rule_answer(prompt, filtered_df)
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})

            if st.session_state.messages:
                if st.button("🗑️ 清空对话"):
                    st.session_state.messages = []
                    st.rerun()


if __name__ == "__main__":
    main()
