# Chain Whitelist And Source Tiering Design

## 1. Context

The current source system is configured as a flat list in [config/sources.yaml](/Users/57block/Documents/code/web3-automated-agent/config/sources.yaml). Official feeds, website scrapers, RSSHub Twitter bridges, GitHub label searches, and Tavily discovery queries all enter the same pipeline at the same level.

This creates two problems:

- operational instability: several fetch methods are inherently fragile or rate-limited, especially RSSHub, broad GitHub search, and web discovery queries;
- weak trust separation: high-signal official opportunity sources are mixed with low-signal discovery sources, so downstream verification and scoring start from the same baseline even when source quality is very different.

The desired direction is to monitor Web3 opportunities primarily from chain ecosystems themselves: chain websites, foundation blogs, official grants and hackathon pages, governance forums, and a small set of official social accounts. Auxiliary discovery sources should remain available for recall, but should no longer dominate the main pipeline.

## 2. Goal

Restructure source management around a whitelist of monitored chains and a tiered source model:

- define a curated Top 50 chain whitelist derived from DefiLlama, filtered to chains with meaningful ecosystem incentive activity;
- attach a standard official source set to each selected chain;
- downgrade GitHub, RSSHub, and Tavily to auxiliary discovery sources;
- allow downstream verification, scoring, and reporting to distinguish officially confirmed opportunities from unconfirmed discovery candidates.

This design improves precision without removing controlled recall.

## 3. Scope

In scope:

- chain whitelist configuration model;
- source registry split between official and discovery sources;
- metadata additions required for trust-aware processing;
- pipeline behavior changes for official vs discovery sources;
- reporting and output behavior changes;
- migration path from the current flat source list.

Out of scope:

- full automatic source generation from DefiLlama;
- Discord real-time listener design changes;
- Copilot UI changes;
- immediate expansion to every ecosystem social platform.

## 4. Chain Selection Policy

The monitored chain universe starts from a large DefiLlama-based list with a target size around 50, but inclusion is not purely rank-based.

Chains are included when they satisfy the following policy:

- they are L1s or major L2s with active ecosystem development;
- they have a credible official surface for opportunity publication, such as a foundation, official blog, grants page, hackathon page, or governance forum;
- they plausibly publish opportunities relevant to builders, researchers, or bounty hunters.

Chains are excluded when they are high TVL but low opportunity signal, purely application-like, or lack identifiable official opportunity surfaces.

This produces a curated Top 50-style whitelist rather than a blind top-50 import.

## 5. Configuration Model

The source system should move from one flat file toward two layers of configuration.

### 5.1 Chain registry

Create a dedicated chain registry file, for example `config/chains.yaml`, with one record per monitored chain.

Suggested fields:

- `chain_id`: internal stable identifier, such as `ethereum`, `solana`, `sui`;
- `name`: display name;
- `defillama_slug`: optional mapping back to DefiLlama;
- `category`: `l1` or `l2`;
- `priority`: numeric or categorical ranking for operational focus;
- `enabled`: whether the chain is currently in scope.

The chain registry becomes the authoritative list of monitored ecosystems.

### 5.2 Source registry

Replace the single undifferentiated source list with source records that explicitly identify their chain and trust tier.

Suggested fields added to each source:

- `chain`: links the source to a chain in the chain registry;
- `source_tier`: `official` or `discovery`;
- `signal_type`: `blog`, `grants`, `hackathon`, `governance`, `social`, `bounty`, or `discovery`;
- `official`: boolean convenience flag;
- `enabled`: unchanged operational switch.

The source registry may be split into:

- `config/sources.official.yaml`
- `config/sources.discovery.yaml`

or represented as one file with clear tier metadata. The split-file approach is preferred because it makes operator intent obvious and prevents accidental mixing.

## 6. Standard Official Source Set Per Chain

Each included chain should attempt to populate a standard set of official surfaces. The chosen default set is:

- official website or blog;
- foundation or ecosystem fund surface;
- grants page;
- hackathon page;
- governance forum;
- official X account.

Not every chain will have every surface. Missing surfaces are acceptable, but the chain should still have enough official presence to justify inclusion in the whitelist.

Priority order for collection:

1. RSS or Atom feeds from official blog or announcement surfaces.
2. Stable official webpages suitable for targeted scraping.
3. Governance forum RSS feeds where available.
4. Official social accounts, treated as official but lower confidence than a first-party site unless later corroborated.

