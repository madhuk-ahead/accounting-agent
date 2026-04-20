# Telemetry onboarding

A concise guide for **Grafana access** and for **adding OpenTelemetry-based telemetry** to production agents, with **Grafana** as the dashboard and observability layer.

---

## Important

**Before validating dashboard changes**, confirm the user has been **granted access** to the team Grafana environment. Without org access, dashboards cannot be viewed or verified.

---

## Overview

This document describes:

1. How to onboard people onto the **telemetry stack** (Grafana + OTLP/metrics).
2. How to update an **existing agent repository** so telemetry appears in Grafana.

The workflow uses **OpenTelemetry** for instrumentation and **Grafana** for dashboards and exploration.

---

## Access and links

### Grafana

| Resource | Link |
|----------|------|
| **Internal dashboard** | [Open dashboard (kurtboden stack)](https://kurtboden.grafana.net/goto/efftyku8wbxtsf?orgId=stacks-1550996) |
| **Invite users** | [Invite members — kurtboden org](https://grafana.com/orgs/kurtboden/members?src=grafananet&cnt=invite-user-top-bar) |

**New users** must be **invited to the Grafana organization** before they can view or validate dashboards.

**Sign-in:** use the stack directly (e.g. `https://kurtboden.grafana.net/login`) or your org’s SSO. Short `/goto/...` links assume you are already authenticated.

---

## Required repositories

Clone the **infrastructure** repo and the **target agent** repo **side by side** so observability docs and examples are easy to open while you implement changes.

| Type | Repository | Purpose |
|------|------------|---------|
| Infra / docs | [**aheadailabs-infra**](https://github.com/kb-ahead/aheadailabs-infra) | Primary observability documentation and dashboard JSON examples. |
| Example agent | [**empty_agent_template_langgraph**](https://github.com/kb-ahead/empty_agent_template_langgraph) | Reference implementation with telemetry wired end-to-end. |

---

## Key reference files (aheadailabs-infra)

Canonical paths in **aheadailabs-infra** (clone the repo to use these paths locally):

| Topic | Path |
|-------|------|
| **Telemetry addition plan** | `aheadailabs-infra/docs/observability/ADDING_TELEMETRY_TO_ANY_AGENT.md` — step-by-step guidance for adding telemetry to a new repo. |
| **Dashboard structure (full)** | `aheadailabs-infra/docs/observability/agent-overview-dashboard.json` — agent tracking dashboard example. |
| **Dashboard structure (simple)** | `aheadailabs-infra/docs/observability/agent-overview-simple-dashboard.json` — simpler JSON you can copy and adapt. |

### Mirror in this repository (accounts_payable_agent)

When working only in this repo, equivalent artifacts may exist under `docs/` (for example `docs/ADDING_TELEMETRY_TO_ANY_AGENT.md`, `docs/agent-overview-dashboard.json`). Treat **aheadailabs-infra** as the source of truth when the two differ.

---

## Recommended workflow

1. **Grant access** — Confirm the user can sign in to the Grafana org and open the team dashboards.
2. **Clone repositories** — Clone **aheadailabs-infra** and the **target agent** repository in parallel.
3. **Read the guidance** — Read `ADDING_TELEMETRY_TO_ANY_AGENT.md` fully **before** code changes.
4. **Study the example** — Use **empty_agent_template_langgraph** as a working reference.
5. **Implement and validate** — Plan, implement, test, and finish telemetry until metrics/traces show up as expected in Grafana (with a coding assistant if helpful).

---

## Suggested prompt for a coding assistant

Use (and customize) the following when asking an assistant to add telemetry to a **target** repository.

```text
Please review the aheadailabs-infra/docs/observability/ADDING_TELEMETRY_TO_ANY_AGENT.md and familiarize yourself with the document completely.

Then please review the [target agent] repo completely. If [target agent] is not filled in or updated, please ask the user what the target agent repo is before continuing.

After you’ve familiarized yourself with each codebase, please write up a temporary step-by-step plan doc to add telemetry to the [target agent] repo.

For each step in the plan, follow this workflow:
1. Investigate the current codebase and environment
2. Write up a temporary plan for the current step
3. Execute on the plan
4. Test if possible
5. Clean up
6. Move to the next step

For reference on how the dashboard looks, you can view:
aheadailabs-infra/docs/observability/agent-overview-dashboard.json

Now, please review the ADDING_TELEMETRY_TO_ANY_AGENT.md file, then review the [target agent] repo, then write up the temporary step-by-step plan doc.

Finally, execute on this step-by-step plan until the telemetry is completely added to the Grafana dashboard.
```

Replace **`[target agent]`** with the concrete repo name or path (for this workspace: **accounts_payable_agent**).

---

## Dashboard notes

- Creating a **new dashboard** in the team Grafana environment is fine when it improves clarity.
- The fastest path is usually to **copy and adapt** an existing JSON export rather than building from scratch.
- Start from:
  - `aheadailabs-infra/docs/observability/agent-overview-dashboard.json`, or  
  - `aheadailabs-infra/docs/observability/agent-overview-simple-dashboard.json`

Ensure the **Prometheus/Mimir** datasource UID in the JSON matches your stack (or use the dashboard’s `ds` variable after import).

---

## Flags and notes

| | |
|--|--|
| **Important** | New users need **Grafana access** before they can validate dashboard changes. |
| **Important** | Keep **aheadailabs-infra** cloned **next to** the target agent repo so assistants and humans can reference observability docs while implementing. |
| **Tip** | Use the **telemetry-enabled example** repo as a working model when updating a new agent. |
| **Tip** | Starting from an **existing dashboard JSON** is usually faster and more consistent than creating one from scratch. |
| **Note** | If the **target repo** has not been specified, the coding assistant should **stop and ask** for it before proceeding. |

---

## Support

For questions, contact **Kurt Boden**.
