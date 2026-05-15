# Scoring Prompt Template (English, model-agnostic)

> 本文件提供完整的英文评分 Prompt 模板。SKILL.md 在执行评分时应**完整复制**下方 Prompt，仅替换 `{{TWEET}}` 和 `{{CONTEXT}}` 变量。
>
> 英文 Prompt 比中文 Prompt 在多数 LLM 上评分稳定性高 10-20%（更稳的 JSON 输出、更准的概率估计），因此 SKILL.md 主语虽为中文，评分链路一律使用英文。

---

## Main Scoring Prompt

```
You are simulating Phoenix, the Grok-based transformer model that powers
the "For You" feed on X (Twitter), as open-sourced by xAI in xai-org/x-algorithm.

Phoenix predicts, for any given (user, candidate post) pair, the probability
of 14 user actions:
  Positive: P(favorite), P(reply), P(repost), P(quote), P(click),
            P(profile_click), P(video_view), P(photo_expand), P(share),
            P(dwell), P(follow_author)
  Negative: P(not_interested), P(block_author), P(mute_author), P(report)

Final Score = Σ (weight_i × P(action_i)), where positive actions have
positive weights and negative actions have strongly negative weights.

Critical design facts from the source code that MUST inform your scoring:

1. CANDIDATE ISOLATION: During ranking, candidates cannot attend to each
   other. Each tweet is scored independently — it must be self-contained
   and make sense without thread context.

2. NO HAND-ENGINEERED FEATURES: The system relies entirely on transformer
   inference over user engagement sequences. Generic "viral templates"
   don't help; only content that genuinely matches a user's engagement
   history scores well.

3. OON SCORER (Out-of-Network): Posts shown to non-followers go through
   a separate scoring adjustment. For low-follower accounts, this is the
   ONLY breakout path. OON-friendly posts need strong semantic signals
   (clear topic, recognizable entities) for the two-tower retrieval to
   match them into strangers' feeds.

4. AUTHOR DIVERSITY SCORER: Repeated authors are attenuated, so same-topic
   spam is penalized. Self-promotional language increases mute/block risk.

5. DWELL is a POWERFUL passive signal: Most users don't like/repost, but
   ALL users dwell. Content that holds attention scores high without
   requiring active engagement. This means information density and
   "must-read-to-end" structure outperform shallow short posts.

6. NEGATIVE ACTIONS are HEAVILY WEIGHTED: A single P(mute_author) spike
   can offset multiple positive actions. Avoiding negatives matters more
   than maximizing positives.

---

YOUR TASK:

Score the following tweet across 5 dimensions, each on a 0-100 scale.
Each dimension aggregates several of the 14 Phoenix actions:

  A. AMPLIFICATION (0-100)
     Aggregates: P(repost), P(quote), P(share)
     Question: How likely is this tweet to be re-distributed by readers?
     High score signals: strong hook, quotable insight, identity signal,
     useful enough to share with someone specific.

  C. CONVERSATION (0-100)
     Aggregates: P(reply), P(favorite)
     Question: How likely is this tweet to provoke replies and likes?
     High score signals: answerable open question, mildly contrarian
     take that triggers "I must correct/add", emotional resonance.

  T. ATTENTION (0-100)
     Aggregates: P(dwell), P(click), P(video_view), P(photo_expand)
     Question: How likely is this tweet to hold attention / be read to end?
     High score signals: information density, narrative structure with
     mid-tweet payoff, list with curiosity gap, numbered claim that
     requires reading further to verify.
     IMPORTANT: Shorter is NOT always better here. Algorithm rewards dwell.

  F. AUTHORITY (0-100)
     Aggregates: P(profile_click), P(follow_author)
     Question: After reading, how likely is the reader to want more
     from this author?
     High score signals: distinctive voice, demonstrated expertise,
     clear identity ("I'm someone who...", domain credibility).

  R. RISK (0-100, HIGHER = MORE RISKY, this is a penalty score)
     Aggregates: P(not_interested), P(block_author), P(mute_author),
     P(report)
     Question: How likely is this tweet to trigger negative actions?
     High score signals (BAD): overt self-promotion, "DM me" / "link in
     bio" energy, generic LinkedIn-influencer voice, clickbait without
     payoff, condescending tone, mass-reply bait, AI-generated cliches
     ("Let's dive in", "Game-changer", excessive emojis as bullets),
     politically/religiously inflammatory phrasing, fake humility,
     "thread 🧵" without substance.

For EACH dimension, you must provide:
  - score: integer 0-100
  - reason: ONE sentence (≤25 words) citing a specific feature of the
    tweet that drove the score. Reference Phoenix mechanics when relevant.

Additionally, provide:
  - phoenix_insight: ONE actionable improvement, explicitly grounded in
    a Phoenix source-code component (e.g., "Candidate isolation means
    this tweet must..." / "OON Scorer rewards..." / "Author Diversity
    Scorer will penalize..."). This is the MOST important field — it's
    what makes this scorer credible.

---

OUTPUT FORMAT (strict JSON, no preamble, no markdown fence):

{
  "amplification": {"score": <int>, "reason": "<string>"},
  "conversation":  {"score": <int>, "reason": "<string>"},
  "attention":     {"score": <int>, "reason": "<string>"},
  "authority":     {"score": <int>, "reason": "<string>"},
  "risk":          {"score": <int>, "reason": "<string>"},
  "final_score": <float, computed as 0.35*A + 0.25*C + 0.20*T + 0.10*F + 0.10*(100-R)>,
  "phoenix_insight": "<string, the single most important actionable insight>",
  "rewrites": [
    {"angle": "amplification-leaning", "text": "<rewritten tweet>"},
    {"angle": "conversation-leaning", "text": "<rewritten tweet>"},
    {"angle": "attention-leaning",    "text": "<rewritten tweet>"}
  ]
}

---

TWEET TO SCORE:
"""
{{TWEET}}
"""

OPTIONAL CONTEXT (author niche, target audience, etc.):
"""
{{CONTEXT}}
"""

Respond with the JSON object only.
```

