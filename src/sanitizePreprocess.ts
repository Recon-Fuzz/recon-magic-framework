const ALLOWED_PREPROCESSES = [
  // Generic
  "yarn install --ignore-scripts",

  // Smilee
  // Parameters 0 to 6
  "forge install && cp test/invariants/utils/scenarios/Parameters_0.sol test/invariants/utils/scenarios/Parameters.sol",
  "forge install && cp test/invariants/utils/scenarios/Parameters_1.sol test/invariants/utils/scenarios/Parameters.sol",
  "forge install && cp test/invariants/utils/scenarios/Parameters_2.sol test/invariants/utils/scenarios/Parameters.sol",
  "forge install && cp test/invariants/utils/scenarios/Parameters_3.sol test/invariants/utils/scenarios/Parameters.sol",
  "forge install && cp test/invariants/utils/scenarios/Parameters_4.sol test/invariants/utils/scenarios/Parameters.sol",
  "forge install && cp test/invariants/utils/scenarios/Parameters_5.sol test/invariants/utils/scenarios/Parameters.sol",
  "forge install && cp test/invariants/utils/scenarios/Parameters_6.sol test/invariants/utils/scenarios/Parameters.sol",

  // Weekly 1 and 2
  "forge install && cp test/invariants/utils/scenarios/Parameters_1_weekly.sol test/invariants/utils/scenarios/Parameters.sol",
  "forge install && cp test/invariants/utils/scenarios/Parameters_2_weekly.sol test/invariants/utils/scenarios/Parameters.sol",

  // Weekly Slippage 1 and 2
  "forge install && cp test/invariants/utils/scenarios/Parameters_1_weekly_slippage.sol test/invariants/utils/scenarios/Parameters.sol",
  "forge install && cp test/invariants/utils/scenarios/Parameters_1_weekly_slippage.sol test/invariants/utils/scenarios/Parameters.sol",
];
// If exact match, we will use it
// Else we return empty

export function sanitizePreprocess(
  preprocess: string,
  isAllowedScript: boolean,
  otherScript?: string
): string {
  // TODO 0XSI
  // Remove that after corn engagement
  if (isAllowedScript && otherScript) {
    return otherScript;
  }
  if (isAllowedScript) {
    return "yarn install";
  }
  if (ALLOWED_PREPROCESSES.includes(preprocess)) {
    return preprocess;
  }

  return "";
}
