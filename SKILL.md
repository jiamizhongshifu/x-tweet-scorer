---
name: x-tweet-scorer
description: 基于 X (Twitter) 官方开源算法 (xai-org/x-algorithm) 的 Phoenix 评分模型反向工程出的推文评分系统。当用户需要评估、优化、对比、复盘推文（X/Twitter post）质量时使用，包括但不限于：发布前打分预测互动潜力、对比多个候选草稿、分析已发推文的算法表现、识别会触发算法负向惩罚的内容风险。无论用户是否明确提到 "Phoenix"、"X 算法"、"For You" 等关键词，只要涉及推文/X post/Twitter 内容质量评估、互动率预测、爆款分析、涨粉优化、出圈判断，都应使用此 skill。也适用于内容创作者、增长团队、社交媒体运营在发布前进行 A/B 决策。Use this whenever a user wants to score, optimize, compare, or audit tweets / X posts for algorithmic engagement potential.
---

# X Tweet Scorer · 推文算法评分器

> 基于 [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm) Phoenix 评分模型的反向工程实现。

## 这个 Skill 是什么

X 的 For You 推荐算法核心是一个叫 **Phoenix** 的 Grok-based transformer，它对每条推文预测 **14 种用户动作的发生概率**，然后用加权求和算出最终分数：

```
Final Score = Σ (weight_i × P(action_i))
```

正向动作（like、repost、reply、share、dwell 等）权重为正，负向动作（block、mute、report、not_interested）权重为负。

本 Skill 把这 14 个原生动作概率**聚合为 5 个创作者可读、可优化的维度**，并提供三种工作模式：发布前优化、批量对比、已发推文复盘。

## 何时使用本 Skill

触发关键词包括：
- **直接信号**：评分推文、推文打分、tweet 评分、score this tweet、推文质量、tweet quality
- **间接信号**：预测互动率、爆款潜力、为什么没人看、涨粉优化、出圈分析、A/B 选哪条、推文复盘
- **场景信号**：用户给出一段文本说"准备发推"、"哪个版本好"、"为什么这条数据差"

## 三种工作模式

模式由用户输入自动判定：

| 用户输入特征 | 触发模式 |
|---|---|
| 单条推文文本 + 想"优化/打分/预测" | **模式 A：单条优化** |
| 2 条及以上推文文本（"哪个更好"、"对比"） | **模式 B：批量对比** |
| 推文文本 + 实际数据（点赞/转发/曝光数） | **模式 C：复盘分析** |

如果无法判定，向用户确认一次。

---

## 评分核心：五维模型

### 维度定义（聚合自 Phoenix 14 动作）

| 维度 | 中文名 | 聚合的原生动作 | 权重 | 创作者含义 |
|---|---|---|---|---|
| **A** | 🔥 分发力 (Amplification) | P(repost) + P(quote) + P(share) | 0.35 | 决定能否被转发出圈 |
| **C** | 💬 对话力 (Conversation) | P(reply) + P(favorite) | 0.25 | 决定参与度和评论区活跃度 |
| **T** | 👀 沉浸力 (Attention) | P(dwell) + P(click) + P(video_view) + P(photo_expand) | 0.20 | 算法暗中重视的"被读完"信号 |
| **F** | 🎯 关注力 (Authority) | P(profile_click) + P(follow_author) | 0.10 | 决定能否从单推转化为新粉丝 |
| **R** | ⚠️ 风险分 (Risk) | -[P(not_interested) + P(block) + P(mute) + P(report)] | 0.10 | 一旦触发就直接腰斩，需单独审视 |

**Final Score（0-100）** = 0.35×A + 0.25×C + 0.20×T + 0.10×F + 0.10×(100-R)

### 为什么是这个权重

- **分发力 35% 最高**：源码里 OON Scorer（Out-of-Network Scorer）专门处理陌生人看到你内容时的打分，分发是粉丝少的创作者唯一的出圈通道。
- **沉浸力 20% 被低估**：源码 P(dwell) 是少数不需要用户主动操作的正向信号，意味着算法非常喜欢它（因为大部分人不点赞但所有人都"看"）。这是反直觉的——很多人以为"写短"是王道，但算法实际上奖励"让人读得久"。
- **风险分用 (100-R) 而非 R**：因为它是减分项，转成正向后参与加权能让总分尺度统一。

---

## 执行流程

每个模式的执行都走两层：**Layer 1 规则红线** → **Layer 2 LLM 评分**。

### Layer 1：规则红线扫描（先于 LLM 调用）

源码里 Pre-Scoring Filter 直接对应红线检查，先用规则过一遍，省 token 也给出确定性反馈。具体规则清单见 `references/filter-rules.md`，主要扫描：

- **MutedKeywordFilter 类**：高频静音词、推广话术、烂大街开头
- **AgeFilter 类**：时效性陷阱词
- **AuthorDiversity 类**：过度自我推销、重复主题
- **VFFilter 类**：可见性红线（暴力/灰产/违规）

