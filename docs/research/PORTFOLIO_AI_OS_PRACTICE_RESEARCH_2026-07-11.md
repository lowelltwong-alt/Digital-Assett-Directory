# Portfolio AI OS Practice Research — 2026-07-11

Status: public research synthesis and candidate design evidence. Community
reports are dated experience signals, not product authority. This document does
not authorize cross-repo writes, cloud data transfer, or branch cleanup.

## Finding

There is no single mature product that reliably solves creative idea sprawl,
hundreds of repositories, forgotten dirty branches, isolated coding agents,
related-project memory, and humane attention management. Teams solve it by
combining five patterns:

1. a durable project/repository catalog with owner and lifecycle;
2. one executable workstream per branch, worktree, and primary agent task;
3. append-only local activity metadata and a short resume capsule;
4. a small batched attention queue with explicit snooze/pause states;
5. cloud tools as execution or audit adapters, not canonical memory.

## Catalog And Ownership

- [Backstage Software Catalog](https://backstage.io/docs/features/software-catalog/)
  centralizes discovery while keeping component metadata near source. Its
  [descriptor model](https://github.com/backstage/backstage/blob/master/docs/features/software-catalog/descriptor-format.md)
  makes owner, lifecycle, system, and domain explicit.
- GitHub's [durable repository owner program](https://github.blog/security/application-security/how-github-gave-every-repository-a-durable-owner/)
  describes a portfolio of more than 14,000 repositories. It used automatic
  known mappings, a grace period, reversible archive instead of deletion, and a
  low-water-mark abort when bulk counts looked suspicious.
- GitHub's [stale repository action announcement](https://github.blog/open-source/maintainers/announcing-the-stale-repos-action/)
  reinforces report-before-mutation.

DAD implication: every active project needs a stable ID, owner, lifecycle,
canonical repositories, current focus, and next action. Unknown ownership is an
attention item, not permission to archive.

## Worktrees And Agent Sessions

- Native Git supports multiple linked working trees and machine-readable
  inventory through [`git worktree`](https://git-scm.com/docs/git-worktree.html).
  Dirty worktrees resist normal removal, and locks protect intentionally
  long-lived worktrees from pruning.
- OpenAI presents the [Codex app](https://openai.com/index/introducing-the-codex-app/)
  as a multi-agent command center with projects, isolated worktrees, and review
  queues.
- Claude Code's [session model](https://code.claude.com/docs/en/how-claude-code-works)
  ties resumable sessions to directories; its
  [power-user guidance](https://support.claude.com/en/articles/14554000-claude-code-power-user-tips)
  recommends a small number of parallel named worktrees rather than unlimited
  fan-out.
- Cursor [background agents](https://docs.cursor.com/background-agent) use
  isolated branches and remote environments, with explicit network, credential,
  and prompt-injection risks. Cursor's
  [April 2026 update](https://cursor.com/changelog/04-24-26) added worktree
  foregrounding and multi-root workspaces.
- VS Code documents [branch and worktree support](https://code.visualstudio.com/docs/sourcecontrol/branches-worktrees)
  and [multi-root workspaces](https://code.visualstudio.com/docs/editing/workspaces/multi-root-workspaces).
- [Worktrunk](https://github.com/max-sixty/worktrunk) is a useful worktree UX
  reference for branch-addressed creation, listing, hooks, ports, PR state, and
  cleanup. DAD should first wrap native Git and evaluate a dependency later.
- [GitButler's parallel-agent guidance](https://docs.gitbutler.com/ai-agents/parallel-agents)
  distinguishes lightweight virtual branches from true worktrees needed for
  incompatible runtimes, competing attempts, and stronger isolation.
- Incident.io describes [shipping with Claude Code and worktrees](https://incident.io/thedebrief/shipping-with-claude-code-and-worktrees).
  A representative Reddit thread on
  [workspace ownership](https://www.reddit.com/r/AI_Agents/comments/1sqqpvv/how_are_people_handling_local_workspace_ownership/)
  highlights the practical boundary: worktrees isolate tracked files and the
  index, not ports, credentials, caches, external services, or shared databases.

DAD implication: a workstream should bind one intent, branch, worktree, and
primary agent task. Runtime claims such as ports and shared services belong in
the workstream record or lease layer.

## Safe Branch Attention

- GitHub's built-in [stale branch view](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-branches-in-your-repository/viewing-branches-in-your-repository)
  uses a coarse three-month definition and cannot represent "this project is
  active but this related dirty branch has been idle for three days."
- Automatic deletion applies to [merged head branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-the-automatic-deletion-of-branches),
  not arbitrary local dirty work.
- [`git for-each-ref`](https://git-scm.com/docs/git-for-each-ref.html) provides
  branch dates and upstream state; [`git cherry`](https://git-scm.com/docs/git-cherry)
  helps detect patch-equivalent commits; [`git merge-tree`](https://git-scm.com/docs/git-merge-tree)
  can test syntactic merge conflicts without touching the worktree.
- Squash and rebase merges create new commit identities, as GitHub's
  [merge documentation](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges)
  explains. Ancestry alone can therefore produce false cleanup advice.
- GitHub's [`actions/stale`](https://github.com/actions/stale) defaults are
  designed for issue/PR hygiene, not creative personal work; automatic closure
  converts inactivity into loss and pressure.

DAD implication: classify and explain; never auto-delete. A future archive flow
must collect dirt, upstream, PR, ancestry, patch-equivalence, worktree-lock, and
conflict evidence, create a resume capsule, and obtain a human decision.

## Tasks, Ideas, And Relationships

- [GitHub Projects](https://docs.github.com/en/issues/planning-and-tracking-with-projects)
  spans repositories and supports table, board, and roadmap projections plus
  [automation](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/automating-projects-using-actions).
- [Beads](https://github.com/gastownhall/beads) provides agent-oriented graph
  tasks, dependencies, ready-work detection, and relationships such as
  duplicate, supersedes, and relates-to. ThoughtWorks listed it on its
  [2026 technology radar](https://www.thoughtworks.com/radar/tools/beads).
  The Dolt ecosystem's [workflow discussion](https://www.dolthub.com/blog/2026-04-15-common-beads-workflows/)
  and a public [worktree-sync issue](https://github.com/steveyegge/beads/issues/376)
  show the cost of adding another distributed canonical tracker.
- Community discussions about
  [too many project ideas](https://www.reddit.com/r/learnprogramming/comments/1ub503f/i_have_too_many_programming_project_ideas_and/)
  and [forgotten pause context](https://www.reddit.com/r/SideProject/comments/1ttvb2i/i_kept_forgetting_why_i_abandoned_my_side/)
  converge on tiny first-milestone cards and explicit resume context.

DAD implication: borrow ready-task and relation semantics, but keep DAD's
existing SQLite/JSONL/graph control plane. GitHub Projects may be an export or
projection.

## Humane Attention

- An [ICSE 2025 mixed-methods study](https://people.cs.umass.edu/~mendres/papers/GetMeInTheGroove.pdf)
  of 493 professional programmers plus community analysis reports greater
  context-switching difficulty among programmers with ADHD and recurring value
  from clear milestones, task chunking, written communication, breaks,
  coworking/body doubling, routines, timers, and completion reminders.
- Microsoft inclusive design recommends
  [respecting focus](https://inclusive.microsoft.design/articles/respecting-focus):
  alerts should match the required attention level and users need control.
- A [two-week notification batching study](https://www.sciencedirect.com/science/article/abs/pii/S0747563219302596)
  found benefits from three predictable batches per day; hourly batching was
  largely indistinguishable from continuous notifications.
- A representative Reddit thread on
  [productivity systems for ADHD programmers](https://www.reddit.com/r/ADHD_Programmers/comments/1upqdpg/productivity_systems_that_actually_work_for_adhd/)
  warns that elaborate dashboards are often abandoned when maintaining them
  becomes another task.

DAD implication: `Today` is capped at three normal items. Conflicts, failed
checks, or blocked agents may interrupt. Paused-by-choice work is silent until
its review date or a related new idea activates it. Every prompt offers one
clear next action and snooze.

## Local-First Boundary

The [local-first software essay](https://www.inkandswitch.com/essay/local-first/)
centers ownership, offline use, longevity, privacy, and user control. DAD's
local data root, append-only metadata, SQLite, journal, and bounded review
packets match this architecture.

Codex should be the primary interactive execution surface. Cursor should receive
bounded low-level work packets. Fable should receive compact sanitized
architecture, design, checker-dispute, and premortem packets. None should become
the only holder of project state, and raw conversations should not become the
portfolio database.

## Recommended Success Measures

- Every active project has lifecycle, owner, and next action.
- Every active workstream maps to one branch, worktree, and primary agent task.
- Resume-to-useful-action takes less than two minutes.
- Normal daily attention is capped at three items and respects snooze/pause.
- No destructive cleanup occurs without evidence plus human confirmation.
- Related-work suggestions record accept, defer, reject, and false-positive
  outcomes so low-precision signals decay.
