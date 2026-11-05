# Plan mode vs. direct execution — team decision guide

Choosing between Claude Code's **plan mode** (investigate and propose before changing anything) and **direct execution** (change code immediately) is the single biggest leverage point in how the team uses the harness day-to-day. The wrong mode at either extreme costs us: plan mode for trivial fixes is friction; direct execution for architectural changes burns context and produces rework.

<!--
TODO: Replace this comment with a blockquote citation for the Knight-Webb
      "SWE Is Becoming Plan and Review" anchor talk that frames this decision,
      for example:

        > Anchor talk: Knight-Webb, "SWE Is Becoming Plan and Review."

      The validator checks that the citation names the speaker (Knight-Webb), the
      talk title, and the words "anchor talk".
-->

This doc walks four concrete decisions against our codebase: one plan-mode example, one direct-execution example, one Explore-subagent example, and one combined-workflow example.

---

## 1. Plan-mode example

<!--
TODO: Write a plan-mode worked example against this codebase. Requirements:

  - Touch AT LEAST THREE real files in src/. A natural candidate is extracting a
    shared `useCart(userId)` hook into src/hooks/ from three components that
    currently duplicate the pattern:
      - src/components/Cart/Cart.tsx
      - src/components/Checkout/Checkout.tsx
      - src/components/MiniCart/MiniCart.tsx
    (All three exist in this repo — confirm before referencing.)

  - State the reasoning that uses the plan-mode criteria: large-scale changes,
    multiple valid approaches, architectural decisions, multi-file modifications.

  - EXPLICITLY cite "prevent costly rework" (or equivalent phrasing) as the value
    of planning before committing. This is the Knight-Webb principle.

  - File-path rule: if you mention a file in backticks, it must actually exist
    in the repo. For hypothetical/future files (e.g. the extraction target that
    doesn't exist yet), use PROSE form (no backticks) instead. Otherwise the
    validator will flag a dangling reference.
-->

---

## 2. Direct-execution example

<!--
TODO: Write a direct-execution worked example. Requirements:

  - Target a single, well-scoped change in ONE function. A natural candidate is
    adding a `min: 0` validation to the quantity field in the orders schema or
    handler:
      - src/api/orders/handler.ts (or src/api/_schemas/orders.ts)
    Confirm the file exists before referencing it.

  - State the reasoning that uses the direct-execution criterion: simple,
    well-scoped changes.

  - Convey the bar for "direct execution": you (the author) already know what
    the diff looks like before invoking Claude. If you can describe the change
    in one sentence and predict the patch, skip planning.
-->

---

## 3. Explore-subagent example

<!--
TODO: Write an Explore-subagent worked example. Requirements:

  - A real discovery task in this codebase. A natural candidate: "find every
    place we call `processRefund`" — the answer touches src/api/orders/refund.ts,
    src/api/billing/issue.ts, and src/services/payment.ts. Confirm the files
    and the call sites exist before referencing them.

  - State the reasoning that uses the Explore criterion: isolating verbose
    discovery output and returning summaries to preserve main conversation context.

  - REFERENCE THE SCRATCHPAD PATTERN. The Explore sub-agent
    should write its working notes to a scratchpad file (e.g. tmp/refund-callsites.md)
    so the inventory survives the main session's context window. Name it
    explicitly — "scratchpad pattern" should appear in your text.
-->

---

## 4. Combined workflow — plan mode for investigation, then direct execution

<!--
TODO: Write a combined-workflow worked example. This is the most subtle of the
      four — developers often see plan mode and direct execution as binary. The
      combined workflow uses plan mode for the DISCOVERY part (where you don't
      yet know the call-site list) and direct execution for the MECHANICAL part
      (where the rename is keystrokes once the list is known).

      Requirements:

      - A real change in this codebase where investigation should precede edits.
        A natural anchor: renaming `ordersRepo.findById` → `ordersRepo.getById`
        in src/db/orders.ts to align with a team naming convention
        (get* for single-row reads, find* for multi-row). The investigation
        question is "where is findById called, and are any of them dynamic
        (constructed string lookups grep would miss)?" — plan mode handles that.
        Once the call-site list is in hand, the rename itself is mechanical:
        direct execution.

      - State the reasoning: "Combining plan mode for investigation with
        direct execution for implementation."

      - Show the flow as a 3-step sequence: (1) plan mode investigates and
        proposes; (2) you approve the plan; (3) direct execution applies the
        rename and runs tests.
-->

---

## Quick reference

| Situation | Mode |
|-----------|------|
| Single function, fix is obvious, you can predict the diff | Direct execution |
| Multi-file refactor, API shape is debatable | Plan mode |
| Discovery / inventory across the codebase, you'll throw away the intermediate steps | Explore subagent |
| Investigation-then-mechanical-change | Plan mode → direct execution |
| Architectural decision (which database, which queue) | Plan mode, possibly with a fork to compare options |

When in doubt: plan mode is recoverable (you can switch to execution), but direct execution on a complex change is not. Default to plan when uncertain.
