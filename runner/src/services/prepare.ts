import { Job } from "@prisma/client";
import { JsonObject } from "@prisma/client/runtime/library";
import { getBlockTimestamp, getLatestBlockNumber } from "./chainInfo";

interface FindReplace {
  target: string; // The substring to search for, replacement starts at the start of this string
  replacement: string; // The string to added into the contract
  endOfTargetMarker: string; // Substring that marks the end of the replacement
  targetContract?: string; // Optional. The specific .sol file to search and replace
}

const ALCHEMY_API_KEY = "EN8-iA0eGN4NmGkKaMt_cF4MYWJAq0Vi";

// This is used to craft a generic find and replace bash command which can be called with `exec`
// Likely used for dynamic replacement
// target: the string to search for
// endOfTargetMarker: this is the `sed` command fragment that tells the command to which string to search up to
// replacement: the string to replace it with
export function findAndReplace(
  target: string,
  endOfTargetMarker: string,
  replacement: string,
  contract?: string
): string {
  /**************************************
   * Run local using yarn with a MAC
    const grepPattern = target.replace(/"/g, '\\"');
    const sedPattern = target.replace(/"/g, '\\"');
    if (!replacement.endsWith(";")) {
      replacement = replacement + ";";
    }
    endOfTargetMarker = endOfTargetMarker === "[^;]**" ? "[^;]*" : endOfTargetMarker;

    return `
  # Test if file exists first
  FILE=\$(find recon -type f -name "${contractTarget}" -exec grep -l "${grepPattern}" {} \\; | head -n 1)
  # Debug output
  echo "File found----> : $FILE"
  echo "Grep pattern: ${grepPattern}"
  echo "Sed pattern: ${sedPattern}"
  if [ -f "$FILE" ]; then
    sed -i '' "s#${sedPattern}${endOfTargetMarker};#${replacement}#g" "$FILE"
    echo "Modified $FILE:"
    cat "$FILE"
  else
    echo "File not found" >&2
    exit 1
  fi`.trim();
   *
   */
  if (!replacement.endsWith(";")) {
    replacement = replacement + ";";
  }
  endOfTargetMarker =
    endOfTargetMarker === "[^;]**" ? "[^;]*" : endOfTargetMarker;
  console.log("replacement: ", replacement);
  console.log(
    "endOfTargetMarker: ",
    endOfTargetMarker,
    "=> ",
    "Target: ",
    target
  );
  const contractTarget = contract ? contract : "*.sol";
  // Escape target for grep and sed
  // Create basic patterns without complex escaping
  // const grepPattern = target.replace(/"/g, '\\"');
  // const sedPattern = target.replace(/"/g, '\\"');
  // const replacementPattern = replacement.replace(/"/g, '\\"');

  let grepPattern: string;
  let sedPattern: string;
  let replacementPattern: string;

  // VM Commands (roll, warp)
  if (target.startsWith("vm.")) {
    // Base command (vm.roll or vm.warp)
    grepPattern = target;

    // Match full command with any number between parentheses
    sedPattern = `${target}\\([0-9]*\\)`;

    // Strip semicolon from replacement if present
    replacementPattern = replacement;
    if (!replacementPattern.endsWith(';')) {
      replacementPattern += ';';
    }
    console.log(`VM Command detected:
    Base command: ${grepPattern}
    Pattern to replace: ${sedPattern}
    Replacement: ${replacementPattern}`);

  } else {
    grepPattern = target.replace(/"/g, '\\"');
    sedPattern = target.replace(/"/g, '\\"');
    replacementPattern = replacement.replace(/"/g, '\\"');
  }

  return `
  # Find file containing pattern
  FILE=$(find recon -type f -name "${contractTarget}" -exec grep -l "${grepPattern}" {} \\; | head -n1)

  if [ -f "$FILE" ]; then
    echo "Processing: $FILE"

    # Show original content
    echo "Before:"
    grep -F "${grepPattern}" "$FILE" || true

    # Create backup and perform replacement
    cp "$FILE" "$FILE.bak"
    sed "s#${sedPattern}${endOfTargetMarker};#${replacementPattern}#g" "$FILE.bak" > "$FILE"
    rm "$FILE.bak"

    # Show result and verify
    echo "After:"
    if [ "${target}" = "vm.roll" ] || [ "${target}" = "vm.warp" ]; then
      grep "${target}.*;" "$FILE" || echo "Pattern not found after replacement"
    else
      grep -F "${replacementPattern}" "$FILE" || echo "Pattern not found after replacement"
    fi
  else
    echo "No file found with pattern: ${grepPattern}" >&2
    exit 1
  fi`.trim();
}

export function prepareForkFoundry(fuzzerArgs: JsonObject): string {
  let chain = fuzzerArgs?.forkMode
    ? getChainUrl(fuzzerArgs?.forkMode.toString())
    : ``;

  let block = ``;
  if (fuzzerArgs?.forkBlock) {
    block =
      fuzzerArgs.forkBlock === "LATEST" ? `` : `, ${fuzzerArgs.forkBlock}`;
  }

  const forkString = `vm.createSelectFork\\('${chain.replace(
    "https://eth-mainnet.g.alchemy.com/v2/",
    "https:\\/\\/eth-mainnet.g.alchemy.com\\/v2\\/"
  )}'${block}\\);`;
  console.log("forkString: ", forkString);
  return forkString;
}

export function getChainUrl(chain: string): string {
  let chainUrl;

  // Swithcing between the most common chains
  switch (chain) {
    case "MAINNET":
      chainUrl = `https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`;
      break;

    case "OPTIMISM":
      chainUrl = `https://opt-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`;
      break;

    case "ARBITRUM":
      chainUrl = `https://arb-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`;
      break;

    case "POLYGON":
      chainUrl = `https://polygon-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`;
      break;

    case "BASE":
      chainUrl = `https://base-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`;
      break;

    case "TESTNET-SEPOLIA":
      chainUrl = `https://eth-sepolia.g.alchemy.com/v2/${ALCHEMY_API_KEY}`;
      break;
    case "TESTNET-CORN":
      chainUrl = `https://corn-testnet.gateway.tenderly.co/${process.env.TENDERLY_API_KEY}`;
    case "CORN":
      chainUrl = `https://corn.gateway.tenderly.co/${process.env.TENDERLY_API_KEY}`;
    // If the `forkMode` is present, but it's empty or unknown, then we assume mainnet
    default:
      chainUrl = `https://eth-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}`;
  }

  return chainUrl;
}

// Helper function to construct the Foundry command
/**
 * Commands that need to accounted for on the front-end:
 * - contract: is there a contract to match?
 * - testCommand: is there a test to match?
 * - verbosity (optional): how verbose should the output be?
 * - runs: how many runs should there be?
 * - forkMode: is this a fork run?
 * - forkBlock: is this a specific block?
 * - seed: need a seed value in formatted as bytes32 but passed through as a string, i.e. 0x0000000000000000000000000000000000000000000000000000000000000001
 */
export function getFoundryCommand(
  fuzzerArgs: JsonObject,
  path: string
): string {
  const contract = fuzzerArgs?.contract
    ? `--match-contract ${fuzzerArgs.contract}`
    : "";
  // The testCommand gives us the flexibility to also accept specific tests or test commands
  const testCommand = fuzzerArgs?.testCommand
    ? `${fuzzerArgs.testCommand} ${fuzzerArgs?.testTarget}`
    : ``;
  const verbosity = fuzzerArgs?.verbosity ? `${fuzzerArgs.verbosity}` : `-vvv`;

  const runs = fuzzerArgs?.runs ? `--fuzz-runs ${fuzzerArgs.runs}` : "";
  // Use a default fuzz seed to get around the foundry CI bug
  const seed = fuzzerArgs?.seed
    ? `--fuzz-seed ${fuzzerArgs.seed}`
    : "--fuzz-seed 0x0000000000000000000000000000000000000000000000000000000000000001";

  let forkPrep = "";
  if (fuzzerArgs?.forkMode !== "NONE") {
    forkPrep = `${findAndReplace(
      "vm.createSelectFork",
      "[^;]*",
      prepareForkFoundry(fuzzerArgs)
    )} && cd ${path} && `;
  }

  // If you need to inspect the traces add this: `RUST_LOG=forge=trace,foundry_evm=trace,ethers=trace`
  const command = `${forkPrep} forge test ${contract} ${testCommand} ${verbosity} ${runs}`;

  return command;
}

// This function iterates through the gov fuzzing params and prepares the repo for it
export async function prepareDynamicReplacement(job: Job): Promise<string> {
  console.log("job received: ", job);
  console.log("In Gov Fuzz Flow");
  const fuzzerArgs = job?.fuzzerArgs as JsonObject;
  console.log("fuzzerArgs: ", fuzzerArgs);
  if (!fuzzerArgs?.prepareContracts || fuzzerArgs?.govFuzz !== true) {
    console.log("No Gov Fuzz detected");
  }

  let findCommand = "";
  let contractPrep = fuzzerArgs?.prepareContracts as JsonObject[];

  if (fuzzerArgs?.forkReplacement !== true) {
    console.log("No Fork Dynamic Replacement detected");
  } else {
    let blockNumber: string;

    if (!fuzzerArgs?.forkBlock || fuzzerArgs?.forkBlock === "LATEST") {
      blockNumber = await getLatestBlockNumber(
        getChainUrl(fuzzerArgs?.forkMode?.toString() || "")
      );
    } else {
      blockNumber = fuzzerArgs.forkBlock.toString();
    }

    console.log("Fork Dynamic Replacement Detected");
    const blockTimestamp = await getBlockTimestamp(
      getChainUrl(fuzzerArgs?.forkMode?.toString() || ""),
      blockNumber
    );
    const timestampCommand = findAndReplace(
      `vm.warp`,
      "[^;]*",
      `vm.warp\\(${blockTimestamp}\\);`,
      "Setup.sol"
    );
    const blockCommand = findAndReplace(
      `vm.roll`,
      "[^;]*",
      `vm.roll\\(${blockNumber}\\);`,
      "Setup.sol"
    );

    findCommand = `${timestampCommand} && ${blockCommand} `;
  }

  if (fuzzerArgs?.govFuzz === true) {
    contractPrep.forEach((item) => {
      if (!item?.target || !item?.endOfTargetMarker || !item?.replacement)
        return;

      console.log(`Preparing Contract ${item.target.toString()}`);
      if (findCommand === "") {
        findCommand = findAndReplace(
          item.target.toString().split("=")[0],
          item.endOfTargetMarker.toString(),
          item.replacement.toString()
        );
      } else {
        findCommand =
          findCommand +
          ` && ` +
          findAndReplace(
            item.target.toString().split("=")[0],
            item.endOfTargetMarker.toString(),
            item.replacement.toString()
          );
      }
    });
  }

  console.log(`Find command: ${findCommand}`);
  return findCommand;
}
