---
description: "First Audit Phase 5: Stateless Libraries Partial Formal Verification"
mode: subagent
temperature: 0.1
---

Phase 5: Stateless Libraries Partial Formal Verification

I'm doing a security review, to simplify the code we want to move parts of the code to stateless libraries so we can formally verify those.

Can you identify:
- Stateless parts of code that are good candidate for formal verifications?
- Complex parts of the code that should be manually reviewed and tested?
- Refactoring opportunities that can be used to make parts of the code stateless so we can simplify and test it?

List out the parts and recommendations for fixing them in a simple table.


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
| `Refactoring Opportunity` | yes | Description of code changes you'd make |

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
    "Refactoring Opportunity": "Can formally verify the convertToShares portion of the code by passing assets and shares to the function"                
  }  
```
