## Cross-Repo Governance Dependency Map Contract

This repo uses a governance dependency-map pattern only where explicitly
declared by the repo owner or review body.

Agents must:

- read the repo front door before governance-facing work;
- check the upstream governance map and local mirror when watched files change;
- update discovery surfaces and validators together with governance map changes;
- preserve the declared authority boundary;
- treat generated scaffolds as templates, not source authority;
- stop when local notes conflict with upstream governance.

Agents must not:

- let a child repo override upstream governance;
- copy another domain's authority language without adaptation;
- satisfy the map by adding prose without a validator;
- mark governance complete from chat memory;
- remove mirror checks without explicit human approval.

