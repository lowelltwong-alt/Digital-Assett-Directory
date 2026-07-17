# DAD Remote MCP Contract and Conformance Boundary

This document defines a provider-neutral remote MCP boundary. It is a design
and synthetic conformance contract only. DAD does not deploy or enable a remote
server through this document.

## Required remote properties

- authenticated transport with short-lived, revocable identity;
- explicit tenant and matter isolation before resource lookup;
- correlation IDs, replay detection, bounded request/response sizes, and timeouts;
- resource, tool, and prompt parity with the local contract;
- categorical redaction of paths, credentials, raw conversations, and client data;
- append-only audit evidence without credentials or raw payloads;
- no mutation authority, host configuration writes, or execution authority;
- fail-closed behavior on unknown capability, stale policy, revoked identity,
  expired approval, or unavailable audit sink;
- documented retention, deletion, rollback, and incident response controls.

## Synthetic harness

The conformance harness must exercise a compliant fake transport and hostile
fixtures for missing authentication, cross-tenant access, replayed request IDs,
oversized payloads, stale approvals, path/secret leakage, unknown methods, and
attempted authority escalation. Fixtures contain synthetic identifiers only.

Passing the harness is evidence of contract compatibility, not authorization to
deploy, connect production tenants, or enable remote side effects.
