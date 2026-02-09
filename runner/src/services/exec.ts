import {
  FuzzingResults,
  processEchidna,
  processMedusa,
  processHalmos,
} from "@recon-fuzz/log-parser";
import { ChildProcess, exec as execCmd, spawn } from "child_process";
import fs from "fs";
import nodePath from "path";
import readline from "readline";
import prisma from "./prisma";

import { Alert } from "@prisma/client";
import { directJobUpdateToDB, sendCoverageSnapshot, storeBrokenProps } from "src/utils/utils";
import { ECHIDNA_SERVER_PORT } from "./fuzzer";
import { calculateCoverage } from "./coverage";

const isWhiteListedFuzzer = (fuzzer: string): boolean => {
  return ["MEDUSA", "ECHIDNA", "HALMOS"].includes(fuzzer);
};

export async function exec(
  cmd: string,
  onData = (_: string) => undefined
): Promise<string> {
  return new Promise((resolve, reject) => {
    const process = execCmd(cmd, (error, stdout, stderr) => {
      const output = stdout ? stdout : stderr;
      console.log(output);
      if (error) {
        reject(error);
      } else {
        resolve(output.trim());
      }
    });
    process.stdout?.on("data", onData);
    process.stderr?.on("data", onData);
  });
}

export function subprocess(cmd: string): ChildProcess {
  const process: ChildProcess = spawn(cmd, { shell: true });
  process.stdout?.on("data", (data) => console.log(data.toString()));
  process.stderr?.on("data", function (data) {
    console.log(data.toString());
  });
  process.on("exit", function (code) {
    console.log(code?.toString());
  });
  return process;
}

let jobStats: FuzzingResults = {
  duration: "0",
  coverage: 0,
  failed: 0,
  passed: 0,
  results: [],
  traces: [],
  brokenProperties: [],
  numberOfTests: 0,
};

let doneBrokenProps: string[] = [];

