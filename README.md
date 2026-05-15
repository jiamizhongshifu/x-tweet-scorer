# x-tweet-scorer

> 基于 X (Twitter) 官方开源算法 [`xai-org/x-algorithm`](https://github.com/xai-org/x-algorithm) 的 Phoenix 评分模型反向工程出的推文评分 Skill。
>
> 在发推之前，先让 AI 模拟算法给它打个分。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Skill Format](https://img.shields.io/badge/Skill-Anthropic%20Compatible-blue)](https://docs.claude.com)
[![Model Agnostic](https://img.shields.io/badge/Model-Agnostic-green)](#)

---

## 这是什么

X 的 For You 算法核心是一个叫 **Phoenix** 的 Grok-based transformer，它对每条推文预测 14 种用户动作的概率，然后加权求和算出最终分数。

本 Skill 把这 14 个动作聚合为 5 个创作者可读的维度，让任何 LLM（Claude / GPT / GLM / DeepSeek）都能模拟算法给推文打分。

```
Final Score = 0.35 × 分发力 + 0.25 × 对话力 + 0.20 × 沉浸力 + 0.10 × 关注力 + 0.10 × (100 - 风险分)
```

## 5 秒看懂能做什么

```
你：评一下这条推文 → "今天分享一个 AI 工具，DM 我领取..."

AI：
📊 推文算法评分报告
═════════════════════════
【最终得分】34.2 / 100  (偏弱)

🔥 分发力  28 ███░░░░░░░  推销话术压低了被转发欲望
💬 对话力  41 ████░░░░░░  缺少引发回复的钩子
👀 沉浸力  35 ███░░░░░░░  信息密度过低，dwell 不友好
🎯 关注力  22 ██░░░░░░░░  没展现作者身份感
⚠️ 风险分  68 ██████░░░░  多个推销词触发 mute 风险

🟡 检测到 "DM 我" → 触发 Author Diversity Scorer 静音风险

【Phoenix 洞察】
源码显示 OON Scorer 对陌生人展示的推文有独立打分逻辑，
而推销话术会显著提高 P(mute_author)，几乎无法出圈。

【改写建议】
[偏分发] {更具体的工具名 + 它解决了什么独特问题}
...
```

## 三种使用模式

| 模式 | 触发场景 | 用法 |
|---|---|---|
| **A. 单条优化** | 发推前给草稿打分 | "评一下这条推文：{文本}" |
| **B. 批量对比** | 多个版本选一个发 | "对比这几个版本：{文本1} / {文本2} / {文本3}" |
| **C. 复盘分析** | 已发推文 + 数据找原因 | "这条推文 {文本} 实际曝光 1.2 万、点赞 30、转发 2，帮我分析" |

## 安装使用

### 方式一：作为 Claude/Cursor Skill 使用

把整个 `x-tweet-scorer/` 目录放到你的 Skill 路径下：

```bash
# Claude Code (macOS / Linux)
cp -r x-tweet-scorer ~/.claude/skills/

# 或克隆整个仓库
git clone https://github.com/jiamizhongshifu/x-tweet-scorer.git ~/.claude/skills/x-tweet-scorer
```

然后在对话里直接说"评一下这条推文"，Skill 会自动触发。

### 方式二：作为独立 Python 脚本使用

```bash
pip install openai
export OPENAI_API_KEY="your-key"

python scripts/score_template.py "你的推文内容"
```

### 方式三：接入任意 LLM

本 Skill 模型无关。将 `references/scoring-prompt.md` 中的 Prompt 模板填入 `{{TWEET}}` 后，发给任何兼容 JSON 输出的 LLM 即可。

```python
# 接入智谱 GLM-5 示例
from score_template import score_tweet

result = score_tweet(
    "推文内容",
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    model="glm-5",
    api_key="your-glm-key",
)
```

## 文件结构

```
x-tweet-scorer/
├── SKILL.md                          # 主入口：协议定义和工作流
├── references/
│   ├── scoring-prompt.md             # ⭐ 核心英文评分 Prompt
│   ├── filter-rules.md               # 规则红线清单（中英双语）
│   └── phoenix-mapping.md            # 14 动作 → 5 维度映射 + 源码引用
└── scripts/
    └── score_template.py             # Python 参考实现
```

## 5 个维度怎么来的

| 维度 | 聚合 Phoenix 原生动作 | 权重 |
|---|---|---|
| 🔥 **分发力** Amplification | repost + quote + share | 35% |
| 💬 **对话力** Conversation | reply + favorite | 25% |
| 👀 **沉浸力** Attention | dwell + click + video_view + photo_expand | 20% |
| 🎯 **关注力** Authority | profile_click + follow_author | 10% |
| ⚠️ **风险分** Risk | -(not_interested + block + mute + report) | 10% |

完整的权重设计依据见 [`references/phoenix-mapping.md`](references/phoenix-mapping.md)。

## 为什么和"普通推文优化器"不一样

| 维度 | 普通优化器 | 本 Skill |
|---|---|---|
| **依据** | 个人经验、爆款总结 | xai-org 官方开源源码 |
| **目标** | 模糊的"互动率" | Phoenix 14 个具体动作概率 |
| **解释** | "更吸引人" | 引用具体源码组件（OON Scorer / Candidate Isolation 等）|
| **盲区** | 不知道算法不喜欢什么 | 显式建模 4 种负向动作 |

每次评分输出都会引用一个具体的 Phoenix 组件作为依据——这是核心可信度锚点，也是和市面所有"AI 推文助手"的关键差异。

## 模型兼容性

| 模型 | 测试状态 | 备注 |
|---|---|---|
| Claude Sonnet 4.6 / Opus 4.7 | ✅ | JSON 输出最稳定 |
| GPT-4o / GPT-4o-mini | ✅ | 评分准确度高 |
| 智谱 GLM-5 | ✅ | 通过 OpenAI 兼容接口 |
| DeepSeek-V3 | ✅ | 性价比最高 |
| Qwen-Max | ⚠️ | JSON 偶有逃逸，需重试 |

## 几个反直觉的发现

源码读下来，有几个和"创作者常识"反着来的设计，本 Skill 都显式建模了：

1. **算法实际上奖励"让人读得久"**。P(dwell) 是 14 个动作里少数不需要用户主动操作的正向信号——这意味着大部分用户不点赞，但所有人都"看"。复杂结构、信息密度高的推文反而比"短平快"得分更高。

2. **避免负向比追求正向更重要**。负向动作（block/mute/report）在加权公式里是减法，单次触发 P(mute_author) 升高的伤害 ≈ 失去多个正向反应。

3. **出圈只有一条路：OON Scorer**。粉丝少的账号要进入陌生人的 For You，必须靠 Phoenix Retrieval 的 two-tower 相似度匹配。这意味着"内部黑话"、"和朋友说话的口吻"几乎不可能出圈——但同时它也是粉丝少账号唯一的破局路径。

4. **Candidate Isolation 让每条推文独立打分**。算法对每条推文是隔离评分的（candidates 不能 attend to each other），意味着 thread 里的每一条都必须自包含成立。

## 参与贡献

发现规则误判？想加入新的静音词清单？欢迎提 Issue 或 PR：

- 红线词清单：编辑 [`references/filter-rules.md`](references/filter-rules.md)
- 评分 Prompt 优化：编辑 [`references/scoring-prompt.md`](references/scoring-prompt.md)
- 模型兼容测试：在 Issue 里贴出你的测试结果

## License

MIT

## 致谢

- [`xai-org/x-algorithm`](https://github.com/xai-org/x-algorithm) — 让本 Skill 可能的开源贡献
- 灵感来源于 [`claude-power-skills`](https://github.com/jiamizhongshifu/claude-power-skills) 系列

## 相关项目

- 📖 配套博客：[《当我把 X 算法源码读完，我做了一个 AI 推文评分器 —— 一个小账号的自救实验》](BLOG.md)
- 🔗 同系列 Skills：[claude-power-skills](https://github.com/jiamizhongshifu/claude-power-skills)

---

**如果觉得有用，欢迎 ⭐ Star，也欢迎用本 Skill 评分这条 README 顺便测试一下** 🙂
