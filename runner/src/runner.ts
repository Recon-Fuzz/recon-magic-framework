import { Alert, FUZZER, Job, JobStatus } from "@prisma/client";
import prisma from "./services/prisma";
import config from "./config";
import { exec, streamExec } from "./services/exec";
import { getFuzzerCommand } from "./services/fuzzer";
import { customCorpus, uploadCorpus } from "./services/corpus";
import { prepareDynamicReplacement } from "./services/prepare";
import { cleanUpBrokenProperties, webHookHandlerEndOfRun } from "./utils/utils";
import { existsSync } from "fs";

interface Params {
  jobId: string;
  url: string;
}

// This defines how often the logs are updated while the job is running.
// Be careful! This may impact running costs!
const LOGS_INTERVAL_MS = 60 * 1000;

export default async function main(params: Params) {
  console.log("RUN: Start runner");

  if (!params.jobId) {
    console.error("No job ID provided");
    process.exit(1);
  }

  let job: Job;
  try {
    job = await prisma.job.findUniqueOrThrow({
      where: {
        id: params.jobId,
      },
    });
  } catch (err) {
    console.log("Error in getting job: ", err);
    process.exit(1);
  }

  let alerts: Alert[] = [];

  //Grab the alerts for the recurring job
  const recurring = await prisma.recurringJob.findFirst({
    where: {
      jobs: {
        some: {
          id: job.id,
        },
      },
    },
    include: {
      alerts: true,
    },
  });

  let createdFromRecipeAndHasAlerts;
  // If a job is created from a recipe, we should be able to map them
  if (job.recipeId) {
    createdFromRecipeAndHasAlerts = await prisma.recipe.findFirst({
      where: {
        id: job.recipeId,
      },
      include: {
        alerts: true,
      },
    });
  }

  // Find the alerts
  if (recurring && recurring.alerts) {
    alerts = recurring.alerts;
  } else if (createdFromRecipeAndHasAlerts && createdFromRecipeAndHasAlerts.alerts) {
    alerts = createdFromRecipeAndHasAlerts.alerts;
  } else {
    console.log("Fail to find alerts configured for the job")
  }

  const hasAlerts = !!recurring || !!createdFromRecipeAndHasAlerts;

  try {
    await prisma.job.update({
      data: {
        status: "RUNNING",
      },
      where: {
        id: job.id,
      },
    });
  } catch (error) {
    console.error("Error updating job status:", error);
    process.exit(1);
  }

  // To do: extract this into it's own file
  try {
    // If there was a token (private repo) the url contains the entire url
    if (params.url.includes("https://git:")) {
      console.log("RUN: Git Clone Private");

      const tokenRegex = /git:([^@]+)@github.com/;
      const match = params.url.match(tokenRegex);
      const token = match ? match[1] : "";

      await exec(
        `git config --global url."https://git:${token}@github.com/${job.orgName}".insteadOf "https://github.com/${job.orgName}"`
      );
      await exec(
        `git config --global url."https://github.com/".insteadOf "git@github.com:"`
      );

      await exec(
        `git clone --recurse-submodules -b ${job.ref} --single-branch ${params.url} recon`
      );

      // If there was no token this is a simple clone
    } else {
      console.log("RUN: Git Clone Public");
      await exec(
        `git clone --recurse-submodules -b ${job.ref} --single-branch https://github.com/${job.orgName}/${job.repoName} recon`
      );
    }
    console.log("Repo cloned successfully");
  } catch (error: any) {
    console.error("Git clone failed:", error);

    await prisma.job.update({
      data: {
        status: "ERROR",
      },
      where: {
        id: job.id,
      },
    });

    // Kill the runner
    process.exit(1);
  }

  try {
    // Create the temp folder for logs
    await exec(`touch /tmp/final.txt`);
  } catch (err: any) {
    console.log("Error creating final.txt: ", err);
    process.exit(1);
  }

  // Create partial logs and update the link every interval
  const intervalId = setInterval(async () => {
    const value =
      Math.floor(new Date().getTime() / LOGS_INTERVAL_MS) * LOGS_INTERVAL_MS;
    const logsUrl = `s3://${config.aws.s3.bucket}/job/${job.id}/logs/partial-${value}.txt`;
    // Copy the current state of final.txt to the bucket
    await exec(`aws s3 cp /tmp/final.txt ${logsUrl}`);
    // We update the job here, because this ensures we populate the logsUrl, which allows the front-end to have up to date logs!
    await prisma.job.update({
      data: {
        logsUrl: `/job/${job.id}/logs/partial-${value}.txt`,
      },
      where: {
        id: job.id,
      },
    });
  }, LOGS_INTERVAL_MS);

  let status: JobStatus;
  let path: string;

  // If there is a custom directory then we need to make sure it gets specified from the id/customDir
  if (job.directory !== ".") {
    path = `recon/${job.directory}`;
  } else {
    // else everything happens in the job.id folder that was cloned into
    path = `recon`;
  }
  console.log("Path used: ", path);

  // We check if there is either a custom corpus, or an old corpus available to re-use
  // TODO-foundry First Foundry change: do nothing if this is a Foundry-based test
  if (job.fuzzer === "ECHIDNA" || job.fuzzer === "MEDUSA") {
    try {
      await customCorpus(job, path);
    } catch (err) {
      console.log("Error with corpus:", err);
      // We fail the job if the corpus is not as expected
      process.exit(1);
    }
  }

  // In case there are any custom changes needed, like for gov fuzzing, we prepare the contracts here.
  try {
    const dynamicReplacementString = await prepareDynamicReplacement(job);
    if (dynamicReplacementString !== "") {
      await exec(dynamicReplacementString);
    }
  } catch (err) {
    console.log(`Dynamic Replacement Error: ${err}`);
    console.log("RUN: End runner");
    await prisma.job.update({
      data: {
        status: "ERROR",
      },
      where: {
        id: job.id,
      },
    });
    process.exit(1);
  }

  try {
    if (job.preprocess) {
      console.log(`RUN Preprocess: ${job.preprocess}`);
      //preprocess = subprocess(`cd ${path} && ${job.preprocess}`);
      await exec(`cd ${path} && ${job.preprocess}`);
    }
  } catch (err) {
    console.log("Error in preprocess: ", err);
    process.exit(1);
  }

  // Check for recon-coverage.json and generate if not present
  const reconCoveragePath = `${path}/recon-coverage.json`;
  if (!existsSync(reconCoveragePath)) {
    console.log("recon-coverage.json not found, attempting to generate...");
    try {
      await exec(`cd ${path} && npx -y recon-generate@latest coverage`);
      console.log("recon-coverage.json generated successfully");
    } catch (err) {
      console.log("Error generating recon-coverage.json: ", err);
      // Continue without failing - coverage generation is optional
    }
  } else {
    console.log("recon-coverage.json already exists, skipping generation");
  }

  // Some jobs need custom preprocesses
  // RCE risk! Always check what is being done in package.json scripts
  try {
    // Depending on the fuzzer we have different commands
    const fuzzerCommand = getFuzzerCommand(job);
    console.log(`RUN Fuzzing: ${fuzzerCommand}`);
    // 0XSI - That where we write to final.txt
    await streamExec(
      path,
      fuzzerCommand || "",
      "/tmp/final.txt",
      job.id,
      job.fuzzer,
      hasAlerts,
      alerts
    );
    status = "SUCCESS";
  } catch (err) {
    status = "ERROR";
    console.log("ERROR in during fuzzing process:", err);
    process.exit(1);
  }

  const isSupportedFuzzer = ["ECHIDNA", "MEDUSA", "HALMOS"].includes(
    job.fuzzer
  );

  if (isSupportedFuzzer) {
    try {
      await cleanUpBrokenProperties(job.id, job.fuzzer as FUZZER);
    } catch (err) {
      console.log("Error in cleaning up broken properties: ", err);
      // Note:
      // Even if clean up fail, we don't want to kill the process here
    }
  }

  // upload corpus, coverage
  // Foundry doesn't generate a corpus
  if (isSupportedFuzzer) {
    await uploadCorpus(job, path);
  }

  try {
    console.log("uploading final txt to S3 ....");
    await exec(
      `aws s3 cp /tmp/final.txt s3://${config.aws.s3.bucket}/job/${job.id}/logs/final.txt`
    );
  } catch (err) {
    console.log("Error in uploading final.txt: ", err);
    // No process exit, we don't want to stop the runner here
  }

  try {
    console.log("Updating job artifacts urls ....");
    await prisma.job.update({
      data: {
        status,
        coverageUrl: `/job/${job.id}/coverage/final.html`,
        corpusUrl: `/job/${job.id}/corpus/final.zip`,
        logsUrl: `/job/${job.id}/logs/final.txt`,
      },
      where: {
        id: job.id,
      },
    });
  } catch (err) {
    console.log("Error in uploading job artifacts: ", err);
    // No process exit, we don't want to stop the runner here
  }

  try {
    await webHookHandlerEndOfRun(job.id);
  } catch (err) {
    console.log("error in webhook handler", err);
    // No process exit, we don't want to stop the runner here
  }

  console.log("RUN: End runner");
  process.exit(0);
}
