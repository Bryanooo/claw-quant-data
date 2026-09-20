---
name: claw-quant-event-research
description: Investigate why an A-share moved by combining Claw Quant price/event evidence with official announcements, policy documents, and company releases. Use for price-move attribution, catalyst, news, announcement, policy-impact, or event-study requests; do not treat media narratives as proven causes.
---

# Claw Quant Event Research

Start with the governed research surface:

```bash
./clawq stock research-pack TS_CODE --lookback-days 180
./clawq research technicals TS_CODE --lookback-days 400
./clawq research event-study TS_CODE --event-date EVENT_DATE --pre-days 5 --post-days 10
```

Read [references/evidence-policy.md](references/evidence-policy.md) before external research.
If official-announcement coverage is reported missing or `unknown_empty`, search authoritative
external sources instead of claiming there was no announcement.

Construct an event ledger with event time, source, fact, affected mechanism, expected sign,
and the first market session able to react. Compare the security's return with its benchmark
and sector before attributing an idiosyncratic move.

Label every statement as one of:

- verified fact;
- market narrative supported by named sources;
- analyst inference;
- unresolved hypothesis.

Conclude with ranked drivers and disconfirming evidence. Use causal language only when timing,
mechanism, and relative-price evidence align; otherwise say the event is associated with the
move, not that it caused it.
