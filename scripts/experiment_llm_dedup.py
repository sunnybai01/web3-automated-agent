#!/usr/bin/env python3
"""
实验：对比 LLM 摘要 vs 原始文本 的向量去重效果

核心假设：同一个机会被不同源报道时，内容差异大，导致原始文本的 embedding
相似度低于阈值（漏过）；但 LLM 提取的结构化摘要去除噪音后，embedding 会更接近。

实验步骤：
1. 从 DB 读取全部 events
2. 按标题相似度找出候选重复对
3. 对每对：
   a. 原始文本 (title + description) → embedding → cosine similarity
   b. LLM 提取结构化摘要 → embedding → cosine similarity
   c. 对比两个 similarity 的差异
4. 输出对比表格

用法：
    python scripts/experiment_llm_dedup.py [--dry-run] [--limit 10]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Docker hostname "postgres" doesn't resolve outside Docker — force localhost
os.environ["POSTGRES_HOST"] = os.environ.get("EXPERIMENT_PG_HOST", "localhost")
os.environ["CHROMA_HOST"] = os.environ.get("EXPERIMENT_CHROMA_HOST", "localhost")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import settings
from src.classifier.llm_gateway import LLMGateway, PROVIDER_PRIORITY

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("experiment")


SUMMARY_EXTRACTION_PROMPT = """Extract structured metadata from this Web3 opportunity description.

Return ONLY a JSON object (no markdown, no backticks) with these keys:
- "canonical_title": a normalized title (remove emoji, hashtags, handle mentions, merge "by X" suffixes)
- "deadline": ISO 8601 date or null
- "publish_date": ISO 8601 date of when this was published (extract from context if possible) or null
- "location_type": "online" | "offline" | "hybrid" | "unknown"
- "ecosystem": which blockchain/ecosystem (ethereum, solana, arbitrum, etc.) or null
- "summary": one concise sentence (max 140 chars) summarizing the core opportunity

Content:
{content}

JSON:"""


def load_events():
    """Load all grant/hackathon events from DB."""
    from src.db.database import SessionLocal
    from src.db.models import Event

    db = SessionLocal()
    try:
        events = (
            db.query(Event)
            .filter(Event.status.in_(["new", "pushed"]))
            .filter(Event.event_type.in_(["grant", "hackathon"]))
            .order_by(Event.created_at.desc())
            .all()
        )
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "title": e.title or "",
                "description": e.description or "",
                "source_url": e.source_url or "",
                "created_at": e.created_at,
            }
            for e in events
        ]
    finally:
        db.close()


def find_candidate_pairs(events, limit=10):
    """Find pairs of events with similar titles (Jaccard on word sets)."""
    import re

    def tokenize(text):
        return set(re.findall(r"[a-z0-9]{3,}", text.lower()))

    pairs = []
    for i in range(len(events)):
        ti = tokenize(events[i]["title"])
        for j in range(i + 1, len(events)):
            tj = tokenize(events[j]["title"])
            if not ti or not tj:
                continue
            intersection = ti & tj
            union = ti | tj
            jaccard = len(intersection) / len(union)
            if jaccard >= 0.25:  # loose threshold to catch "Open House Online" vs "Open House London"
                pairs.append((events[i], events[j], jaccard))

    pairs.sort(key=lambda x: -x[2])
    return pairs[:limit]


def get_embedding(text: str) -> list[float] | None:
    """Get embedding using ChromaDB's default embedding function."""
    try:
        import chromadb
        from chromadb.utils import embedding_functions

        ef = embedding_functions.DefaultEmbeddingFunction()
        result = ef([text])
        if result is None or (hasattr(result, '__len__') and len(result) == 0):
            return None
        # ChromaDB may return numpy array — convert to list
        emb = result[0]
        if hasattr(emb, 'tolist'):
            return emb.tolist()
        return list(emb) if emb is not None else None
    except Exception as e:
        logger.warning(f"Embedding failed: {e}")
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def extract_summary(llm: LLMGateway, content: str) -> dict | None:
    """Call LLM to extract structured summary."""
    try:
        raw = llm.complete(
            system_prompt="You are a precise metadata extractor. Return ONLY valid JSON.",
            user_prompt=SUMMARY_EXTRACTION_PROMPT.format(content=content[:3000]),
            json_mode=True,
            temperature=0.1,
            max_tokens=300,
        )
        if raw is None:
            return None
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:]) if lines[0].startswith("```") else raw
            if raw.endswith("```"):
                raw = raw[:-3]
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"LLM extraction failed: {e}")
        return None


