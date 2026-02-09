import { FUZZER, Job } from "@prisma/client";
import { JsonObject } from "@prisma/client/runtime/library";
import { getChainUrl, getFoundryCommand } from "./prepare";

// Port for echidna SSE server (enables /dump_lcov endpoint)
export const ECHIDNA_SERVER_PORT = 8666;

export function getFuzzerCommand(job: Job) {
  // Hardcoded Command
  // Yarn command
  // yarn XYZ
  if (job?.arbitraryCommand) {
    return job.arbitraryCommand;
  }

  const fuzzerArgs = job?.fuzzerArgs as JsonObject;

  let testModeString: string;
  let forkModeCommand: string;

  if (fuzzerArgs?.testMode && fuzzerArgs?.testMode !== "config") {
    testModeString = `--test-mode ${fuzzerArgs?.testMode}`;
  } else {
    testModeString = "";
  }

  let path: string;

  // If there is a custom directory then we need to make sure it gets specified from the id/customDir
  if (job.directory !== ".") {
    path = `recon/${job.directory}`;
  } else {
    // else everything happens in the job.id folder that was cloned into
    path = `recon`;
  }

  // Checks if this is supposed to be an echidna fork-job, then crafts it using Recon
  // Note the hardcoded API key
  if (
    fuzzerArgs?.forkMode &&
    fuzzerArgs?.forkMode !== "NONE" &&
    job.fuzzer === "ECHIDNA"
  ) {
    let chainUrl = fuzzerArgs?.rpcUrl
      ? fuzzerArgs.rpcUrl
      : getChainUrl(fuzzerArgs.forkMode.toString());
    let forkBlock: string;

    // Note that by default all jobs that have a fork selected MUST have at least "LATEST"
    // This is enforced on the front-end, but we handle the case where it is not present in case CI/CD misconfig
    if (!fuzzerArgs?.forkBlock || fuzzerArgs.forkBlock === "LATEST") {
      forkBlock = "";
    } else {
      // Last line of defense against RCE here
      try {
        // TODO 0XSI
        // Check that
        // forkBlock = `--rpc-block ${Number(fuzzerArgs.forkBlock).toString()}`
        forkBlock = `--fork-block-number ${Number(
          fuzzerArgs.forkBlock
        ).toString()}`;
      } catch {
        // Log the error and do not use fork block
        forkBlock = "";
        console.log("ERROR: Invalid String for block number");
      }
    }

    // TODO 0XSI
    // Check that
    forkModeCommand = `nohup anvil -f ${chainUrl} ${forkBlock}  > /dev/null 2>&1 & ANVIL_PID=$!; cd ${path} &&
                  echidna ${fuzzerArgs?.pathToTester || "."} --config ${
      fuzzerArgs?.config || "echidna.yaml"
    } --contract ${
      fuzzerArgs.contract || "CryticTester"
    } ${testModeString} --rpc-url http://127.0.0.1:8545 --test-limit ${
      fuzzerArgs?.testLimit || "1000"
    } --workers 15 --server ${ECHIDNA_SERVER_PORT}; kill $ANVIL_PID`;

    // forkModeCommand = ` echidna ${fuzzerArgs?.pathToTester || "."} --config ${
    //   fuzzerArgs?.config || "echidna.yaml"
    // } --contract ${
    //   fuzzerArgs.contract || "CryticTester"
    // } ${testModeString} --rpc-url ${chainUrl}  ${forkBlock} --test-limit ${
    //   fuzzerArgs?.testLimit || "1000"
    // } --workers 15`;
    return forkModeCommand;
  }

  switch (job.fuzzer) {
    case FUZZER.ECHIDNA:
      return `echidna ${fuzzerArgs?.pathToTester || "."} --config ${
        fuzzerArgs?.config || "echidna.yaml"
      } --contract ${
        fuzzerArgs.contract || "CryticTester"
      } ${testModeString} --test-limit ${
        fuzzerArgs?.testLimit || "100000"
      } --workers 16 --server ${ECHIDNA_SERVER_PORT}`;
    case FUZZER.MEDUSA:
      return `medusa fuzz --timeout ${fuzzerArgs?.timeout || "60"} --config ${
        fuzzerArgs?.config || "medusa.json"
      } --no-color`;
    case FUZZER.FOUNDRY:
      const foundryCommand = getFoundryCommand(fuzzerArgs, path);
      return foundryCommand;
    case FUZZER.HALMOS:
      const baseHalmos = `--solver-timeout-assertion 0 --solver-timeout-branching 0 --cache-solver --coverage-output ./halmos/coverage.html`;
      // NOTE: mkdir to generate the folder cause Halmos cannot do it itself
      return `mkdir halmos && halmos ${
        fuzzerArgs?.contract !== "" ? `--contract ${fuzzerArgs?.contract}` : ""
      } ${
        fuzzerArgs?.halmosPrefix !== ""
          ? `--function ${fuzzerArgs?.halmosPrefix}`
          : ""
      } ${baseHalmos} ${
        fuzzerArgs?.halmosArray
          ? `--array-lengths ${fuzzerArgs?.halmosArray}`
          : ""
      } ${fuzzerArgs?.halmosLoops ? `--loop ${fuzzerArgs?.halmosLoops}` : ""} ${
        fuzzerArgs?.verbosity || ""
      }`;
    case FUZZER.KONTROL:
      // Step 1: Build Kontrol
      // Step 2: Run Kontrol
      return `. /root/.nix-profile/etc/profile.d/nix.sh && . /root/.nix-profile/etc/profile.d/nix.sh && kontrol build && kontrol prove --match-test ${fuzzerArgs?.kontrolTest} --verbose && kontrol list`;
  }
}
