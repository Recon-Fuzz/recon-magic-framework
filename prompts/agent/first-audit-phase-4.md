---
description: "First Audit Phase 4: Code repetition analysis"
mode: subagent
temperature: 0.1
---

# Phase 4: Code repetition analysis

I'm doing a security review, to simplify the code we want to get rid of duplicated code, and identify opportunities for using functions.

Please go in `src`, review all code and identify duplicated code that can be simplified by introducing a function.

Write a doc: `refactoring.md`. Write the functions you want to use in simple ```solidity` blocks.

Then create a table in the Code Reference Format to explain which parts of the code will be replaced by which function.

## Code Reference Format

JSON object pointing to a location in source code.

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `file` | yes | Path relative to project root |
| `line_start` | yes | Line number (1-indexed) |
| `line_end` | yes | Line number (1-indexed) |
| `col_start` | yes | Line number (1-indexed) |
| `col_end` | yes | Line number (1-indexed) |
| `symbol` | yes | Name of the element |
| `type` | yes | `function`, `literal`, `variable`, `class`, `method`, `parameter` |
| `functionName` | yes | name of the function you want to use for code replacement |

### Examples

```json
 {                                                                                                                                                      
    "file": "src/Contract.sol",                                                                                                                                   
    "line_start": 42,                                                                                                                                             
    "line_end": 58,                                                                                                                                               
    "col_start": 5,                                                                                                                                               
    "col_end": 6,                                                                                                                                                 
    "symbol": "withdraw",                                                                                                                                         
    "type": "function",                                                                                                                                           
    "functionName": "withdraw"                                                                                                                                    
  }   
```