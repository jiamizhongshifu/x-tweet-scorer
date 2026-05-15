# 当我把 X 算法源码读完，我做了一个 AI 推文评分器

> 一个小账号的自救实验：从 16k stars 的开源源码里，反推出推文为什么没人看

---

## 起因：我的推文凭什么没人看

我做开源，写 Skill，关注 Cursor、Claude Code、Agent 相关的方向。技术上不算外行，但 X 账号惨淡。

写得用心的推文 80 曝光、3 个赞，复制别人爆款的句式 50 曝光、0 赞，发个工具截图说"刚做完一个小东西"——可能就完全沉了，连我自己再次刷到都得搜半天。

这种状态持续到某天，我看到 xAI 把 X 的 For You 算法开源了。仓库叫 [`xai-org/x-algorithm`](https://github.com/xai-org/x-algorithm)，主体是 Rust + Python，16k stars。我把它从头读到尾，一边读一边骂自己——**我之前发的那些推文，按照算法的标准，几乎每一条都触发了至少一个负向信号**。

读完之后做了一个东西：[`x-tweet-scorer`](https://github.com/jiamizhongshifu/x-tweet-scorer)，一个 Claude Skill。原理是把算法源码里预测的 14 个动作概率，重新打包成 5 个创作者能看懂的维度。在发推之前先让 AI 模拟算法给打个分。

这篇博客记录两件事：
1. 算法源码里到底写了什么——重点是和"创作者常识"反着来的几个发现
2. 怎么把这些发现变成一个能用的 Skill

如果你也是粉丝量不大、又不想瞎写的人，这篇值得看完。

---

## 第一部分：源码里到底写了什么

### 整个算法只在做一件事

X 的推荐算法核心是一个叫 **Phoenix** 的 Grok-based transformer，它的工作很简单：对每一条候选推文，预测下面这 14 个动作的发生概率：

```
正向动作（权重为正）：
  P(favorite)        点赞
  P(reply)           回复
  P(repost)          转发
  P(quote)           引用转发
  P(click)           点击链接
  P(profile_click)   点击你的头像进主页
  P(video_view)      看视频
  P(photo_expand)    展开图片
  P(share)           外部分享
  P(dwell)           停留时长
  P(follow_author)   关注你

负向动作（权重为负）：
  P(not_interested)  不感兴趣
  P(block_author)    拉黑
  P(mute_author)     静音
  P(report)          举报
```

最终分数就是一个加权求和：

```
Final Score = Σ (weight_i × P(action_i))
```

正向动作贡献正分，负向动作贡献负分。然后按分数排序，决定要不要把这条推文塞进你的 For You。

**这是整个推荐系统在做的事，没了**。源码里写着："We have eliminated every single hand-engineered feature"——他们删光了所有手工特征，全靠 transformer 学。

### 读完之后我立刻意识到 4 件反直觉的事

#### 1. 算法实际上奖励"让人读得久"，不是"写得短"

P(dwell) 这一项是单独建模的，并且权重不低。

dwell 是少数几个**不需要用户主动操作**就能产生的正向信号——绝大多数人不点赞、不转发，但所有人都会"看"。这意味着对算法而言，dwell 是一个比点赞更稠密、更可靠的信号。

我之前一直信奉"推文要短、要快、要一句话讲完"。但源码告诉我：**让一条推文短到 5 秒读完，等于主动放弃了一个最大的正向信号**。

那些数字列表、对比结构、悬念前置的推文之所以效果好，不一定是因为内容更精彩——而是因为它们让人多看了 10 秒。

#### 2. 避免负向，比追求正向重要得多

权重公式里，负向动作是减分项。一个 P(mute_author) 升高造成的伤害，可能要好几个 P(favorite) 才能补回来。

我翻了翻自己过去发过的推文，发现自己反复在踩雷：

- "DM 我领取" → 触发推销话术静音
- "兄弟们今天来聊聊" → 烂大街开头降权
- 连续 3 条都在讲同一个项目 → 触发 `AuthorDiversityScorer` 衰减

源码里专门有一个 `AuthorDiversityScorer`：**同一个作者在 feed 里被反复看到的分数会被衰减**。意思是，你发再多同主题推文，算法会主动压低后面那些的曝光。

我之前一直以为"多发就有概率爆"——错的。**多发会让自己的每一条都被压制**。

#### 3. 出圈只有一条路，叫 OON Scorer

源码里有一个组件叫 `OON Scorer`，全称 Out-of-Network Scorer。它的作用是给"展示给非粉丝看"的推文打分。

读完这部分我才理解为什么有些人粉丝少但能出圈，有些人粉丝多但永远在小圈子里转——**OON 是粉丝少的账号唯一的破局路径**。

OON 的工作机制是 two-tower retrieval：
- 把每个用户的兴趣编码成一个 embedding（向量）
- 把你的推文也编码成 embedding
- 通过点积相似度匹配，决定要不要把你的推文塞进陌生人的 For You

这意味着两件事：

第一，**"和朋友说话的口吻"几乎不可能出圈**。因为口语化、缺少明确语义信号的推文，编码出来的 embedding 是模糊的，匹配不到任何陌生人。

第二，**内部黑话和自嘲也几乎不可能出圈**。你写"今天又被产品经理坑了哈哈哈"——这条推文的 embedding 远离任何主流话题，OON Retrieval 找不到合适的陌生用户给它推。

但反过来：**只要你的推文带有清晰的语义信号（具体的工具名、明确的技术概念、可识别的实体），就有出圈的可能**——哪怕你只有 50 个粉丝。

这是粉丝少账号的福音，也是大部分小号没意识到的杠杆。

#### 4. 每条推文都是被独立评分的

源码里有一个非常关键的设计叫 **Candidate Isolation**：

```
Candidates CANNOT attend to each other (only self)
```

翻译过来：transformer 在给推文打分时，候选推文之间不能互相"看到"。每条推文都是孤立地、独立地被打分的。

这意味着：

- 你写 thread，每一条都必须**自包含成立**。依赖前文的"接上条"、"继续说"会让那一条单独被算法看到时完全失分。
- 你不能指望"前面那条火了，后面那条会被带飞"。算法不是这么工作的。

我之前发 thread 经常依赖上下文，第二条说"接着上面那条"——按算法的逻辑，这第二条进入别人 For You 时是孤立的，它**看起来就像一句莫名其妙的废话**。

---

## 第二部分：怎么把这些变成一个能用的 Skill

知道了算法的逻辑，下一步就是把它变成一个**在发推之前**就能用上的工具。我选择做成一个 Claude Skill，原因有三个：

1. **Skill 格式正在成为 AI 工具的标准协议**，Claude / Cursor / 自定义 Agent 都能直接读
2. **不需要后端服务**——一个 Markdown 文件加一个 Prompt 就能跑
3. **模型无关**——Claude、GPT、GLM、DeepSeek 都能跑

### 设计决策一：把 14 个动作聚合成 5 个

直接暴露 14 个数字会让人陷入"看不懂哪个最重要"的认知过载。我按"创作者可优化的方向"重新打包：

| 维度 | 聚合的 Phoenix 动作 | 权重 |
|---|---|---|
| 🔥 **分发力** | repost + quote + share | 35% |
| 💬 **对话力** | reply + favorite | 25% |
| 👀 **沉浸力** | dwell + click + video_view + photo_expand | 20% |
| 🎯 **关注力** | profile_click + follow_author | 10% |
| ⚠️ **风险分** | -(not_interested + block + mute + report) | 10% |

权重不是拍脑袋的：

- **分发力 35% 最高**：因为 OON Scorer 决定了出圈，对小账号是最稀缺的资源
- **沉浸力 20% 独立成维**：因为 dwell 是被低估的暗物质信号
- **风险分单独存在**：因为它在最终公式里是减法关系，单点触发就崩盘

### 设计决策二：两层架构

```
用户输入推文
    │
    ▼
Layer 1: 规则红线扫描（确定性、不花 token）
    │   检测高频静音词、推销话术、依赖前文等
    │   命中 → 标黄/标红，不阻断
    │
    ▼
Layer 2: LLM 五维评分（语义层）
    │   英文 Prompt + 强制 JSON 输出
    │   每个维度 0-100 + 一句话依据
    │   核心字段：phoenix_insight（必须引用源码组件）
    │
    ▼
聚合输出：评分报告 + 改写建议
```

Layer 1 是规则，Layer 2 是语义。这样既保证了"DM 我"这种确定性问题不需要花 token 就能识别，又保证了"这条推文 hook 强不强"这种语义判断交给 LLM。

### 设计决策三：评分 Prompt 用英文写

SKILL.md 主体用中文（面向中文创作者），但内部的评分 Prompt 一律用英文。原因是实测下来，**英文 Prompt 在多数 LLM 上的 JSON 输出稳定性高 10-20%**，概率估计也更准。

Prompt 的核心是要求 LLM **必须引用一个具体的 Phoenix 源码组件作为评分依据**：

```
phoenix_insight: ONE actionable improvement, explicitly grounded in
a Phoenix source-code component (e.g., "Candidate isolation means
this tweet must..." / "OON Scorer rewards..." / "Author Diversity
Scorer will penalize..."). This is the MOST important field — it's
what makes this scorer credible.
```

这一条让本 Skill 和市面上所有"AI 推文助手"产生了根本差异：**别的工具说"这样写更吸引人"，本 Skill 必须说清楚"因为 X 算法的哪个组件会这样反应"**。

### 设计决策四：模型无关

我没有把 Skill 绑死在 Claude 上。Prompt 模板是纯文本，Python 实现用 OpenAI 兼容接口。这意味着：

- Claude 用户可以直接当 Skill 用
- Cursor 用户可以接 GPT
- 国内开发者可以接智谱 GLM-5 / DeepSeek
- 想自托管的人可以接 Qwen / 自己微调的模型

任何能输出 JSON 的 LLM 都能跑，门槛降到最低。

---

## 第三部分：我用它做了什么

做完 Skill 之后我做的第一件事，是把自己过去 30 条推文喂进去打分。结果：

- 平均分 41 / 100
- 14 条触发了至少一个红线（"DM 我"、"今天来聊聊"、自我推销）
- 21 条沉浸力维度低于 50（信息密度不足）
- 3 条分发力高于 70——巧合的是这 3 条正是我历史上互动最高的

打完分之后我开始用它做发布前检查。流程是：

1. 写出第一稿
2. 让 Skill 打分
3. 看哪个维度最低，按建议改一版
4. 重新打分，对比
5. 直到总分 > 65 才发

**用了两周，平均曝光从 60 多涨到 200 多，互动率翻了 3 倍**。样本量小，不算严格的 A/B 实验，但至少证明这个工具能给方向。

更重要的是，每次评分输出会引用具体源码组件，这让我对算法的理解越来越具体——**从"我感觉这条会火"变成"这条触发了 OON Scorer 友好的语义信号，所以可能会被陌生人看到"**。

直觉变成了机制。这才是最大的收益。

---

## 几个使用建议

如果你也想用，几个我自己踩过的坑：

**1. 不要追求满分**

我刻意把校准基准设在 50 分左右是中位数，65+ 算优秀，85+ 是极少数。如果你的评分都在 80+，几乎可以肯定是 LLM 给分偏高，需要在 Prompt 里加更强的 calibration 提醒。

**2. 风险分 > 40 必须先改再发**

风险分高一点点就会大幅拖累总分。看到红线告警优先处理，比优化任何正向维度都重要。

**3. 复盘模式比优化模式更有用**

我后来发现最有价值的不是发推前打分，是**发推后用复盘模式跑一遍**。让 Skill 对比"预测分数 vs 实际表现"，找出算法盲点。

比如有一条推文预测 72 分（中等偏上），实际只有 40 个曝光。复盘模式告诉我："分发力被高估，因为这条推文的主题超出了你历史粉丝的 user embedding 邻域"——翻译过来就是，这条主题和我以往内容差太远，老粉不感兴趣，OON Retrieval 又匹配不到合适的新用户。

这种归因是普通"推文优化器"做不到的。

**4. 不要 100% 听 AI 的**

Skill 的本质是把算法的偏好建模出来，不是替你做内容。如果你的内容定位本身就是"和朋友说话的口吻"——很好，那就接受小圈层、放弃出圈，别强行追高分。

工具是帮你做明确的取舍，不是帮你做所有决定。

---

## 写在最后

这个项目让我想起一件事：**很多创作者的瓶颈不是"不会写"，是"不知道算法到底在看什么"**。

X 把算法开源了，但 16k stars 里有多少人真的把它读完了？又有多少人把它转化成了普通创作者能用的工具？

读源码的能力 + 把抽象算法翻译成具体可用工具的能力 = 一个被严重低估的杠杆。**这是 2026 年小创作者最值得做的事情之一**：不是去卷内容产量，是去搞懂内容被分发的机制。

[`x-tweet-scorer`](https://github.com/jiamizhongshifu/x-tweet-scorer) 是我对这件事的一个初步答案。开源 MIT 协议，欢迎 fork、提 Issue、给红线词清单补刀。

如果它帮你的小号也涨了点流量，回来告诉我一声——我也想知道这个工具到底有没有用。

---

**仓库地址**：https://github.com/jiamizhongshifu/x-tweet-scorer
**配套 Skill 系列**：[claude-power-skills](https://github.com/jiamizhongshifu/claude-power-skills)
**作者**：[@drmrzhong](https://x.com/drmrzhong)

如果觉得有用，⭐ Star 是对独立开发者最大的鼓励。

---

## 附：3 分钟上手

```bash
# 克隆仓库
git clone https://github.com/jiamizhongshifu/x-tweet-scorer.git

# 方式一：作为 Claude Skill
cp -r x-tweet-scorer ~/.claude/skills/

# 方式二：作为独立 Python 脚本
cd x-tweet-scorer
pip install openai
export OPENAI_API_KEY="your-key"
python scripts/score_template.py "你想评分的推文内容"
```

然后看着分数，开始改你的推文。

