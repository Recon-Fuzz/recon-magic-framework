## Clamping Handlers: Rules to Follow

---
**⚠️ CRITICAL REQUIREMENT ⚠️**

**ALL modulo arithmetic operations used for clamping MUST include `+ 1` after the modulo operator.**

This is **MANDATORY** and **NON-NEGOTIABLE**. The `+ 1` allows the maximum value to be passed in during fuzzing.

❌ **WRONG**: `amount %= balance;`
✅ **CORRECT**: `amount %= (balance + 1);`

**Failure to include `+ 1` will result in incomplete fuzzing coverage.**

---

### Using The Meaningful Values
The `meaningful-values.json` file will outline values to clamp each function by using the following format: 
```json
    { 
        {
            "target_function": "function_name",
            "type": "max" | "exact",
            "value": "type and name of the value to be replaced",
            "access": "function defining meaningful value" | "state variable in setup which stores meaningful value"
        }
    }
```

Where:
- **"target_function"**: specifies the function in which this value should be used for clamping
- **"type"**: specifies whether the value should be used to constrain the existing input by the "value" using modulo arithmetic (when set to "max") or the existing input should be set explicitly to the value using the "value" (when set to "exact")
- **"value"**: specifies the input parameter in the handler function to be replaced
- **"access"**: the way to access the value to use for clamping

### Implementation Rules

<Hard Limits>
**These rules are MANDATORY and MUST be followed for all clamped handlers:**

1. **Naming Convention**: Clamped handlers MUST always end with the `_clamped` suffix.

2. **Single State-Changing Call**: Clamped handlers should NEVER contain more than one state-changing function call. The ONLY state-changing call should be to the corresponding unclamped handler function.

3. **Call Hierarchy**: Clamped handlers MUST call their unclamped handler counterpart. They should NEVER call the contract directly or call other state-changing functions.

**IMPORTANT: All state-changing function calls should be made to handlers (unclamped handlers), NOT directly to contracts or other functions within clamped handlers**.
</Hard Limits>

**Bad Example**:
```solidity
contract TargetFunctions {
    function gateway_send_clamped(uint256 amount) public {
        amount %= vault.totalSupply(); // WRONG: Missing + 1

        // NOTE: clamped handler should call unclamped handler
        gateway.send(amount);
    }

    function gateway_send(uint256 amount) public { 
        gateway.send(amount);
    }
}
```

**Good Example**:
```solidity
contract TargetFunctions {
    function gateway_send_clamped(uint256 amount) public {
        amount %= (vault.totalSupply() + 1); // CRITICAL: Must include + 1

        // NOTE: clamped handler calls the unclamped handler
        gateway_send(amount);
    }

    function gateway_send(uint256 amount) public { 
        gateway.send(amount);
    }
}
```

2. When clamping amounts use a modulo operator to constrain the minimum and maximum values to values that won't revert.

**CRITICAL**: Always add `+ 1` to modulo values to allow the maximum value to be passed in. This is MANDATORY for all clamping operations.

**Example**:
```solidity
contract TargetFunctions {
    function vault_deposit_clamped(uint256 amount) public {
        amount %= (MockERC20(_getAsset()).balanceOf(_getActor()) + 1); // NOTE: adding + 1 allows depositing the full user balance

        vault_deposit(amount);
    }

    function vault_deposit(uint256 amount) public { 
        vault.deposit(amount);
    }
}
```

3. When clamping handlers with values that are explicitly provided by the `meaningful-values.json` file to replace input parameters to a function, the arguments to the handler function should be removed. 

**Example**: 
```solidity
contract TargetFunctions {
    // NOTE: recipient parameter is explicitly removed from this handler because clamping doesn't rely on it
    function vault_transfer_clamped(uint256 amount) public {
        vault_transfer(_getActor(), amount);
    }

    function vault_transfer(address recipient,uint256 amount) public { 
        vault.transfer(recipient, amount);
    }
}
```

NOTE: all other unused handler function arguments should also be removed.

4. Only add clamped handlers if the search space for the given inputs to a handler is too large and makes it unlikely that a given line will be reached without a clamped version.

If you believe the code will achieve line coverage as is with a longer fuzzing run to explore more of the state space, do not add a clamped handler.

5. **IMPORTANT**: The values stored in the `meaningful-values.json` file should be the only special values used for constraining function inputs in clamped handlers.

**BAD EXAMPLE**:
The following handler only tries one value instead of using a range

```solidity
    // NOTE: bad to use hardcoded values for minDuration
    function stblMfs_deposit_minDuration(uint256 stblAmt, uint256 usstAmt) public asActor {
        uint256 minDuration = 148800; // 1 day in blocks
        stblMfs_deposit_pureSTBL(stblAmt, usstAmt, minDuration);
    }

    // NOTE: bad to use hardcoded values for mediumDuration
    function stblMfs_deposit_mediumDuration(uint256 stblAmt, uint256 usstAmt) public asActor {
        uint256 mediumDuration = 2232000; // ~15 days in blocks
        stblMfs.deposit(stblAmt, usstAmt, mediumDuration);
    }

    function stblMfs_deposit_pureSTBL(uint256 stblAmt, uint256 duration) public asActor {
        stblMfs.deposit(stblAmt, 0, duration);
    }
```

