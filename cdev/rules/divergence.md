# Divergence pattern prevention rule

Divergence is the state in which a fix for a finding produces the next finding, and findings keep coming however many fixes are stacked. The architect keeps the divergence patterns below out of the design, and the reviewer detects them in the design review.

## Divergence patterns

- **Undecided specification or invariant**: the design does not decide a specification or invariant the implementation depends on (input range, ordering / exclusion guarantees, ownership and lifetime, behavior on error, etc.). This includes places that list options without choosing one, and places left to a judgment at implementation time.
- **Unclosable problem class**: the correctness of the adopted approach depends on enumerating individual cases, and the range to enumerate is unbounded. Handling one counterexample still leaves further counterexamples of the same class constructible without limit (e.g., a race window the architecture inherently cannot remove, regex-based parsing of input that is not constrained).
- **Unadjudicated conflict**: the design does not decide which of two conflicting requirements or quality goals takes priority (e.g., defensive checks versus removing redundancy, performance versus safety).
- **Mismatch with the existing design**: the adopted approach does not fit the existing code's design (ownership, threading model, error-handling convention, etc.), and the design shows no policy for reconciling them.

## architect

- Undecided specification or invariant: decide it in the design and write the decision down. When it cannot be decided from the task and the existing code, state the adopted assumption explicitly as an assumption.
- Unclosable problem class: choose an approach that closes the problem class structurally (e.g., a grammar-based parser, serialization onto a single owner). When no such approach is available, state the scope that is accepted (input constraints, preconditions, tolerated residual risk) and declare everything outside it out of scope.
- Unadjudicated conflict: write down which side takes priority and why.
- Mismatch with the existing design: fit the existing design. When deviating, write down the reason for the deviation and how the two are reconciled at the boundary.

## reviewer

- Raise each place that matches a pattern as a finding of Major or higher, and pick the recommended fix direction from the responses in § architect.
- For an unclosable problem class, do not ask for a response to the individual counterexample. Cite counterexamples only as evidence that the problem class exists.
- When the design states the scope it accepts, do not raise counterexamples outside that scope. Raise the scope itself only when the task cannot be met within it.
