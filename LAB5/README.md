# LAB 5 — DL-07 Agentic AI System II

**ประภากรณ์ ภิธรรมมา · Prapakorn Phithamma · 116730462033-5**
Computer Engineering Department, Engineering Faculty, RMUTT

Module 04 (**External Data Services**) of an eight-person team build:
[PROxTAE/travel-safety-ai](https://github.com/PROxTAE/travel-safety-ai), a travel
safety assistant that answers questions about a journey from live weather, hazard,
routing and transit data.

This module is the one that talks to the outside world. Everything the other seven
modules reason about — every hazard, forecast, route and transit status — enters the
system through here. Nothing downstream can be more truthful than what this module
hands it.

All eight phases of the module plan are delivered and merged. Every line of
module 04 — adapters, transport, registry, endpoints and tests — is my own work
within the eight-person build; the other seven modules are my teammates'.

```
8 endpoints · 9 registered providers · 7 callable · 645 tests · 28 live canaries
```

## What it does

| Capability | Endpoint | Providers |
| --- | --- | --- |
| Geocoding | `POST /internal/v1/geocode/search` | Open-Meteo Geocoding |
| Weather | `POST /internal/v1/weather/query` | Open-Meteo Forecast |
| Hazards | `POST /internal/v1/disasters/query` | USGS · GDACS · NASA EONET |
| Road routing | `POST /internal/v1/routes/query` | openrouteservice Directions |
| Emergency places | `POST /internal/v1/places/nearby` | openrouteservice POIs |
| Transit realtime | `POST /internal/v1/transport/query` | GTFS-Realtime (MTA) |
| Combined context | `POST /internal/v1/context/query` | all of the above, in parallel |
| Provider health | `GET /internal/v1/providers/health` | — |

Every provider is real. There is no mock path, no sample data behind a flag, and a
CI check that fails the build if one appears.

## The rule the whole module is built around

**It never decides that anything is safe.**

`severity` is `UNKNOWN` on every hazard. `risk_level` is `UNKNOWN` on every route
and `exposure` is `null`. Not because the information is missing — the provider's own
numbers are all carried through — but because turning a magnitude into a danger level
is a judgement, and the judgement belongs to the risk and decision modules.

A live query returns 512 hazard events with `severity: UNKNOWN` on all of them. That
is the correct output. CI greps for any attempt to fill those fields in.

The same principle runs through the smaller decisions. An empty list always means
"nothing was reported" and never "we could not find out" — if every hazard source
times out, the request fails with an error code rather than returning `events: []`,
because `[]` reads as *no hazards near you*. A weather value the provider did not
supply is `null` with a quality flag, never `0`, because `0` reads as *no rain*.

## Five traps that were only found by calling the real thing

Each of these produced output that looked completely healthy.

**A GTFS realtime feed and its own timetable use different trip ids.** The schedule
writes `BSP26GEN-A055-Sunday-00_051550_A..N54R`; the realtime feed writes
`051550_A..N54R`. Joining them with `==` matches **zero of sixty-seven** live trips —
and nothing errors, because a trip with no schedule attached is a perfectly valid
record. A broken join returns sixty-six healthy-looking records that all say
`UNKNOWN`, and the endpoint returns 200. The function that fixes it was written
three times, and the first two wrong versions also matched nothing while looking
fine. There is now a test for each wrong version.

**GTFS clock times are local to the transit agency.** Reading a New York timetable as
UTC made every train exactly 250 minutes late — a four-hour offset plus a real
ten-minute delay. A plausible enough number to ship.

**Freshness was measuring the age of the earthquake, not the age of the data.** With
the ten-minute budget the project gives hazard data, that marked every event older
than ten minutes `STALE`: a live query returned 268 events, **268 of them STALE and
none FRESH**, including all 32 above magnitude 5.0. A field with one value on every
record carries no information, and a consumer filtering on it as the specification
tells them to receives nothing at all. The whole 346-test suite passed while this was
true, because nothing asserted what the field *meant* — only that it was populated.

**`official` was true on every single record.** It meant "a government body recorded
this", which all three hazard sources satisfy, so a magnitude **-0.48** earthquake
nobody can feel was `official: true` — and the project's own acceptance rules make
"official closure or high alert" force an AVOID decision **over** both the language
model and the risk score, so everything was feeding the strongest shortcut in the
system. It now means "a warning has actually been issued" and returns 96 of 512.

**A plausible-looking category id returned the wrong kind of place.** A "nearest
hospital" search came back with a pub 250 m away. The ids were then read from the
provider's own category endpoint rather than guessed.

## Two findings that changed the shared contract

The module's real output was validated against the team's frozen JSON Schema, which
surfaced nine mismatches in the first round and six in the second. Two were more than
naming.

**A route cannot be required to carry a risk assessment it has not had.** The schema
made `exposure` a required, non-nullable object, and this module is its producer — so
the only way to satisfy it was `score: 0, closed: false`, which is a route across a
closed bridge arriving at the decision engine asserting, in the contract's own
vocabulary, that nothing is wrong. The schema now allows null, with a conditional rule
that a route without an exposure must also carry `risk_level: UNKNOWN`, so
"not yet assessed" cannot be read as "checked, and fine".

**Two of nineteen real hospitals near Victory Monument have no name in
OpenStreetMap**, one of them 335 m away — closer than several that do. The schema
required a non-null name, which left two options and both were wrong: drop the record
and hide the nearest hospital from somebody who needs one, or invent a label the
provider never said. It is nullable now.

The gap also revealed why the first round had been missed: `jsonschema` treats
`format` as an annotation unless a checker is passed, so every `format: uuid` in the
contract had been passing without being enforced by anyone.

## Layout

```
external-data/
  app/
    adapters/      one per provider, all behind a common interface
    transport/     shared HTTP: timeout budget, retry, circuit breaker,
                   concurrency limiter, quota tracker, SSRF host guard
    domain/        canonical records, enums, queries, typed errors
    services/      duplicate grouping, health probe, context fan-out
    providers/     the registry that decides what may be called
    api/           internal endpoints and the error envelope
    cache/         Redis with a stampede lock and negative caching
  config/providers.yaml     governance record: licence, quota, coverage, owner
  tests/                    29 files, 517 tests, real captured fixtures
docs/
  M04-external-data.md      completion report: every acceptance item with evidence
  sample-records/           real output, for the two modules downstream
ci/external-data.yml        the module's CI workflow
```

## The registry

`config/providers.yaml` is the part worth reading first. Every provider is declared
with its licence, attribution, coverage, quota and credential owner, and the runtime
reconciles that against the environment: a provider marked `ACTIVE` whose key is
missing degrades to `PENDING_CREDENTIAL` rather than failing at call time.

It deliberately only promotes downwards. Supplying a key does **not** activate a
provider — status records an approval decision, not reachability, so turning one on is
an explicit edit to a file that everyone can see in review.

Quotas are measured rather than assumed. The routing provider allows 200 calls a day
and its places endpoint 50, on separate budgets — read from the provider's own
rate-limit headers, because treating them as one pool would let route lookups quietly
exhaust the emergency directory.

## Running it

```bash
cd external-data
uv sync
uv run pytest                 # 645 tests, no network
uv run pytest -m canary       # 28 tests against live providers
uv run ruff check . && uv run mypy app
```

The full stack runs from the team repository's compose file. Without any API key the
service still answers geocoding, weather, all three hazard sources and transit; routing
and places need a free openrouteservice key and report themselves unavailable without
one.

Canaries are excluded from the default run and from CI: a third-party outage should not
turn every pull request red, and a free-tier quota is not something to spend on every
push. They are the only thing that can detect a provider changing shape — a frozen
fixture pins what was true when it was captured and cannot notice drift.

## What is deliberately not here

**Flight data.** The specification forbids serving the test environment of the flight
provider as a real result, and the project has no production credential. The capability
reports itself permanently unavailable, which is the honest end state the plan allows —
not a gap waiting to be filled.

**Transit outside one city.** Bangkok publishes a static GTFS snapshot and no live
realtime feed, which was checked before an alternative was chosen. The registered region
is the New York City subway. A query outside it returns an explicit coverage error
rather than an empty list, because "no trains here" and "we do not cover here" are
different answers.

---

Full detail, including all seventeen known limitations and the acceptance checklist
walked item by item: [`docs/M04-external-data.md`](docs/M04-external-data.md)
