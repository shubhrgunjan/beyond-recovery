# Research formulation after baseline characterization

The current system measures controller-specific task continuation. It does not yet learn to preserve recovery options or establish physical viability.

Let `z = (physical state, task state, controller memory)` be the state. Task state includes the current subgoal, elapsed budget and any carried-object/contact commitments. Controller memory matters: identical joint poses do not imply identical responses from a history-conditioned policy. In hardware, `z` would be a belief with state and model uncertainty.

For a fixed task controller and recovery strategy `k`, define continuation as the event that a disturbance is contained, prohibited contacts/damage proxies are avoided, and the original task is resumed or completed within explicitly specified horizons. Standing is an intermediate outcome. A head strike followed by standing can still violate the task's safety specification.

A controller-dependent recovery value is `V_k(z) = P(continuation succeeds | z, disturbance distribution, controller k, horizons)`. Probability requires an explicit distribution. A finite force grid instead provides an empirical response profile; it is not a calibrated safety probability. A bounded worst-case disturbance problem is a different formulation and needs a disturbance budget, timing limits and physically valid transitions.

With multiple selectable recovery strategies, `max_k V_k` assumes the correct strategy can be selected with the available observations. Averaging the per-disturbance oracle best strategy is optimistic: the robot cannot inspect future disturbances before choosing. Define and evaluate the strategy selector explicitly. Counting recovery modes also overstates reserve when they fail under the same disturbances; joint failure dependence matters.

The proposed preservation question is whether choosing task action `a` changes subsequent continuation capability: compare `V(z after a)` against alternatives while controlling task progress, remaining horizon and disturbance exposure. A time-dependent value can increase when a robot reaches a useful support, so recoverability is not necessarily a monotonically depleted scalar resource.

A practical initial algorithm could learn continuation values from state-matched branches, condition on task and controller history, estimate uncertainty on separately held-out seeds/dynamics, then select among nominal task actions subject to an empirically validated reserve constraint. Any claimed lower confidence bound must be validated on its intended distribution, including selection bias from choosing actions using that bound. The current code does not provide such a guarantee.

## Gates before preservation learning

1. Qualify the walking controller's forward, lateral, yaw and stopping responses. Resolve basic route-following stalls and establish nominal multi-stage completion.
2. Establish reachable tasks and sufficient observation horizons. Treat obstacle passage, navigation, task resumption and physical stabilization as separate endpoints.
3. Use state/controller-matched branches. The implemented checkpoint parity test is a useful implementation check, not a general proof.
4. Compare a conventional map planner and command-compatible steering before calling task failures a new recoverability problem.
5. Probe genuine physical recovery across support geometries. Distinguish a wall providing support from a wall trapping the controller.
6. Only then train an action-selection rule that preserves a measured continuation reserve. Compare with random perturbation training, a fixed fallback, task-only control and a recovery-aware baseline without adversarial sampling.

## Scope of the overnight evidence

The box experiment includes a held-out contrast that did not replicate the pilot clearance advantage. The first push grid produced no falls, revealing that task failure alone cannot demonstrate physical unrecoverability. Stronger-impulse probes are an explicitly exploratory follow-up. The current controller is a single unified walking/get-up policy, not a portfolio of independently selectable recovery skills. These results guide experimental design; they are not evidence of algorithmic novelty or hardware safety.


The completed calibration repeat is a strong confound check: the legacy trip study's “regained standing but did not complete” count changed from 26/61 to 1/37 under yaw mapping alone, across the same full 144-condition design (the set of trials that fell also changed). With calibrated yaw at the pre-entry checkpoint, conventional A* changed completion from 11/48 to 44/48 in the 0.75 m corridor and 10/48 to 41/48 in the 0.90 m corridor. Each cell reused eight parent seeds. These findings argue for qualifying ordinary control and planning before building a new preservation method around these failures. Nominal centered-arrival qualification completed all twelve goals in eight development seeds; separate held-out dynamics/tasks remain necessary.
