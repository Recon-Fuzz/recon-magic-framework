I want to implement a tool that scores coverage based on the depth of the lines that are uncovered in a given function. 

For a given run of fuzzer it will generate an lcov file that looks like the following: 

```lcov
SF:/Users/nelsonpereira/Documents/GitHub/Auditing/Fuzzing/Recon_Fuzzing/Nerite_Fresh/nerite/contracts/src/BorrowerOperations.sol
DA:18,0
DA:34,4
DA:38,0
DA:39,22
DA:42,0
DA:57,22
DA:161,1
DA:162,1
DA:163,1
DA:168,66
DA:170,67
DA:172,65
DA:173,65
DA:174,65
DA:176,76
DA:177,76
DA:178,76
DA:179,76
DA:180,68
DA:182,15
DA:183,16
DA:184,16
DA:185,16
DA:186,16
DA:189,65
DA:194,12
DA:206,1
DA:207,5
DA:209,4
DA:211,12
DA:212,1
DA:213,1
DA:214,1
DA:215,1
DA:216,1
DA:217,1
DA:218,1
DA:219,1
DA:220,1
DA:221,1
DA:222,1
DA:223,1
DA:224,4
DA:228,75
DA:230,45
DA:232,5
DA:235,11
DA:238,1
DA:240,13
DA:242,0
DA:243,0
DA:245,0
DA:248,0
DA:249,0
DA:250,0
DA:251,0
DA:252,0
DA:253,0
DA:254,0
DA:255,0
DA:256,0
DA:257,0
DA:258,0
DA:259,0
DA:260,0
DA:261,0
DA:262,0
DA:263,0
DA:264,0
DA:267,0
DA:270,0
DA:271,0
DA:272,0
DA:273,0
DA:274,0
DA:275,0
DA:276,0
DA:279,0
DA:280,0
DA:281,0
DA:282,0
DA:283,0
DA:284,0
DA:287,0
DA:290,3
DA:304,1
DA:305,4
DA:307,2
DA:310,10
DA:311,11
DA:312,13
DA:314,135
DA:316,12
DA:320,36
DA:321,7
DA:323,6
DA:324,7
DA:327,18
DA:329,71
DA:330,15
DA:331,6
DA:333,20
DA:334,5
DA:337,7
DA:338,15
DA:341,0
DA:342,0
DA:343,0
DA:347,19
DA:348,5
DA:350,15
DA:351,5
DA:356,9
DA:357,10
DA:359,56
DA:362,9
DA:365,45
DA:366,65
DA:368,4
```

which corresponds to the following lines in the `BorrowerOperations` contract:

