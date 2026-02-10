# Spec Based Properties
A set of behaviours, and global checks that match what the spec says.
These properties must have a reference to the documentation or comments.

# Valid States
Combination of variables values that is considered safe and valid. E.g. Solvent, Supply > Borrows.

# State Transitions
Change from one state to the other, explicitly tests a FSM, e.g. A user cannot self-liquidate.

# Variable Transitions
Change of one Variable, to a value that is reasonable. E.g. Adding supply must always increase the value, (never overflow).

# High Level Properties
Properties that ,must always be correct for the system. E.g. The total must always match the sum of individual user balances.

# Doomsday Checks
A check about something that must never happen.
E.g. as a user I must always be able to repay and close my position as long as I have funds.

Notice how the "always" may have some condition.

# DOS Invariants
A check about some behaviour for which the system must always work.
E.g. Calling Mint must always work.


# Dust Invariants
A set of checks to ensure that operations do no leave remainders or small amounts of assets.
For example a router should always have no funds left when done.
A liquidated account that is closed, should have all their values zeroed out.

# Stateful Unit Tests
Simple before after check, for a specific combination of operations
E.g. I receive the shares returned by the deposit function