export function streamExec(
  path: string,
  fuzzerCommand: string,
  outputPath: string,
  jobId: string,
  fuzzer: string,
  hasAlerts: boolean,
  alerts?: Alert[]
): Promise<void> {
  console.log("running in : streamExec with fuzzer:", fuzzer);
  return new Promise((resolve, reject) => {
    const writeStream = fs.createWriteStream(outputPath);

    const command = `cd ${path} && ${fuzzerCommand}`;

    const process = spawn("bash", ["-c", command]);
    const lineReader = readline.createInterface({
      input: process.stdout,
      terminal: false,
    });

    let terminated = false;
    let checkIntervalSeconds = 60;

    // Niave implementation based on time since starting command
    const checkIntervalMillis = checkIntervalSeconds * 1000;

    // Lcov coverage snapshots for ECHIDNA: first after 1 minute, then every 5 minutes
    const LCOV_FIRST_DUMP_MS = 1 * 60 * 1000; // 1 minute
    const LCOV_DUMP_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
    let lcovIntervalId: NodeJS.Timeout | null = null;
    let lcovFirstTimeoutId: NodeJS.Timeout | null = null;

    const dumpLcovCoverage = async () => {
      if (terminated) return;
      try {
        const response = await fetch(`http://127.0.0.1:${ECHIDNA_SERVER_PORT}/dump_lcov`, {
          method: "POST",
        });
        if (response.ok) {
          const data = await response.json();
          console.log(`[lcov] Dumped coverage to: ${data.file}`);
          console.log(`[lcov] Project path: ${path}`);

          // Resolve the lcov file path relative to project path
          // Echidna returns path relative to where it runs (inside ${path})
          const lcovFile = nodePath.resolve(path, data.file);
          console.log(`[lcov] Resolved lcov path: ${lcovFile}`);

          // Calculate coverage and send snapshot to backend
          try {
            const coverageResult = await calculateCoverage(lcovFile, path);
            console.log(`[lcov] Coverage: ${coverageResult.totalCoverage.toFixed(2)}%`);
            await sendCoverageSnapshot(jobId, coverageResult);
          } catch (coverageErr) {
            console.log(`[lcov] Error calculating coverage: ${coverageErr}`);
          }
        } else {
          console.log(`[lcov] Failed to dump coverage: ${response.status}`);
        }
      } catch (err) {
        console.log(`[lcov] Error dumping coverage: ${err}`);
      }
    };

    if (fuzzer === "ECHIDNA") {
      // First snapshot after 1 minute
      lcovFirstTimeoutId = setTimeout(async () => {
        await dumpLcovCoverage();
        // Then start the 5-minute interval
        lcovIntervalId = setInterval(dumpLcovCoverage, LCOV_DUMP_INTERVAL_MS);
      }, LCOV_FIRST_DUMP_MS);
    }

    const intervalId = setInterval(() => {
      if (isWhiteListedFuzzer(fuzzer)) {
        // Update job data in the DB once the job is over
        directJobUpdateToDB(jobId, jobStats);
      }
      // Check the stop condition
      if (!terminated) {
        checkStopCondition(jobId)
          .then((shouldStop) => {
            if (shouldStop) {
              console.log("Stopping process due to stop condition...");
              terminated = true;
              process.kill("SIGINT");
            }
            // If the check errors out there must be an issue with the DB
            // Should we terminate in that case?
            // Technically the runner could still upload to AWS?
          })
          .catch((error) => {
            console.error("Error checking stop condition:", error);
            terminated = true;
            process.kill("SIGINT");
          });
      }
    }, checkIntervalMillis);

    lineReader.on("line", (line) => {
      // Keep writing the logs to the final.txt file
      // removes non-ASCII characters and specific strings that pop up from the fuzzers
      const processedLine = line
        .replace(/[^\x20-\x7E]+/g, "")
        .replace(/\[0m/g, "")
        .replace(/\[32m/g, "")
        .replace(/\[36m/g, "");
      console.log(processedLine);
      writeStream.write(processedLine + "\n");

      // Handle based on fuzzer
      if (fuzzer === "MEDUSA") {
        processMedusa(processedLine, jobStats);
      } else if (fuzzer === "ECHIDNA") {
        processEchidna(processedLine, jobStats);
      } else if (fuzzer === "HALMOS") {
        processHalmos(processedLine, jobStats);
      }
      if (jobStats.brokenProperties.length > 0) {
        storeBrokenProps(
          doneBrokenProps,
          jobId,
          jobStats.brokenProperties,
          hasAlerts,
          alerts || []
        );
      }
    });

    process.stderr.on("data", (data) => {
      console.error(`stderr: ${data}`);
      writeStream.write(`stderr:` + data + "\n");
    });

    process.on("close", (code) => {
      clearInterval(intervalId);
      if (lcovFirstTimeoutId) clearTimeout(lcovFirstTimeoutId);
      if (lcovIntervalId) clearInterval(lcovIntervalId);
      writeStream.end();

      if (isWhiteListedFuzzer(fuzzer)) {
        // Update job data in the DB once the job is over
        directJobUpdateToDB(jobId, jobStats);
      }

      // Code 1 means that there was failure case in the test
      // Code 7 means that the fuzzer was stopped for Medusa
      if (code === 0 || code === 1 || code === 7) {
        resolve();
      } else {
        reject(new Error(`Process exited with code ${code}`));
      }
    });

    process.on("exit", (code) => {
      console.log(`Process exit with code: ${code}`);
      if (isWhiteListedFuzzer(fuzzer)) {
        // Update job data in the DB once the job is over
        directJobUpdateToDB(jobId, jobStats);
      }
    });

    process.on("error", (error) => {
      if (isWhiteListedFuzzer(fuzzer)) {
        // Update job data in the DB once the job is over
        directJobUpdateToDB(jobId, jobStats);
      }
      clearInterval(intervalId);
      if (lcovFirstTimeoutId) clearTimeout(lcovFirstTimeoutId);
      if (lcovIntervalId) clearInterval(lcovIntervalId);
      writeStream.end();
      reject(error);
    });

    // Handle unexpected termination like SIGKILL
    process.on("disconnect", () => {
      clearInterval(intervalId);
      if (lcovFirstTimeoutId) clearTimeout(lcovFirstTimeoutId);
      if (lcovIntervalId) clearInterval(lcovIntervalId);
      if (isWhiteListedFuzzer(fuzzer)) {
        // Update job data in the DB once the job is over
        directJobUpdateToDB(jobId, jobStats);
      }
      writeStream.end();
      if (!terminated) {
        console.error("Process disconnected unexpectedly");
        reject(new Error("Process disconnected unexpectedly"));
      }
    });
  });
}

// General handler for checking stop conditions
// Note we should expand this to cover other conditions like stop after broken property
// For now we check if the db has been updated: job.status == STOPPED
async function checkStopCondition(jobId: string): Promise<boolean> {
  console.log("Checking status");
  // We establish a new connection because passing in the `job` object from `runner` leads to stale checks.
  const job = await prisma.job.findUniqueOrThrow({
    where: {
      id: jobId,
    },
  });

  // First generic condition check
  if (job.status === "STOPPED") {
    return true;
  }

  /* IMPORTANT!
    We need to be careful activating the below, as it would immediately affect ALL orgs
    Including it here for review already as it could be a main driver of gracefully terminating jobs

  // Second generic stop condition
  const org = await prisma.organization.findUniqueOrThrow({
    where: {
      id: job.organizationId,
    }
  });

  // If an org has no minutes left then we gracefully terminate
  if (org.totalMinutesLeft === 0) {
    return true;
  } else {
    // If an org had minutes left then we decrement those minutes
    try {
      const result = await prisma.organization.update({
        where: {
          id: job.organizationId,
        },
        data: {
          totalMinutesLeft: {
            decrement: 1
          }
        }
      })
    } catch {
      // If it fails we should also gracefully terminate the job
      return true;
    }
  }
  */

  return false;
}
