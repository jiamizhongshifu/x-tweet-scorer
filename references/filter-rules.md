# Filter Rules · 规则红线扫描清单

> 对应 Phoenix 源码中的 10 个 Pre-Scoring Filter 和 2 个 Post-Selection Filter。
> 这些规则在调用 LLM 评分**之前**执行，先用确定性规则过一遍，节省 token 也给出可解释的反馈。

## 扫描方式

对用户输入的推文文本，按以下分类扫描关键词/模式。每条规则触发后，**不直接拒绝**，而是在最终输出中标注：

- 🟢 通过：无触发
- 🟡 警告：触发了软规则（如自我推销词），需提醒用户但仍可评分
- 🔴 严重：触发了硬规则（如可见性红线），需建议改写后再评分

---

## 1. MutedKeywordFilter 类（高频静音词）

**源码依据**：`MutedKeywordFilter` 会移除包含用户静音词的推文。我们维护一份"全网高频静音词"清单（即被大量用户静音的词），命中即提示 🟡。

### 中文清单

```
推广话术类：
- "DM 我" / "私信我" / "加我微信" / "扫码加群" / "进群"
- "限时优惠" / "仅剩 X 名额" / "立即购买" / "扫码下单"
- "点击链接" / "戳链接" / "链接在简介" / "见评论区第一条"

烂大街开头：
- "兄弟们" / "家人们" / "宝子们" / "今天来聊聊"
- "不得不说" / "说真的" / "讲真"
- "震惊！" / "重磅！" / "突发！"

AI 味浓厚词：
- "在这个 XX 的时代" / "让我们深入探讨"
- "毋庸置疑" / "众所周知" / "无可厚非"
- "赋能" / "抓手" / "颗粒度" / "对齐" (商业语境外滥用时)
```

### 英文清单

```
Promotion language:
- "DM me" / "link in bio" / "check my profile"
- "limited time" / "only X spots left" / "buy now"
- "thread 🧵 below" (without substance)

Generic openers:
- "Let me share" / "Here's the thing" / "Hot take:"
- "Unpopular opinion:" (overused)
- "BREAKING:" / "MUST READ"

AI cliches:
- "Let's dive in" / "Game-changer" / "Paradigm shift"
- "In today's fast-paced world"
- "It's not just X, it's Y" (overused)
```

**处理**：命中任意 1 个 → 🟡 警告；命中 3 个及以上 → 🔴 严重，建议先改写。

---

## 2. AgeFilter 类（时效性陷阱）

**源码依据**：`AgeFilter` 会移除超过保鲜期的推文。Thunder 内存存储有自动修剪机制。这意味着包含强时效性词的推文，过期后**完全无法被推荐**。

### 高时效性词清单

```
绝对时间：
- "今天" / "刚刚" / "5 分钟前" / "今早"
- "today" / "just now" / "moments ago" / "this morning"

事件锚定：
- "刚发生" / "正在直播" / "现场" / "更新中"
- "live now" / "happening now" / "developing story"
```

**处理**：检测到时效词时 → 不算扣分，但在输出中提示用户"这条推文的有效窗口约 24 小时"。

---

## 3. AuthorDiversityScorer 类（自我推销/重复主题）

**源码依据**：`AuthorDiversityScorer` 会衰减重复出现的同作者评分以保证 feed 多样性。同时**过度自我推销词会显著提高 P(mute_author)**。

### 自我推销红线

```
强自夸：
- "我的新课程" / "我的产品" / "我做了" (高频)
- "my new course" / "my product" / "I built"

成就吹嘘：
- "X 万粉丝" / "X 万收入" / "成就"
- "X followers" / "X revenue" / "achieved"

凡尔赛：
- "想不到" / "没想到这么..."
- "Just casually..." / "Apparently I..."
```

**处理**：单次出现 → 🟡；同主题在用户最近 5 条推文中重复 → 🔴（如用户提供历史）。

---

## 4. VFFilter 类（Visibility Filtering 红线）

**源码依据**：`VFFilter` 是 Post-Selection Filter，会移除"deleted/spam/violence/gore"等。命中这类内容，**评分多高都没用，根本不会被分发**。

### 红线词类（不公开具体清单，仅描述类别）

```
- 暴力/血腥描述
- 显式仇恨言论（针对群体）
- 灰产广告（赌博/色情/违禁品）
- 显式煽动违法
- 严重虚假信息（如医疗误导）
```

**处理**：命中 → 🔴 严重，直接建议改写，不进入评分流程。

---

## 5. Format-level Issues（非源码 filter，但影响算法理解）

### 候选自包含性检查（Candidate Isolation 友好度）

**源码依据**：Ranking 阶段 candidates cannot attend to each other，意味着每条推文必须自包含。

检测模式：
- 开头："接上条" / "刚才说的那个" / "如上" / "续"
- "as I said" / "continuing from" / "follow-up to"

**处理**：检测到 → 🟡 警告，提示"算法会独立打分这条推文，依赖前文会让 dwell 表现变差"。

### 信息密度过低（dwell 不友好）

检测：
- 推文字数 < 20（中文）或 < 10 words（英文）
- 不含任何具体名词、数字、动词

**处理**：→ 🟡，提示沉浸力维度会被压低。

---

## 规则维护

本清单基于源码分析 + 社区共识初始化。建议每 3 个月根据 X 算法更新和创作者反馈迭代。

清单不是越长越好——**只保留误杀率 < 5% 的高确定性规则**。模糊判断交给 Layer 2 的 LLM 处理。