## 7. Discovery Source Policy

GitHub search, RSSHub, and Tavily remain in the system, but no longer define the main monitoring surface.

Their role changes to auxiliary discovery only:

- they can surface candidate opportunities that may not yet be present in official feeds;
- they cannot, by themselves, justify high-confidence output;
- they should be processed after or separately from official sources;
- they should be explicitly labeled as discovery-origin records.

This preserves recall while reducing false confidence.

## 8. Pipeline Behavior Changes

The fetch stage should stop treating all enabled sources as operationally equivalent.

### 8.1 Fetch ordering

Preferred behavior:

- run `official` sources as the primary collection set;
- run `discovery` sources as a secondary collection set;
- maintain per-tier fetch health so instability in discovery sources does not appear equivalent to official source failures.

### 8.2 Record metadata

Each fetched item should carry forward:

- `chain`
- `source_tier`
- `signal_type`
- `official`

These fields must survive through deduplication, classification, verification, scoring, and reporting.

### 8.3 Classification and candidate state

Discovery-origin records that look relevant but lack confirmation should be allowed into a candidate state rather than being treated as fully verified opportunities.

Suggested states:

- `official_confirmed`
- `discovered_unconfirmed`
- `rejected_noise`
- `rejected_fraud`

## 9. Verification And Scoring Policy

The trust improvement depends on downstream logic using the new source-tier metadata.

### 9.1 Origin trust

Verification should assign a higher initial origin-trust value to official first-party sources:

- chain website, foundation blog, grants page, hackathon page, governance forum;
- official social accounts only slightly lower than first-party websites.

Discovery sources start from a lower origin-trust baseline.

### 9.2 Cross-confirmation rule

A discovery-origin record should not receive a high-confidence verdict unless it is corroborated by at least one official source, or another equally strong official signal.

Examples:

- a tweet from RSSHub mentioning a grant is only high-confidence once matched to an official grants page, blog post, or governance announcement;
- a GitHub issue labeled `bounty` may remain a valid candidate, but should not be elevated to top-trust unless corroborated by an official program surface.

### 9.3 Score ceiling

Unconfirmed discovery-origin records should have a ceiling that prevents them from appearing as top-confidence opportunities.

This can be implemented as either:

- a hard score cap; or
- a verdict cap that prevents `trusted` status without official corroboration.

### 9.4 Reporting semantics

Final outputs should separate:

- officially confirmed opportunities;
- discovered but unconfirmed candidates.

This distinction should appear in generated reports and Slack output.

## 10. Operational Guidance

### 10.1 Reliability priorities

Preferred fetch methods by stability:

1. official RSS or Atom feeds;
2. stable official webpages with targeted scraping;
3. governance RSS feeds;
4. official social accounts via bridge or other adapter;
5. discovery search sources.

### 10.2 Failure interpretation

Source-health monitoring should distinguish between:

- `official source degraded`: higher operational priority;
- `discovery source degraded`: lower priority unless recall is suffering materially.

### 10.3 Maintenance model

Operators should maintain sources chain-by-chain, not source-type-by-source-type.

This means the maintenance question becomes:

- “What are the official opportunity surfaces for Sui?”

instead of:

- “What RSS feeds do we have globally?”

That framing better matches how Web3 opportunities are actually published.

## 11. Migration Plan

The migration should be incremental.

Phase 1:

- introduce chain and tier metadata into the existing source config;
- mark current official sources and discovery sources;
- keep runtime behavior mostly unchanged.

Phase 2:

- add a dedicated chain registry;
- split official and discovery source definitions;
- update fetch orchestration to run official sources first and record per-tier health.

Phase 3:

- update verification and scoring to use source-tier metadata;
- add report separation for confirmed vs unconfirmed opportunities.

Phase 4:

- prune or replace weak discovery sources that do not contribute useful candidates;
- expand chain-by-chain official coverage within the curated whitelist.

## 12. Acceptance Criteria

The redesign is successful when:

- monitored ecosystems are represented explicitly as a curated chain whitelist;
- every source is attached to a chain and tagged as `official` or `discovery`;
- official sources are the main monitoring path;
- GitHub, RSSHub, and Tavily are retained only as auxiliary discovery inputs;
- verification and scoring distinguish official confirmation from unconfirmed discovery;
- final outputs clearly separate confirmed opportunities from candidates.
