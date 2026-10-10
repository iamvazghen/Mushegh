# Daily briefing — how to open the owner's day

When the owner asks "what's my day", "morning brief", or the proactive morning slot fires,
compose ONE spoken paragraph in this order — skip any empty section silently:

1. **Calendar** (`list_events`): today's events with times; flag the first one if it's within
   2 hours ("your 10 o'clock with X is in 40 minutes").
2. **Email** (`read_email`): count + only the senders/subjects that look like they need him
   today. Never read marketing mail aloud.
3. **Tasks** (Notion `list_tasks`): overdue first, then due-today. Three max — he can ask for more.
4. **News** (`news_brief`): two headlines from categories he follows, one clause each.
   (An earlier draft named a news tool that was never in this registry — it came from a
   different project's MCP server. `test_skill_suite.py` caught it; this name is the real one.)
5. **Weather** (`weather`) only if it changes a decision (rain, extremes, travel day).

Rules:
- Whole brief ≤ 25 seconds spoken. Prioritize what CHANGES HIS BEHAVIOR today; drop the rest.
- Numbers rounded for speech ("about twenty emails", not "19 emails").
- End with the single most important thing: "The one thing that matters, sir: X."
- If everything is empty: "A quiet day, sir — nothing urgent anywhere." Never pad.
