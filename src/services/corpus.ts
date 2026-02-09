import { Job } from "@prisma/client";
import fs from "fs";
import { exec } from "./exec";
import config from "../config";
import { JsonObject } from "@prisma/client/runtime/library";
import { calculateCoverage } from "./coverage";
import { sendCoverageSnapshot } from "../utils/utils";

const getFuzzerCoverageReportDirectory = (job: Job) => {
  if (job.fuzzer === "MEDUSA") {
    return "medusa";
  } else if (job.fuzzer === "ECHIDNA") {
    return "echidna";
  } else if (job.fuzzer === "HALMOS") {
    return "halmos";
  }
};

// Let's fetch the correct corpus directory
export async function getCorpusDirectory(job: any, path: string) {
  // We check if a custom config file has been set and is not ""
  if (job.fuzzerArgs.config && job.fuzzerArgs.config !== "") {
    // We need the path because we aren't using exec and we start our node app in root where the id is the data folder
    const lines = fs
      .readFileSync(`${path}/${job.fuzzerArgs.config}`, "utf8")
      .split(/\r?\n/);
    console.log(`Reading file at: ${path}/${job.fuzzerArgs.config}`);

    for (const line of lines) {
      // If we have the file we check line by line to find the corpus directory
      // There should never be both of these in one file, this would be a client issue
      if (line.includes("corpusDirectory") || line.includes("corpusDir")) {
        // Extract the value after the colon, trim whitespace and quotes
        return line
          .split(":")[1]
          .trim()
          .replace(/['",]+/g, "");
      }
    }
    // If we are here and haven't returned yet, the file is present but no dir is specified
    // Also handle the case where the config is specified but the dir is not specified
    const directory = getFuzzerCoverageReportDirectory(job);
    if (directory) {
      return directory;
    }
    // Note: we are not handling Foundry fuzzing yet

    throw new Error(
      "corpusDirectory or corpusDir key not found in config file"
    );
  } else if (fs.existsSync(`${path}/medusa.json`) && job.fuzzer === "MEDUSA") {
    const lines = fs.readFileSync(`${path}/medusa.json`, "utf8").split(/\r?\n/);

    for (const line of lines) {
      // If we have the file we check line by line to find the corpus directory
      // There should never be both of these in one file, this would be a client issue
      if (line.includes("corpusDirectory") || line.includes("corpusDir")) {
        // Extract the value after the colon, trim whitespace and quotes
        return line
          .split(":")[1]
          .trim()
          .replace(/['",]+/g, "");
      }
    }

    // If we are here and haven't returned yet, the file is present but no dir is specified
    // Also handle the case where the config is specified but the dir is not specified
    const fuzzer = getFuzzerCoverageReportDirectory(job);
    if (fuzzer) {
      return fuzzer;
    }

    // Note: we are not handling Foundry fuzzing yet

    throw new Error(
      "corpusDirectory or corpusDir key not found in config file"
    );
  } else if (
    fs.existsSync(`${path}/echidna.yaml`) &&
    job.fuzzer === "ECHIDNA"
  ) {
    const lines = fs
      .readFileSync(`${path}/echidna.yaml`, "utf8")
      .split(/\r?\n/);

    for (const line of lines) {
      // If we have the file we check line by line to find the corpus directory
      // There should never be both of these in one file, this would be a client issue
      if (line.includes("corpusDirectory") || line.includes("corpusDir")) {
        // Extract the value after the colon, trim whitespace and quotes
        return line
          .split(":")[1]
          .trim()
          .replace(/['",]+/g, "");
      }
    }

    // If we are here and haven't returned yet, the file is present but no dir is specified
    // Also handle the case where the config is specified but the dir is not specified
    const directory = getFuzzerCoverageReportDirectory(job);
    if (directory) {
      return directory;
    }
  } else {
    // No config file found! Should never happen, but safe defaults just in case
    const directory = getFuzzerCoverageReportDirectory(job);
    if (directory) {
      return directory;
    }
    // No foundry for now
    throw new Error("Unsupported fuzzer");
  }
}

export async function uploadCorpus(job: Job, path: string) {
  console.log("Upload corpus");
  try {
    // Check to find the corpus directory (if specified)
    const corpusDir = await getCorpusDirectory(job, path);
    console.log(`Corpus Dir:  ${corpusDir}`);
    if (corpusDir) {
      // during the fuzz run the fuzzer creates a folder to store the cov and corpus in
      // if this is wrong we lose the cov file!
      const coverageFile = await exec(
        `find ${path}/${corpusDir} -name '*.html' | tail -n1`
      );

      // Find and process the final lcov file for coverage tracking
      if (job.fuzzer === "ECHIDNA") {
        try {
          const lcovFile = await exec(
            `find ${path}/${corpusDir} -name '*.lcov' | tail -n1`
          );
          if (lcovFile) {
            console.log(`[lcov] Final lcov file: ${lcovFile}`);
            const coverageResult = await calculateCoverage(lcovFile, path);
            console.log(`[lcov] Final coverage: ${coverageResult.totalCoverage.toFixed(2)}%`);
            await sendCoverageSnapshot(job.id, coverageResult);
          }
        } catch (lcovErr) {
          console.log(`[lcov] Error processing final coverage: ${lcovErr}`);
        }
      }

      if (coverageFile) {
        await exec(`cd ${path} && zip -r final.zip ${corpusDir}`);
        await exec(
          `aws s3 cp ${path}/final.zip s3://${config.aws.s3.bucket}/job/${job.id}/corpus/final.zip`
        );
        await exec(
          `aws s3 sync ${path}/${corpusDir} s3://${config.aws.s3.bucket}/job/${job.id}/corpus/${corpusDir}`
        );
        await exec(
          `aws s3 cp ${coverageFile} s3://${config.aws.s3.bucket}/job/${job.id}/coverage/final.html`
        );
      } else {
        // If there is no coverage file something went wrong
        // We do know that there will be a corpus dir if we are here
        // so we save what we have in the bucket for reconstruction
        await exec(`cd ${path} && zip -r final.zip ${corpusDir}`);
        await exec(
          `aws s3 cp ${path}/final.zip s3://${config.aws.s3.bucket}/job/${job.id}/corpus/final.zip`
        );
        await exec(
          `aws s3 sync ${path}/${corpusDir} s3://${config.aws.s3.bucket}/job/${job.id}/corpus/${corpusDir}`
        );
      }
    } else {
      // This means the corpus directory command failed
      console.log(
        "ERROR: Could not determine corpus directory from config file or fuzzer name."
      );
    }
  } catch (err) {
    console.log("ERROR: ", err);
  }
}

// Note: the provided id must use the same directory structure (corpusDir), otherwise it will fail.
export async function customCorpus(job: Job, path: string) {
  console.log("Custom corpus URL check");

  const fuzzerArgs = job?.fuzzerArgs as JsonObject;

  if (fuzzerArgs?.targetCorpus) {
    const corpusDir = await getCorpusDirectory(job, path);
    await exec(`mkdir -p ${path}/${corpusDir}`);

    // This can still fail if the id is invalid
    // There should be a check in the input to make sure users have access to the job id supplied
    try {
      console.log("Copying old corpus");
      // We are taking the id supplied and copying it right into the local corpus dir
      await exec(
        `aws s3 sync s3://${config.aws.s3.bucket}/job/${fuzzerArgs.targetCorpus}/corpus/${corpusDir} ${path}/${corpusDir}`
      );
      // Old corpus dirs hold .html files which confuse our UI, we delete these old html files
      // Remove .html files from the local directory
      await exec(`find ${path}/${corpusDir} -name "*.html" -type f -delete`);
    } catch (err) {
      console.log("ERROR: ", err);
    }

    // Recurring job, can re-use old corpus
  } else if (job.corpusUrl) {
    // Try/catch because we can still do a new run on the fuzzer if re-use fails
    try {
      const corpusDir = await getCorpusDirectory(job, path);
      await exec(`mkdir ${path}/${corpusDir}`);

      console.log("RUN Corpus: loading prev run results");
      console.log(`CorpusDir: ${corpusDir}`);
      // We copy the existing data at the URL to the local path for the corpus dir
      // s3://staging-runner-bucket/job/a2178a85-1d03-49d2-865c-bd0a4f23f212/corpus/fuzzTests/corpus/
      await exec(
        `aws s3 sync s3://${config.aws.s3.bucket}/job/${job.id}/corpus/${corpusDir} ${path}/${corpusDir}`
      );
    } catch (error) {
      console.error("ERROR: Corpus Re-use failed:", error);
    }

    // Neither custom corpus nor corpus re-use
  } else {
    console.log("No custom or old corpus to re-use");
  }
}