def format_summary_text(s: dict) -> str:
    """Format extracted summary into a text for embedding."""
    parts = [
        s.get("canonical_title", ""),
        s.get("summary", ""),
        f"deadline:{s.get('deadline', 'none')}",
        f"location:{s.get('location_type', 'unknown')}",
        f"ecosystem:{s.get('ecosystem', 'unknown')}",
    ]
    return " | ".join(parts)


def main():
    parser = argparse.ArgumentParser(description="LLM dedup experiment")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM calls, only compute raw similarity")
    parser.add_argument("--limit", type=int, default=10, help="Max pairs to test (default: 10)")
    parser.add_argument("--slack", action="store_true", help="Send results to Slack after experiment")
    args = parser.parse_args()

    print("=" * 90)
    print("LLM 摘要 vs 原始文本 向量去重效果对比实验")
    print(f"时间: {datetime.now(timezone.utc).isoformat()}")
    print(f"LLM Provider: {PROVIDER_PRIORITY[0] if PROVIDER_PRIORITY else 'none'}")
    print(f"当前去重阈值: {settings.SIMILARITY_THRESHOLD}")
    print("=" * 90)

    # 1. Load events
    events = load_events()
    print(f"\n📊 从数据库加载了 {len(events)} 条 events (grant + hackathon)")

    # 2. Find candidate pairs
    pairs = find_candidate_pairs(events, limit=args.limit)
    print(f"🔍 找到 {len(pairs)} 对候选重复（标题 Jaccard >= 0.25）")

    if not pairs:
        print("没有找到候选重复对，退出。")
        return

    # 3. Initialize LLM if needed
    llm = None
    if not args.dry_run:
        try:
            llm = LLMGateway()
            if not llm._clients:
                print("⚠️  没有可用的 LLM provider，回退到 --dry-run 模式")
                args.dry_run = True
        except Exception as e:
            print(f"⚠️  LLM 初始化失败: {e}，回退到 --dry-run 模式")
            args.dry_run = True

    # 4. Compare each pair
    print(f"\n{'─' * 90}")
    print(f"{'#':<3} {'Event A':<6} {'Event B':<6} {'Jaccard':<8} {'Raw Sim':<9} {'LLM Sim':<9} {'Delta':<8} {'A→B':<8} {'Verdict'}")
    print(f"{'─' * 90}")

    results = []
    for idx, (a, b, jaccard) in enumerate(pairs, 1):
        raw_a = f"{a['title']} {a['description']}"[:3000]
        raw_b = f"{b['title']} {b['description']}"[:3000]

        # Raw text embedding similarity
        emb_a = get_embedding(raw_a)
        emb_b = get_embedding(raw_b)
        raw_sim = cosine_similarity(emb_a, emb_b) if emb_a and emb_b else 0.0

        # LLM summary embedding similarity
        llm_sim = None
        if not args.dry_run and llm:
            sum_a = extract_summary(llm, raw_a)
            sum_b = extract_summary(llm, raw_b)
            if sum_a and sum_b:
                text_a = format_summary_text(sum_a)
                text_b = format_summary_text(sum_b)
                emb_sa = get_embedding(text_a)
                emb_sb = get_embedding(text_b)
                if emb_sa and emb_sb:
                    llm_sim = cosine_similarity(emb_sa, emb_sb)

        # Compute delta
        delta = round(llm_sim - raw_sim, 4) if llm_sim is not None else None

        # Verdict
        threshold = settings.SIMILARITY_THRESHOLD
        raw_ok = "✅ DEDUP" if raw_sim >= threshold else "❌ MISS"
        llm_ok = "✅ DEDUP" if (llm_sim is not None and llm_sim >= threshold) else (
            "⚠️ MISS" if llm_sim is not None else "⏳ SKIP"
        )
        verdict = f"{raw_ok} → {llm_ok}"

        delta_str = f"+{delta:.4f}" if delta is not None and delta > 0 else (f"{delta:.4f}" if delta is not None else "N/A")
        llm_str = f"{llm_sim:.4f}" if llm_sim is not None else "N/A"

        print(f"{idx:<3} #{a['id']:<5} #{b['id']:<5} {jaccard:.4f}   {raw_sim:.4f}   {llm_str:<9} {delta_str:<8} {verdict}")

        results.append({
            "pair": (a["id"], b["id"]),
            "title_a": a["title"][:60],
            "title_b": b["title"][:60],
            "jaccard": round(jaccard, 4),
            "raw_similarity": round(raw_sim, 4),
            "llm_similarity": round(llm_sim, 4) if llm_sim is not None else None,
            "delta": delta,
            "raw_dedup": raw_sim >= threshold,
            "llm_dedup": llm_sim is not None and llm_sim >= threshold,
        })

    # 5. Summary
    print(f"{'─' * 90}")
    raw_dedup_count = sum(1 for r in results if r["raw_dedup"])
    llm_dedup_count = sum(1 for r in results if r["llm_dedup"])
    total = len(results)
    print(f"\n📈 总结:")
    print(f"   原始文本去重命中: {raw_dedup_count}/{total} ({raw_dedup_count/total*100:.0f}%)")
    if not args.dry_run:
        print(f"   LLM 摘要去重命中: {llm_dedup_count}/{total} ({llm_dedup_count/total*100:.0f}%)")
        improvements = [r for r in results if r["delta"] is not None and r["delta"] > 0.05]
        print(f"   显著提升 (delta > 0.05): {len(improvements)} 对")
        if improvements:
            for r in improvements:
                print(f"     #{r['pair'][0]} ↔ #{r['pair'][1]}: +{r['delta']:.4f}")

    # 6. Save detailed results
    out_path = Path("reports") / f"dedup_experiment_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str))
    print(f"\n📁 详细结果已保存到: {out_path}")

    # 7. Send to Slack if requested
    if args.slack:
        send_to_slack(results, raw_dedup_count, llm_dedup_count, total, out_path, args.dry_run)


