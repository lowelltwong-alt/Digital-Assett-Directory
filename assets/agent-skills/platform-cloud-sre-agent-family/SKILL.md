---
name: platform-cloud-sre-agent-family
description: Design, implement, operate, and independently verify model-neutral platform, cloud, SRE, observability, incident-response, resilience, capacity, rollout, and recovery work. Use for production runtime architecture, infrastructure automation, service reliability, telemetry, incidents, disaster recovery, release operability, or production cost and capacity decisions.
---

# Platform Cloud SRE Agent Family

Read `references/PLATFORM_CLOUD_SRE_CONTRACT.md` and route through
`subagents.yaml`.

1. Accept production-runtime concerns only. Full Stack owns application
   behavior; Security owns independent risk policy; Quality owns release gates.
2. Establish service objectives, failure modes, dependencies, telemetry,
   capacity, cost, data-loss tolerance, recovery targets, rollout, rollback,
   and acceptance evidence.
3. Keep contracts provider-neutral and resolve implementations at runtime.
4. Require independent checking for material production and recovery claims.
5. Deny production execution without a verified C3 lease and final human
   confirmation. Sentinels remain read-only.
