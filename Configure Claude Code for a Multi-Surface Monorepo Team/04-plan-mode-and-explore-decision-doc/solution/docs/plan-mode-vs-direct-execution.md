# Plan mode vs. direct execution — team decision guide

Choosing between Claude Code's **plan mode** (investigate and propose before changing anything) and **direct execution** (change code immediately) is the single biggest leverage point in how the team uses the harness day-to-day. The wrong mode at either extreme costs us: plan mode for trivial fixes is friction; direct execution for architectural changes burns context and produces rework.

> *Anchor talk: Knight-Webb, "SWE Is Becoming Plan and Review." The framing for this decision: pick the mode by the shape of the work, not its size.*

This doc walks four concrete decisions against our codebase: one plan-mode example, one direct-execution example, one Explore-subagent example, and one combined-workflow example.

---

## 1. Plan-mode example — extracting a shared `useCart` hook

**Task:** three React components currently each duplicate the "load the cart, compute the total, expose a setter" pattern: `src/components/Cart/Cart.tsx`, `src/components/Checkout/Checkout.tsx`, and `src/components/MiniCart/MiniCart.tsx`. We want to extract a shared `useCart(userId)` hook into a new file under src/hooks/ and update all three call sites.

**Why plan mode:** this is exactly the shape the plan-mode criteria call out — *large-scale changes, multiple valid approaches, architectural decisions, multi-file modifications*. Three components change. The hook's API has at least two reasonable shapes: should it return `{ items, total, setQuantity }` (a flat tuple) or `{ items, derived: { total, count }, actions: { setQuantity } }` (a grouped object)? Should the hook own the loading state, or should each call site? Should `MiniCart` skip the setter to avoid pulling in unused dependencies?

Plan mode lets us answer those questions before touching code. The agent reads all three components, proposes one hook shape with justification, and the team decides yes/no — no wasted edits.

**The Knight-Webb principle:** plan mode here also **prevents costly rework**. If we direct-executed and the chosen API didn't suit `MiniCart`'s lighter needs, we'd refactor the hook a second time and lose the change history's clarity.

---

## 2. Direct-execution example — adding a `min: 0` validation to the order quantity

**Task:** clamp the request body so a malicious or buggy client cannot submit `quantity: -3` and decrement inventory. One function: `handle` in `src/api/orders/handler.ts`. The fix lives entirely inside that function (or its schema in `src/api/_schemas/orders.ts` — a single line either way).

**Why direct execution:** the direct-execution criterion calls out *simple, well-scoped changes (e.g., adding a single validation check to one function)* as the canonical case. There is one function to change, one validation rule to add, no architectural decision, no API surface debate. Plan mode here would slow the change without adding signal.

**The bar for "direct execution":** I (the author) already know what the diff looks like before invoking Claude. If you can describe the change in one sentence and predict the patch, skip planning.

---

## 3. Explore-subagent example — "find every place we call `processRefund`"

**Task:** Finance asks where in the codebase we initiate a refund, ahead of a payment-provider migration. We need a complete inventory.

**Why the Explore subagent:** running `grep -R processRefund src/` in the main session works, but the *exploration around the answer* is verbose: every file we open to confirm the call site is real, the surrounding context to understand whether the call is conditional, the test files that exercise each path. That verbose discovery has no value once the inventory is in hand — but it sits in the main session's context window, crowding out the work we actually want to do next.

Delegating to the `Explore` subagent isolates the verbose discovery output and returns a structured summary. Two habits make the delegation work: start broad, then pinpoint; and give the subagent research goals and quality criteria rather than procedural steps. In our codebase, the answer comes back as a short list — `src/api/orders/refund.ts` and `src/api/billing/issue.ts` both import `processRefund` from `src/services/payment.ts` — without the dozens of `git grep` hits or file-open events that produced it.

**Scratchpad pattern:** the Explore subagent should write its working notes to a scratchpad file — for this task, something like tmp/refund-callsites.md listing every call site, its conditions, and the test files that cover it. The scratchpad survives the main session's context window, so when Finance asks a follow-up question two days later we can read the scratchpad instead of re-running the exploration.

---

## 4. Combined workflow — plan mode for investigation, then direct execution

**Task:** rename `ordersRepo.findById` → `ordersRepo.getById` to align with the team's naming convention (`get*` for single-row reads, `find*` for multi-row queries). The function lives in `src/db/orders.ts`.

**Why combined:** *combining plan mode for investigation with direct execution for implementation* is a distinct skill, not a compromise between the two. The investigation question is "where is `findById` called and are any of them dynamic (e.g. constructed string lookups that grep would miss)?" — that's a discovery task best handled in plan mode so we don't start editing files we haven't yet identified. Once the call-site inventory is in hand, the rename itself is mechanical and well-scoped: direct execution from there.

**The flow:**

1. **Plan mode:** Claude reads `src/db/orders.ts`, greps the repo for `findById`, follows the call chain, confirms there are no dynamic invocations, and proposes the rename plus the call-site updates. Verdict: 4 files touched, all static references, low risk.
2. **Approve the plan.** No surprises surfaced.
3. **Direct execution:** Claude applies the rename across the 4 files, runs the test suite, and reports green.

The savings: we did not direct-execute without knowing the call-site list (would have missed any dynamic refs and broken prod), and we did not stay in plan mode for the mechanical edit (would have added friction with no value).

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