**GOOD EXAMPLE**:
The handler clamps the amount to reasonable values using values from the `meaningful-values.json` file
```solidity
    uint256 constant MAX_DURATION = 62899200; // 2 years in seconds.
    
    /// NOTE: Proper naming convention with postfix
    function stblMfs_deposit_clamped(uint256 stblAmt, uint256 usstAmt, uint256 duration) public {
        /// NOTE: Clamp all inputs to reasonable bounds that reduce reverts, under clamping always preferred
        uint256 stblAmt = stblAmt % (stableToken.balanceOf(_getActor()) + 1); // CRITICAL: + 1 is mandatory
        uint256 usstAmt = usstAmt % (usstToken.balanceOf(_getActor()) + 1); // CRITICAL: + 1 is mandatory
        uint256 duration = duration % (MAX_DURATION + 1); // CRITICAL: + 1 is mandatory

        stblMfs_deposit(stblAmt, usstAmt, mediumDuration);
    }
    

    function stblMfs_deposit(uint256 stblAmt, uint256 usstAmt, uint256 duration) public {
        // Hardcode usstAmt to 0 as means to achieve a shortcut, rest is clamped by the clamping conventions
        stblMfs.deposit(stblAmt, usstAmt, duration);
    }
```

6. All addresses used as recipients or initiators of transactions should be clamped to actors tracked within the `ActorManager`. 

**Bad Example**: 
```solidity
contract TargetFunctions {
    function vault_transfer_clamped(uint256 amount) public {
        // NOTE: recipient is a random address so this makes it difficult to define properties for
        address recipient = address(0xbeef);
        vault_transfer(recipient, amount);
    }

    function vault_transfer(address recipient,uint256 amount) public { 
        vault.transfer(recipient, amount);
    }
}
```

**Good Example**: 
```solidity
contract TargetFunctions {
    function vault_transfer_clamped(uint256 amount) public {
        // NOTE: recipient is an actor so can more easily define properties for all actors
        vault_transfer(_getActor(), amount);
    }

    function vault_transfer(address recipient,uint256 amount) public { 
        vault.transfer(recipient, amount);
    }
}
```

7. **NEVER** include require statements or early returns as a form of clamping. Using these to clamp results in the fuzzer reaching a path it would have already reached otherwise so is non-beneficial. 

Functions that return early or revert will be pruned from a call trace during shrinking so implementing this manually adds unnecessary complexity.

**Bad Example**:
```solidity
    function flashLoan_clamped(address token, uint256 assets, bytes memory data) public asActor {
        // Use loan token
        token = address(loanToken);

        // Check available balance in morpho
        uint256 available = loanToken.balanceOf(address(vault));

        // NOTE: this return is useless because the call to flashloan would revert for 0 amounts anyways
        if (available == 0) return;

        // Clamp to available amount
        assets = assets % (available + 1); // CRITICAL: + 1 is mandatory

        vault_flashLoan(token, assets, data);
    }
```

**Good Example**:
```solidity
    function flashLoan_clamped(address token, uint256 assets, bytes memory data) public asActor {
        // Use loan token
        token = address(loanToken);

        // Check available balance in morpho
        uint256 available = loanToken.balanceOf(address(vault));

        // NOTE: If available == 0 this reverts anyways so no need to return early
        assets = assets % (available + 1); // CRITICAL: + 1 is mandatory

        vault_flashLoan(token, assets, data);
    }
```

8. **NEVER** apply clamping that prevents reverts within clamping itsef.

**Bad Example**:
```solidity
    contract VaultTargets {
        function vault_deposit_clamped(uint256 amount) public {
            uint256 balance = MockERC20(_getAsset()).balanceOf(_getActor())
            // NOTE: this is bad practice, the function should be allowed to revert instead
            if(balance > 0) {
                amount %= (balance + 1);
            } else {
                amount = 0
            }

            vault_deposit(_getActor(), amount); // NOTE: calls unclamped handler
        }

        function vault_deposit(address depositor, uint256 amount) public {
            vault.deposit(depositor, amount);
        }
    }
```

**Good Example**:
```solidity
    contract VaultTargets {
        function vault_deposit_clamped(uint256 amount) public {
            // NOTE: the function can revert here if the actor has a 0 balance but it doesn't affect the fuzzing
            amount %= (MockERC20(_getAsset()).balanceOf(_getActor()) + 1); // CRITICAL: + 1 is mandatory

            vault_deposit(_getActor(), amount); // NOTE: calls unclamped handler
        }

        function vault_deposit(address depositor, uint256 amount) public {
            vault.deposit(depositor, amount);
        }
    }
```

9. **Never** use conditional logic to selectively apply clamping. Clamping should either allow multiple possible options or constrain to a narrow set.

