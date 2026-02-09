# Recon Proprietary Tools

- sol-expand

## sol-expand

sol-expand Contract.sol - Full process (analysis, inlining, constraints)
sol-expand --extract-context Contract.sol - Only generate documentation, skip inlining

sol-expand

What it does: Inlines all internal function calls in Solidity contracts into a single
flattened version, similar to Rust's cargo expand. Useful for analysis and understanding
execution flow.

Installation:
npm install && npm run build && npm link

Usage:
sol-expand --extract-context path/to/Contract.sol

Output:
- output/ - Expanded .sol file with all functions inlined using SSA variable renaming
- output/*.json - Symbolic execution paths and solver programs for each function
- context_output/ - Markdown documentation showing call trees and dependencies

Note: Output files are for analysis only, not for deployment.