def send_to_slack(results, raw_dedup_count, llm_dedup_count, total, out_path, dry_run):
    """Format experiment results and send to Slack."""
    from src.dispatch.slack_client import SlackDispatcher

    slack = SlackDispatcher()
    if not slack.is_configured:
        print("⚠️  Slack 未配置，跳过发送。")
        return

    # Build summary text
    lines = [
        "*🧪 LLM 摘要 vs 原始文本 去重对比实验*",
        f"时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"数据: {total} 对候选重复 (来自 11 条 events)",
        f"",
        f"*结果:*",
        f"• 原始文本去重命中: {raw_dedup_count}/{total} ({raw_dedup_count/total*100:.0f}%) ⚠️ 阈值={settings.SIMILARITY_THRESHOLD}",
    ]
    if not dry_run:
        lines.append(f"• LLM 摘要去重命中: {llm_dedup_count}/{total} ({llm_dedup_count/total*100:.0f}%)")

    # Top pairs table
    lines.append("")
    lines.append("*Top 候选对 (按 Jaccard 排序):*")
    lines.append("```")
    header = f"{'#':<3} {'#A':<5} {'#B':<5} {'Jaccard':<8} {'Raw':<8} {'LLM':<8} {'Delta':<8}"
    lines.append(header)
    lines.append("-" * len(header))
    for idx, r in enumerate(results[:8], 1):
        llm_str = f"{r['llm_similarity']:.4f}" if r["llm_similarity"] is not None else "N/A"
        delta = r["delta"]
        delta_str = f"+{delta:.4f}" if delta is not None and delta > 0 else (f"{delta:.4f}" if delta is not None else "N/A")
        lines.append(f"{idx:<3} #{r['pair'][0]:<4} #{r['pair'][1]:<4} {r['jaccard']:.4f}   {r['raw_similarity']:.4f}   {llm_str:<8} {delta_str:<8}")
    lines.append("```")

    # Conclusion
    lines.append("*结论:*")
    if not dry_run and llm_dedup_count > 0:
        improvements = [r for r in results if r["delta"] is not None and r["delta"] > 0.05]
        lines.append(f"LLM 摘要显著提升 ({len(improvements)} 对 delta > 0.05)，建议在 L1 URL 去重之后增加 LLM 摘要提取节点。")
    else:
        lines.append(f"原始文本向量去重 ({settings.SIMILARITY_THRESHOLD}) 全部漏过 {total} 对候选重复，需要降低阈值或改进方案。")

    lines.append(f"详细报告: `{out_path}`")

    try:
        slack.client.chat_postMessage(
            channel=slack.channel_id,
            text="LLM 去重实验报告",
            blocks=[{
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(lines)},
            }],
            unfurl_links=False,
        )
        print("✅ 已发送到 Slack")
    except Exception as e:
        print(f"⚠️  Slack 发送失败: {e}")


if __name__ == "__main__":
    main()
