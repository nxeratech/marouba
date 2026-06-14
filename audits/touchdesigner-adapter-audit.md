# Goal 26 TouchDesigner Adapter Audit

Date: 2026-06-14

## API Sources

TouchDesigner exposes network state through embedded Python:

- `COMP.create(opType, name, initialize=True)` creates operators inside a component.
- `OP.par[...]` accesses operator parameters.
- `Par.val` gets/sets constant parameter values; `Par.eval()` reads current working values.
- `OP.inputs`, `OP.outputs`, and connectors expose operator network connections.

TouchDesigner's OSC In DAT exposes received `address` and `args` in the `onReceiveOSC(...)` callback, and DAT methods can send OSC messages.

Sources: Derivative docs for [COMP Class](https://docs.derivative.ca/COMP_Class), [OP Class](https://docs.derivative.ca/OP_Class), [Par Class](https://docs.derivative.ca/Par_Class), and [oscinDAT Class](https://docs.derivative.ca/OscinDAT_Class).

## r1 Boundary

r1 capture requires:

- created operator type/name/path
- full topology connections
- exact touched parameter values
- exact OSC address and typed args for live-control events

OSC alone is not enough to satisfy replay if the operator network topology is missing.

## Declared Failures

- Missing topology is a hard failure.
- Approximate or unreadable parameter values are hard failures.
- Private/encrypted components require explicit `.tox` payload handling or repair.

## Remaining Machine Proof

The committed tests use a fake TouchDesigner runtime so CI can verify the adapter contract without launching TouchDesigner. Full PASS still requires Dave's machine:

- record a real network edit plus parameter session
- confirm r1 topology and exact parameter events
- replay into a fresh TouchDesigner project
- compare network hash
- run 20 cold replays with at least 95 percent success
