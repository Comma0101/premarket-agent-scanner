# Tim Grittani Evidence Matrix

Each row must map a source-backed lesson to scanner support or a data gap.

| ID | Source IDs | Category | Extracted Lesson | Confidence | Scanner-Supported Fields | Missing Fields | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TG-001 | TG-DVD, TG-Blog | setup | Morning Panic requires a pronounced intraday drop of >= 30% from the recent high to confirm the panic is severe enough. | high | gap %, gap $, direction, intraday drop % | | Replaces vague "large drop" with strict mathematical bounds. |
| TG-002 | TG-DVD, TG-Blog | setup | The Morning Panic must occur after a multi-day run-up of >= 100% over the past 1-3 weeks. | high | multi-day run-up %, volume | | Contextual prerequisite for the setup. |
| TG-003 | TG-DVD, TG-Blog | setup | Relative Volume (RVOL) during the panic must be extreme, specifically >= 5x normal volume. | high | RVOL, volume | | Replaces vague "high volume" with a strict multiplier. |
| TG-004 | TG-DVD, TG-Blog | setup | The Time of Day (TOD) cutoff for a valid Morning Panic entry is strictly the first 30 minutes of the trading day (09:30 - 10:00 ET). | high | TOD timestamp | | Entries after 10:00 ET are lower probability and should be avoided. |
| TG-005 | TG-DVD, TG-Blog | setup | Gap and Crap requires an initial gap up of >= 10% at the open, followed by a failure to make new highs within the first 30 minutes. | high | gap %, gap $, direction, TOD timestamp | | Replaces vague "significant gap" and defines the fade timeframe. |
