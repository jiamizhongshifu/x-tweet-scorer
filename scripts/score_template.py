"""
x-tweet-scorer · Reference Implementation
==========================================

参考实现：用任意 OpenAI 兼容接口调用 LLM 评分推文。
本脚本仅作示范，使用者可替换为 Claude API、GLM-5、其他兼容模型。

用法：
    python score_template.py "你的推文文本"

或在代码中：
    from score_template import score_tweet
    result = score_tweet("推文内容", context="作者是 AI 工具开发者")

依赖：仅需 OpenAI 兼容客户端，标准库 + openai。
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# ------------------------------------------------------------------
# Layer 1: 规则红线扫描
# ------------------------------------------------------------------

MUTED_KEYWORDS_CN = [
    "DM 我", "私信我", "加我微信", "扫码加群", "进群",
    "限时优惠", "立即购买", "点击链接", "戳链接", "链接在简介",
    "兄弟们", "家人们", "宝子们", "今天来聊聊",
    "震惊", "重磅", "突发",
]

MUTED_KEYWORDS_EN = [
    "DM me", "link in bio", "check my profile",
    "limited time", "buy now",
    "let's dive in", "game-changer", "paradigm shift",
    "in today's fast-paced world",
]

AGE_KEYWORDS = [
    "今天", "刚刚", "刚才", "5 分钟前", "今早",
    "today", "just now", "moments ago", "this morning",
    "live now", "happening now",
]

SELF_PROMO_PATTERNS = [
    "我的新课程", "我的产品", "我的服务",
    "my new course", "my product", "I built",
    "X 万粉丝", "X 万收入",
]

ISOLATION_BREAKERS = [
    "接上条", "刚才说的", "如上", "续",
    "as I said", "continuing from", "follow-up to",
]


def scan_red_lines(tweet: str) -> Dict[str, List[str]]:
    """扫描推文的规则红线，返回 {level: [hit_keyword, ...]}"""
    result = {"warning": [], "severe": [], "info": []}
    text = tweet.lower()

    muted_hits = [kw for kw in MUTED_KEYWORDS_CN + MUTED_KEYWORDS_EN
                  if kw.lower() in text]
    if len(muted_hits) >= 3:
        result["severe"].extend(muted_hits)
    elif muted_hits:
        result["warning"].extend(muted_hits)

    age_hits = [kw for kw in AGE_KEYWORDS if kw.lower() in text]
    if age_hits:
        result["info"].extend([f"时效性词: {kw}" for kw in age_hits])

    promo_hits = [p for p in SELF_PROMO_PATTERNS if p.lower() in text]
    if promo_hits:
        result["warning"].extend([f"自我推销: {p}" for p in promo_hits])

    iso_hits = [p for p in ISOLATION_BREAKERS if p.lower() in text]
    if iso_hits:
        result["warning"].extend(
            [f"依赖前文（candidate isolation 不友好）: {p}" for p in iso_hits]
        )

    # 信息密度过低检查
    if len(tweet.strip()) < 20 and len(tweet.split()) < 5:
        result["info"].append("推文过短，沉浸力维度会被压低")

    return result


# ------------------------------------------------------------------
# Layer 2: LLM 评分
# ------------------------------------------------------------------

def load_prompt_template() -> str:
    """从 references/scoring-prompt.md 提取主 Prompt 模板"""
    prompt_path = (
        Path(__file__).parent.parent / "references" / "scoring-prompt.md"
    )
    content = prompt_path.read_text(encoding="utf-8")
    # 提取第一个三反引号代码块
    match = re.search(r"```\n(.*?)```", content, re.DOTALL)
    if not match:
        raise RuntimeError("未能从 scoring-prompt.md 中找到 Prompt 代码块")
    return match.group(1)


def score_with_llm(
    tweet: str,
    context: str = "",
    model: str = "gpt-4o-mini",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    调用 LLM 完成五维评分。

    Args:
        tweet: 推文文本
        context: 可选上下文（作者领域、目标受众等）
        model: 模型 ID（取决于 base_url 兼容性）
        api_key: API key（默认从环境变量 OPENAI_API_KEY 读取）
        base_url: 自定义 endpoint（如智谱、DeepSeek 等 OpenAI 兼容接口）

    Returns:
        包含 5 个维度分数 + final_score + phoenix_insight + rewrites 的 dict
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("请先安装：pip install openai")

    client = OpenAI(
        api_key=api_key or os.environ.get("OPENAI_API_KEY"),
        base_url=base_url,
    )

    prompt = load_prompt_template().replace(
        "{{TWEET}}", tweet
    ).replace(
        "{{CONTEXT}}", context or ""
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw = response.choices[0].message.content
    return json.loads(raw)


# ------------------------------------------------------------------
# 主入口：聚合 Layer 1 + Layer 2
# ------------------------------------------------------------------

def score_tweet(
    tweet: str,
    context: str = "",
    **llm_kwargs,
) -> Dict[str, Any]:
    """完整评分流程：规则红线 + LLM 评分"""
    red_lines = scan_red_lines(tweet)
    scores = score_with_llm(tweet, context, **llm_kwargs)

    return {
        "tweet": tweet,
        "red_lines": red_lines,
        "scores": scores,
    }


def render_report(result: Dict[str, Any]) -> str:
    """将评分结果渲染为模式 A 的可读报告"""
    tweet = result["tweet"]
    rl = result["red_lines"]
    s = result["scores"]

    def bar(score: int, width: int = 10) -> str:
        filled = int(round(score / 100 * width))
        return "█" * filled + "░" * (width - filled)

    final = s.get("final_score", 0)
    if final >= 85:
        verdict = "顶尖"
    elif final >= 70:
        verdict = "优秀"
    elif final >= 50:
        verdict = "中等"
    elif final >= 30:
        verdict = "偏弱"
    else:
        verdict = "不建议发"

    lines = [
        "📊 推文算法评分报告",
        "═" * 40,
        "",
        f"[原文]\n> {tweet}",
        "",
        f"【最终得分】{final:.1f} / 100  ({verdict})",
        "",
        "【五维评分】",
        f"🔥 分发力  {s['amplification']['score']:>3} {bar(s['amplification']['score'])}  {s['amplification']['reason']}",
        f"💬 对话力  {s['conversation']['score']:>3} {bar(s['conversation']['score'])}  {s['conversation']['reason']}",
        f"👀 沉浸力  {s['attention']['score']:>3} {bar(s['attention']['score'])}  {s['attention']['reason']}",
        f"🎯 关注力  {s['authority']['score']:>3} {bar(s['authority']['score'])}  {s['authority']['reason']}",
        f"⚠️ 风险分  {s['risk']['score']:>3} {bar(s['risk']['score'])}  {s['risk']['reason']}",
        "",
    ]

    if rl["severe"] or rl["warning"] or rl["info"]:
        lines.append("【红线扫描】")
        for item in rl["severe"]:
            lines.append(f"🔴 {item}")
        for item in rl["warning"]:
            lines.append(f"🟡 {item}")
        for item in rl["info"]:
            lines.append(f"ℹ️ {item}")
        lines.append("")

    lines.append("【Phoenix 洞察】")
    lines.append(s.get("phoenix_insight", ""))
    lines.append("")

    rewrites = s.get("rewrites", [])
    if rewrites:
        lines.append("【三个改写方向】")
        for r in rewrites:
            lines.append(f"[{r['angle']}] {r['text']}")

    return "\n".join(lines)


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python score_template.py \"推文内容\" [上下文]")
        sys.exit(1)

    tweet_input = sys.argv[1]
    ctx = sys.argv[2] if len(sys.argv) > 2 else ""

    result = score_tweet(tweet_input, context=ctx)
    print(render_report(result))
