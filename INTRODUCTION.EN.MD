# Incident Root Cause Investigation Agent

## Problem

When a microservice goes down, on-call engineers must simultaneously comb through error logs, metrics, deploy history, and source code — then piece together scattered signals into a root cause. This typically takes 20–60 minutes per incident. The hard part isn't lack of data; it's knowing which source to look at and in what order. Under peak-hour pressure, this easily leads to hasty conclusions and fixes applied to the wrong place.

## Target Users

**DevOps / SRE teams** and **on-call engineers** running microservice infrastructure; extended to **Platform** and **Data/Finance** teams investigating anomalies in their own systems.

## How the Agent Works

- **Input:** an incident — error log, alert, or manual description. Received via chat or webhook from Grafana, Prometheus, Sentry, PagerDuty, or OpsGenie.
- **Processing:** the engine generates competing hypotheses, then adaptively selects tools to gather evidence (logs, metrics, deploy history, source code, traces) step by step — eliminating each possibility until the evidence is strong enough to conclude.
- **Output:** a verdict anchored to specific evidence (root cause · confidence level · traceable evidence chain), pushed to Telegram, Gmail, Teams, or Slack.

The agent is deployed on **GreenNode AgentBase** (single-instance container, exposed via a runtime endpoint), receiving webhooks and serving a real-time trace dashboard directly on the platform.

## Value Delivered

In daily operation, the agent cuts triage time from tens of minutes to a few minutes, eliminates repetitive manual lookups, and reduces errors from hasty conclusions — every verdict is grounded in real evidence and every reasoning step can be reviewed.