**Bad Example**:
```solidity
    contract VaultTargets {
        function vault_deposit_clamped(uint256 amount) public {
            uint256 balance = MockERC20(_getAsset()).balanceOf(_getActor())
            // NOTE: this is bad practice, the function should be allowed to revert instead
            if(balance > 0) {
                amount %= (balance + 1);
            } else {
                amount = 0
            }

            vault_deposit(_getActor(), amount); // NOTE: calls unclamped handler
        }

        function vault_deposit(address depositor, uint256 amount) public {
            vault.deposit(depositor, amount);
        }
    }
```

**Good Example**:
```solidity
    contract VaultTargets {
        function vault_deposit_clamped(uint256 amount) public {
            // NOTE: this can allow the case where amount is 0 without explicitly needing to define a conditional statement to allow it
            amount %= (MockERC20(_getAsset()).balanceOf(_getActor()) + 1); // CRITICAL: + 1 is mandatory

            vault_deposit(_getActor(), amount); // NOTE: calls unclamped handler
        }

        function vault_deposit(address depositor, uint256 amount) public {
            vault.deposit(depositor, amount);
        }
    }
```

10. For a state variable that effects a conditional branch in a function and doesn't have values stored in the `meaningful-values.json` file and is unlikely for the fuzzer to reach, pass in values that explicitly modify the state variable using its upper and lower boundaries as a separate clamped handler. 

**Example**
The `if` branch in the following function is only reached if the collateral decreases to 0 which requires that `seizedAssets == position.collateral`:
```solidity
    // 
    function liquidate(
        address borrower,
        uint256 seizedAssets,
        uint256 repaidShares
    ) external returns (uint256, uint256) {
    ...

    position.collateral -= seizedAssets.toUint128();

    ...
    if (position.collateral == 0) {
        ...
    }
    ...
    }
```

This is difficult for the fuzzer to reach because the values aren't implicitly stored in its dictionary, so clamping should be applied as follows: 

```solidity
function vault_liquidate_full_clamped() {
    Position memory position = vault.position(_getActor); 
    seizedAssets = position.collateral;
    repaidShares = position.shares;

    vault_liquidate(_getActor(), seizedAssets, repaidShares);
}

function vault_liquidate(address borrower uint256 seizedAssets, uint256 repaidShares) {
    vault.liquidate(borrower, seizedAssets, repaidShares);
}
```

NOTE: for these types of special clamped handlers you **MUST ALWAYS** indicate the specific action being tested (e.g. `vault_liquidate_full_clamped` in the above example).

11. For specific values that hold significance in the system (e.g. positions, markets, etc.) but which are necessary parameters for other handler functions to reach coverage, these should be stored as state variables that can be used for clamping directly. 

**Example**
The `marketManager` allows creating and depositing into markets: 

```solidity
contract Setup {
    MarketManager marketManager;
    MarketParams defaultMarketParams;

    function setUp() internal {
        ... 

        defaultMarketParams = MarketParams({
            loanToken: address(loanToken),
            collateralToken: address(collateralToken),
            oracle: address(oracle),
            ltvRatio: 0.8e18
        });

        marketManager.createMarket(defaultMarketParams);
    }
}
```

The handler functions then require valid market parameters to call any function on a market. The `defaultMarketParams` is therefore used by clamped handlers to ensure that they always call functions with an actually created market: 

```solidity
contract TargetFunctions {
    function market_supply_clamped(uint256 amount) {
        market_supply(defaultMarketParams, amount);
    }

    function market_supply(MarketParams memory marketParams, uint256 amount) {
        market.supply(marketParams, amount);
    }
}
```

This value should then be updated any time a new market is created: 

```solidity
contract TargetFunctions {
    function market_createMarket(uint256 ltvRatio) asActor {
        // Resets defaultMarketParams with new market
        defaultMarketParams = MarketParams({
            loanToken: address(loanToken),
            collateralToken: address(collateralToken),
            oracle: address(oracle),
            ltvRatio: ltvRatio
        });

        market.createMarket(defaultMarketParams);
    }
}
```

So that clamped handler functions using the `defaultMarketParams` are now using the new value.

12. As stated in the Hard Limits above, clamped handlers MUST contain exactly ONE state-changing function call (to the unclamped handler). This rule is critical for maintaining proper handler architecture.

**Bad Example - Multiple State-Changing Calls**:
```solidity
function market_borrow_clamped(uint256 supplyAmount, uint256 borrowAmount) public {
    // ❌ WRONG: This clamped handler makes TWO state-changing calls
    // NOTE: call to market_supply should NOT be included here
    market_supply(supplyAmount);

    borrowAmount %= (market.maxBorrow(_getActor()) + 1); // CRITICAL: + 1 is mandatory
    market_borrow(borrowAmount);
}
```

**Good Example - Single State-Changing Call**:
```solidity
function market_borrow_clamped(uint256 borrowAmount) public {
    // ✅ CORRECT: Only ONE state-changing call (to unclamped handler)
    borrowAmount %= (market.maxBorrow(_getActor()) + 1); // CRITICAL: + 1 is mandatory
    market_borrow(borrowAmount);
}
```

**Note**: If you need multiple prerequisite calls (like `market_supply` followed by `market_borrow`), create a **shortcut handler** instead. Shortcut handlers can call multiple clamped handlers as prerequisites. See `coverage-phase-2.md` for details on shortcut handlers.
 