红线触发的处理：**不直接拒绝**，而是在评分结果里标注 🟡 警告 / 🔴 严重，决定权留给用户。

### Layer 2：LLM 五维评分

读取 `references/scoring-prompt.md` 中的评分 Prompt 模板（**英文写就，以提升评分准确度**），将用户输入填入后请求 LLM 输出严格的 JSON 结构：

```json
{
  "amplification": {"score": 72, "reason": "..."},
  "conversation": {"score": 58, "reason": "..."},
  "attention": {"score": 81, "reason": "..."},
  "authority": {"score": 45, "reason": "..."},
  "risk": {"score": 12, "reason": "..."},
  "final_score": 64.3,
  "phoenix_insight": "..."
}
```

`phoenix_insight` 字段是必填的核心改进建议，需引用 Phoenix 源码原理（如 candidate isolation、OON scoring、dwell prediction 等），让用户理解"为什么"。

---

## 模式 A：单条优化

**输入**：一条推文草稿。

**输出结构**：

```
📊 推文算法评分报告
════════════════════════════

[原文]
> {tweet}

【最终得分】64.3 / 100  (中等偏上)

【五维评分】
🔥 分发力  72 ████████░░  能转发，但 hook 还可以更强
💬 对话力  58 ██████░░░░  缺少引发回复的开放性钩子
👀 沉浸力  81 █████████░  信息密度好，dwell 友好
🎯 关注力  45 █████░░░░░  作者身份感弱，难导流到主页
⚠️ 风险分  12 █░░░░░░░░░  低风险

【红线扫描】
🟡 检测到 "DM 我" → 提高 P(mute_author) 风险（来自 Author Diversity Scorer）

【Phoenix 洞察】
源码显示 candidate isolation 机制让每条推文独立打分，
这条推文依赖了 "上面那条" 的语境，建议补全自包含信息。

【三个改写方向】
1. [偏分发] {改写版本 1}
2. [偏对话] {改写版本 2}
3. [偏沉浸] {改写版本 3}
```

## 模式 B：批量对比

**输入**：2-10 条候选推文。

**输出**：评分对比表 + 推荐发布顺位 + 互补性分析（避免发完一条后下一条被 RepostDeduplicationFilter 压制）。

```
📊 候选推文对比 (N=3)
════════════════════════════
              A    C    T    F    R    总分   推荐
版本 1       72   58   81   45   12   64.3   ⭐ 首发
版本 2       65   78   55   62   18   62.1   #2 发
版本 3       80   42   70   38   45   54.0   ⚠️ 不建议

【建议发布顺序】v1 → 间隔 6h+ → v2
（v3 风险分 45 过高，建议改写后再发）

【互补性提醒】
v1 和 v2 主题相近，间隔过短会触发 RepostDeduplicationFilter
```

## 模式 C：复盘分析

**输入**：已发推文 + 实际数据（曝光量、点赞、转发、回复、profile clicks 等任意子集）。

**输出**：实际数据 vs 算法预测对比，找出**"算法盲点"**——即模型预测应该高但实际数据低的推文，定位真正的卡点。

```
📊 复盘分析
════════════════════════════

【预测 vs 实际】
预测总分：64.3 → 实际百分位：32%（低于预测）

【偏差归因】
✓ 沉浸力 81 → 实际 dwell 表现尚可（曝光/点赞比正常）
✗ 分发力 72 → 实际转发率显著偏低（推测：题材不属于"易传播"领域）
✗ 关注力 45 → 实际 profile click 率印证了预测，需要强化作者识别度

【下次发布建议】
1. ...
2. ...
```

---

## 模型无关性 (Model-Agnostic Design)

本 Skill **不指定具体 LLM**。`references/scoring-prompt.md` 中的 Prompt 是模型无关的纯文本，调用方可用：

- Claude (Sonnet 4.6 / Opus 4.7 等)
- OpenAI GPT 系列
- 智谱 GLM-5
- DeepSeek、Qwen、其他兼容模型

调用方负责执行 LLM 请求并将 JSON 结果解析后渲染。本 Skill 只规范评分协议，不绑定执行链路。

## 引用与可信度

每次输出都应在 `phoenix_insight` 中引用 Phoenix 源码的具体组件（OON Scorer / Author Diversity Scorer / Candidate Isolation / Filter 名称等），让用户能回到源码验证。这是本 Skill 区别于"普通推文优化器"的核心可信度锚点。

## 文件导览

- `SKILL.md`（本文件）：协议定义和工作流
- `references/scoring-prompt.md`：英文评分 Prompt 模板（核心资产）
- `references/filter-rules.md`：红线规则清单
- `references/phoenix-mapping.md`：14 动作 → 5 维度的完整映射说明和源码引用
- `scripts/score_template.py`：参考实现脚本（Python，OpenAI 兼容接口）