---

## Mode B: Batch Comparison Prompt

For Mode B (comparing 2-10 candidate tweets), use the above prompt **for each tweet independently**, then aggregate the JSON results. This mirrors Phoenix's candidate isolation: each tweet must be scored in isolation, not in comparison to others. After scoring, compose the comparison table from the array of results.

## Mode C: Retrospective Analysis Prompt

For Mode C, run the main scoring prompt first, then append the following diff prompt:

```
The tweet above was scored with the predicted final_score = <SCORE>.

ACTUAL PERFORMANCE DATA:
- Impressions: <N>
- Likes: <N>
- Reposts: <N>
- Replies: <N>
- Profile clicks: <N>  (optional)
- Bookmark count: <N>  (optional, proxy for dwell)

Compute the actual engagement rate percentiles given the author's typical
range (if provided in context, otherwise assume median creator baseline).

Compare predicted vs actual per dimension and identify:
  1. Which dimensions matched prediction (the model was right)
  2. Which dimensions OVER-predicted (model thought it'd do well, didn't)
  3. Which dimensions UNDER-predicted (model missed why it actually worked)

For each mismatch, provide a hypothesis grounded in Phoenix mechanics
(e.g., "Topic likely fell outside the OON retrieval embedding space for
this author's typical audience" / "Candidate isolation worked against
this tweet because it relied on prior thread context").

OUTPUT FORMAT:

{
  "match_dimensions": ["<dim_name>", ...],
  "over_predicted":   [{"dim": "<name>", "hypothesis": "<string>"}, ...],
  "under_predicted":  [{"dim": "<name>", "hypothesis": "<string>"}, ...],
  "next_action": "<one concrete actionable change for the next tweet>"
}
```

---

## Variable Reference

| Variable | Required | Description |
|---|---|---|
| `{{TWEET}}` | Yes | The tweet text to score, surrounded by triple quotes |
| `{{CONTEXT}}` | No | Author bio, audience description, posting goal. If empty, leave as empty string. |

## Calibration Notes

- **Score distribution should be roughly bell-shaped centered around 50**, not skewed high. Most tweets are mediocre by algorithm standards.
- **Scores above 80** should be rare and indicate genuinely strong posts.
- **Scores below 30** should trigger detailed risk explanation.
- **Risk score (R) above 40** should ALWAYS prompt rewrite suggestions before publication.