```solidity
contract BorrowerOperations is LiquityBase, AddRemoveManagers, IBorrowerOperations {
    using SafeERC20 for IERC20;

    // --- Connected contract declarations ---

    IERC20 internal immutable collToken;
    ITroveManager internal troveManager;
    address internal gasPoolAddress;
    ICollSurplusPool internal collSurplusPool;
    IBoldToken internal boldToken;
    // A doubly linked list of Troves, sorted by their collateral ratios
    ISortedTroves internal sortedTroves;
    // Wrapped ETH for liquidation reserve (gas compensation)
    IWETH internal immutable WETH;

    // Critical system collateral ratio. If the system's total collateral ratio (TCR) falls below the CCR, some borrowing operation restrictions are applied
    uint256 public immutable CCR;

    // Shutdown system collateral ratio. If the system's total collateral ratio (TCR) for a given collateral falls below the SCR,
    // the protocol triggers the shutdown of the borrow market and permanently disables all borrowing operations except for closing Troves.
    uint256 public immutable SCR;
    bool public hasBeenShutDown;

    // Minimum collateral ratio for individual troves
    uint256 public immutable MCR;

    /*
    * Mapping from TroveId to individual delegate for interest rate setting.
    *
    * This address then has the ability to update the borrower’s interest rate, but not change its debt or collateral.
    * Useful for instance for cold/hot wallet setups.
    */
    mapping(uint256 => InterestIndividualDelegate) private interestIndividualDelegateOf;

    /*
     * Mapping from TroveId to granted address for interest rate setting (batch manager).
     *
     * Batch managers set the interest rate for every Trove in the batch. The interest rate is the same for all Troves in the batch.
     */
    mapping(uint256 => address) public interestBatchManagerOf;

    // List of registered Interest Batch Managers
    mapping(address => InterestBatchManager) private interestBatchManagers;

    /* --- Variable container structs  ---

    Used to hold, return and assign variables inside a function, in order to avoid the error:
    "CompilerError: Stack too deep". */

    struct OpenTroveVars {
        ITroveManager troveManager;
        uint256 troveId;
        TroveChange change;
        LatestBatchData batch;
    }

    struct LocalVariables_openTrove {
        ITroveManager troveManager;
        IActivePool activePool;
        IBoldToken boldToken;
        uint256 troveId;
        uint256 price;
        uint256 avgInterestRate;
        uint256 entireDebt;
        uint256 ICR;
        uint256 newTCR;
        bool newOracleFailureDetected;
    }

    struct LocalVariables_adjustTrove {
        IActivePool activePool;
        IBoldToken boldToken;
        LatestTroveData trove;
        uint256 price;
        bool isBelowCriticalThreshold;
        uint256 newICR;
        uint256 newDebt;
        uint256 newColl;
        bool newOracleFailureDetected;
    }

    struct LocalVariables_setInterestBatchManager {
        ITroveManager troveManager;
        IActivePool activePool;
        ISortedTroves sortedTroves;
        address oldBatchManager;
        LatestTroveData trove;
        LatestBatchData oldBatch;
        LatestBatchData newBatch;
    }

    struct LocalVariables_removeFromBatch {
        ITroveManager troveManager;
        ISortedTroves sortedTroves;
        address batchManager;
        LatestTroveData trove;
        LatestBatchData batch;
        uint256 newBatchDebt;
    }

    error IsShutDown();
    error TCRNotBelowSCR();
    error ZeroAdjustment();
    error NotOwnerNorInterestManager();
    error TroveInBatch();
    error TroveNotInBatch();
    error InterestNotInRange();
    error BatchInterestRateChangePeriodNotPassed();
    error DelegateInterestRateChangePeriodNotPassed();
    error TroveExists();
    error TroveNotOpen();
    error TroveNotActive();
    error TroveNotZombie();
    error TroveWithZeroDebt();
    error UpfrontFeeTooHigh();
    error ICRBelowMCR();
    error RepaymentNotMatchingCollWithdrawal();
    error TCRBelowCCR();
    error DebtBelowMin();
    error CollWithdrawalTooHigh();
    error NotEnoughBoldBalance();
    error InterestRateTooLow();
    error InterestRateTooHigh();
    error InterestRateNotNew();
    error InvalidInterestBatchManager();
    error BatchManagerExists();
    error BatchManagerNotNew();
    error NewFeeNotLower();
    error CallerNotTroveManager();
    error CallerNotPriceFeed();
    error MinGeMax();
    error AnnualManagementFeeTooHigh();
    error MinInterestRateChangePeriodTooLow();
    error NewOracleFailureDetected();

    event TroveManagerAddressChanged(address _newTroveManagerAddress);
    event GasPoolAddressChanged(address _gasPoolAddress);
    event CollSurplusPoolAddressChanged(address _collSurplusPoolAddress);
    event SortedTrovesAddressChanged(address _sortedTrovesAddress);
    event BoldTokenAddressChanged(address _boldTokenAddress);

    event ShutDown(uint256 _tcr);

    constructor(IAddressesRegistry _addressesRegistry)
        AddRemoveManagers(_addressesRegistry)
        LiquityBase(_addressesRegistry)
    {
        // This makes impossible to open a trove with zero withdrawn Bold
        assert(MIN_DEBT > 0);

        collToken = _addressesRegistry.collToken();

        WETH = _addressesRegistry.WETH();

        CCR = _addressesRegistry.CCR();
        SCR = _addressesRegistry.SCR();
        MCR = _addressesRegistry.MCR();

        troveManager = _addressesRegistry.troveManager();
        gasPoolAddress = _addressesRegistry.gasPoolAddress();
        collSurplusPool = _addressesRegistry.collSurplusPool();
        sortedTroves = _addressesRegistry.sortedTroves();
        boldToken = _addressesRegistry.boldToken();

        emit TroveManagerAddressChanged(address(troveManager));
        emit GasPoolAddressChanged(gasPoolAddress);
        emit CollSurplusPoolAddressChanged(address(collSurplusPool));
        emit SortedTrovesAddressChanged(address(sortedTroves));
        emit BoldTokenAddressChanged(address(boldToken));

        // Allow funds movements between Liquity contracts
        collToken.approve(address(activePool), type(uint256).max);
    }

    // --- Borrower Trove Operations ---

    function openTrove(
        address _owner,
        uint256 _ownerIndex,
        uint256 _collAmount,
        uint256 _boldAmount,
        uint256 _upperHint,
        uint256 _lowerHint,
        uint256 _annualInterestRate,
        uint256 _maxUpfrontFee,
        address _addManager,
        address _removeManager,
        address _receiver
    ) external override returns (uint256) {
        _requireValidAnnualInterestRate(_annualInterestRate);

        OpenTroveVars memory vars;

        vars.troveId = _openTrove(
            _owner,
            _ownerIndex,
            _collAmount,
            _boldAmount,
            _annualInterestRate,
            address(0),
            0,
            0,
            _maxUpfrontFee,
            _addManager,
            _removeManager,
            _receiver,
            vars.change
        );

        // Set the stored Trove properties and mint the NFT
        troveManager.onOpenTrove(_owner, vars.troveId, vars.change, _annualInterestRate);

        sortedTroves.insert(vars.troveId, _annualInterestRate, _upperHint, _lowerHint);

        return vars.troveId;
    }

    function openTroveAndJoinInterestBatchManager(OpenTroveAndJoinInterestBatchManagerParams calldata _params)
        external
        override
        returns (uint256)
    {
        _requireValidInterestBatchManager(_params.interestBatchManager);

        OpenTroveVars memory vars;
        vars.troveManager = troveManager;

        vars.batch = vars.troveManager.getLatestBatchData(_params.interestBatchManager);

        // We set old weighted values here, as it’s only necessary for batches, so we don’t need to pass them to _openTrove func
        vars.change.batchAccruedManagementFee = vars.batch.accruedManagementFee;
        vars.change.oldWeightedRecordedDebt = vars.batch.weightedRecordedDebt;
        vars.change.oldWeightedRecordedBatchManagementFee = vars.batch.weightedRecordedBatchManagementFee;
        vars.troveId = _openTrove(
            _params.owner,
            _params.ownerIndex,
            _params.collAmount,
            _params.boldAmount,
            vars.batch.annualInterestRate,
            _params.interestBatchManager,
            vars.batch.entireDebtWithoutRedistribution,
            vars.batch.annualManagementFee,
            _params.maxUpfrontFee,
            _params.addManager,
            _params.removeManager,
            _params.receiver,
            vars.change
        );

        interestBatchManagerOf[vars.troveId] = _params.interestBatchManager;

        // Set the stored Trove properties and mint the NFT
        vars.troveManager.onOpenTroveAndJoinBatch(
            _params.owner,
            vars.troveId,
            vars.change,
            _params.interestBatchManager,
            vars.batch.entireCollWithoutRedistribution,
            vars.batch.entireDebtWithoutRedistribution
        );

        sortedTroves.insertIntoBatch(
            vars.troveId,
            BatchId.wrap(_params.interestBatchManager),
            vars.batch.annualInterestRate,
            _params.upperHint,
            _params.lowerHint
        );

        return vars.troveId;
    }

    function _openTrove(
        address _owner,
        uint256 _ownerIndex,
        uint256 _collAmount,
        uint256 _boldAmount,
        uint256 _annualInterestRate,
        address _interestBatchManager,
        uint256 _batchEntireDebt,
        uint256 _batchManagementAnnualFee,
        uint256 _maxUpfrontFee,
        address _addManager,
        address _removeManager,
        address _receiver,
        TroveChange memory _change
    ) internal returns (uint256) {
        _requireIsNotShutDown();

        LocalVariables_openTrove memory vars;

        // stack too deep not allowing to reuse troveManager from outer functions
        vars.troveManager = troveManager;
        vars.activePool = activePool;
        vars.boldToken = boldToken;

        require(troveManager.getDebtLimit() >= troveManager.getEntireSystemDebt() + _boldAmount, "BorrowerOperations: Debt limit exceeded.");

        vars.price = _requireOraclesLive();

        // --- Checks ---

        vars.troveId = uint256(keccak256(abi.encode(_owner, _ownerIndex)));
        _requireTroveDoesNotExists(vars.troveManager, vars.troveId);

        _change.collIncrease = _collAmount;
        _change.debtIncrease = _boldAmount;

        // For simplicity, we ignore the fee when calculating the approx. interest rate
        _change.newWeightedRecordedDebt = (_batchEntireDebt + _change.debtIncrease) * _annualInterestRate;

        vars.avgInterestRate = vars.activePool.getNewApproxAvgInterestRateFromTroveChange(_change);
        _change.upfrontFee = _calcUpfrontFee(_change.debtIncrease, vars.avgInterestRate);
        _requireUserAcceptsUpfrontFee(_change.upfrontFee, _maxUpfrontFee);

        vars.entireDebt = _change.debtIncrease + _change.upfrontFee;
        _requireAtLeastMinDebt(vars.entireDebt);

        // Recalculate newWeightedRecordedDebt, now taking into account the upfront fee, and the batch fee if needed
        if (_interestBatchManager == address(0)) {
            _change.newWeightedRecordedDebt = vars.entireDebt * _annualInterestRate;
        } else {
            // old values have been set outside, before calling this function
            _change.newWeightedRecordedDebt = (_batchEntireDebt + vars.entireDebt) * _annualInterestRate;
            _change.newWeightedRecordedBatchManagementFee =
                (_batchEntireDebt + vars.entireDebt) * _batchManagementAnnualFee;
        }

        // ICR is based on the requested Bold amount + upfront fee.
        vars.ICR = LiquityMath._computeCR(_collAmount, vars.entireDebt, vars.price);
        _requireICRisAboveMCR(vars.ICR);

        vars.newTCR = _getNewTCRFromTroveChange(_change, vars.price);
        _requireNewTCRisAboveCCR(vars.newTCR);

        // --- Effects & interactions ---

        // Set add/remove managers
        _setAddManager(vars.troveId, _addManager);
        _setRemoveManagerAndReceiver(vars.troveId, _removeManager, _receiver);

        vars.activePool.mintAggInterestAndAccountForTroveChange(_change, _interestBatchManager);

        // Pull coll tokens from sender and move them to the Active Pool
        _pullCollAndSendToActivePool(vars.activePool, _collAmount);

        // Mint the requested _boldAmount to the borrower and mint the gas comp to the GasPool
        vars.boldToken.mint(msg.sender, _boldAmount);
        WETH.transferFrom(msg.sender, gasPoolAddress, ETH_GAS_COMPENSATION);

        return vars.troveId;
    }
}
```

The `covg-eval` tool will have been run before each call to this tool to identify what the uncovered lines of a given function are.

I want you to implement a tool that scores the uncovered lines using the following point system: 
	- depth of a given line gives it a score value calculated as `1*N` where N is the depth of the line in a given function
	- paths within a branch get `2*N` score
	- paths within a call to an internal/external function get a 3x multiplier with the same 2x multiplier for branches

The sum of the score of uncovered lines should be calculated then appended to the output of the `covg-eval` tool for each uncovered function. 