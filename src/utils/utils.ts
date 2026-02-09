import {
  Alert,
  BrokenProperty as BrokenPropertyDB,
  FUZZER,
} from "@prisma/client";
import {
  BrokenProperty,
  Fuzzer,
  FuzzingResults,
  processLogs,
} from "@recon-fuzz/log-parser";
import config from "src/config";
import prisma from "src/services/prisma";
import fs from "fs/promises";
import { CoverageResult } from "src/services/coverage";

export const storeBrokenProps = async (
  doneBrokenProps: string[],
  jobId: string,
  brokenProperties: BrokenProperty[],
  hasAlert: boolean,
  alerts: Alert[]
) => {
  for (const prop of brokenProperties) {
    if (
      !doneBrokenProps.includes(prop.brokenProperty) &&
      prop.sequence.includes("---End Trace---")
    ) {
      doneBrokenProps.push(prop.brokenProperty);
      await prisma.brokenProperty.create({
        data: {
          brokenProperty: prop.brokenProperty,
          traces: prop.sequence,
          job: {
            connect: {
              id: jobId,
            },
          },
        },
      });
      if (hasAlert && alerts.length > 0) {
        webHookHandlerBrokenPropertyAlert(
          jobId,
          doneBrokenProps,
          alerts,
          prop.brokenProperty,
          prop.sequence
        );
      }
    }
  }
};

export const directJobUpdateToDB = async (
  jobId: string,
  jobStats: FuzzingResults
) => {
  await prisma.job.update({
    where: {
      id: jobId,
    },
    data: {
      testsDuration: jobStats.duration,
      testsCoverage: jobStats.coverage,
      testsFailed: jobStats.failed,
      testsPassed: jobStats.passed,
      numberOfTests: jobStats.numberOfTests,
    },
  });
};

// Calls the backend to notify that the job has finished
// Used in the case of a campaign to post the result in CI/CD
export const webHookHandlerEndOfRun = async (jobId: string) => {
  const ghData = await prisma.githubData.findFirst({
    where: {
      jobId: jobId,
    },
    include: {
      campaign: true,
    },
  });
  if (ghData) {
    await fetch(`${config.backend.url}/webhooks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `${config.backend.token}`,
      },
      body: JSON.stringify({
        jobId: jobId,
        action: "runner_end_run",
      }),
    });
  }
};

let tempStorage: AlertStorage[] = [];
interface AlertStorage {
  jobId: string;
  action: string;
  alertId: string;
  brokenProperty: string;
  sequence: string;
}

// Called when a broken property is found on recurring jobs with alerts
export const webHookHandlerBrokenPropertyAlert = async (
  jobId: string,
  doneBrokenProps: string[], // Stored in  DB - give us information about how many broken props there is currently in this job
  alerts: Alert[],
  brokenProp: string,
  sequence: string
) => {
  alerts.forEach((al) => {
    const isThresholdMet = doneBrokenProps.length >= al.threshold;

    if (!isThresholdMet) {
      // If threshold is not met, store the alert for future processing when threshold is met
      if (
        !tempStorage.find(
          (x) =>
            x.jobId === jobId &&
            x.brokenProperty === brokenProp &&
            x.alertId === al.id
        )
      ) {
        tempStorage.push({
          jobId,
          action: "broken_property_alert",
          alertId: al.id,
          brokenProperty: brokenProp,
          sequence,
        });
      }
    } else {
      // When the threshold is met, send stored alerts first ( prev broken props before the threshold is met )
      // Grab all stored alerts for this job and alertId
      const storedAlerts = tempStorage.filter(
        (x) => x.jobId === jobId && x.alertId === al.id
      );

      if (storedAlerts.length > 0) {
        for (const alert of storedAlerts) {
          sendWebhook(alert);
          // Combination is unique, so we can find the index of the stored alert
          const index = tempStorage.findIndex(
            (tempData) =>
              tempData.jobId === alert.jobId &&
              tempData.alertId === alert.alertId &&
              tempData.brokenProperty === alert.brokenProperty
          );
          // Remove the alert from the temp storage so we avoid sending it again
          if (index > -1) {
            tempStorage.splice(index, 1);
          }
        }
      }

      // Send the new current alert after the threshold is met
      sendWebhook({
        jobId,
        action: "broken_property_alert",
        alertId: al.id,
        brokenProperty: brokenProp,
        sequence,
      });
    }
  });
};

const sendWebhook = async (alert: AlertStorage) => {
  try {
    await fetch(`${config.backend.url}/webhooks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `${config.backend.token}`,
      },
      body: JSON.stringify(alert),
    });
    console.log(
      `Alert sent for job ${alert.jobId} and alertId ${alert.alertId}, for broken property ${alert.brokenProperty}`
    );
  } catch (error) {
    console.error(
      `Failed to send alert for job ${alert.jobId} and alertId ${alert.alertId}, for broken property ${alert.brokenProperty}`,
      error
    );
  }
};

export const cleanUpBrokenProperties = async (
  jobId: string,
  fuzzer: FUZZER
) => {
  try {
    const jobData = await prisma.job.findUnique({
      where: {
        id: jobId,
      },
      include: {
        brokenProperties: true,
      },
    });
    const rawLogs = await fs.readFile("/tmp/final.txt", "utf8");
    let stoppperLine;

    // ---> ECHIDNA
    // If the runner simply reached the test limit, we can expect to see this:
    if (rawLogs.includes("Test limit reached. Stopping.")) {
      stoppperLine = "Test limit reached. Stopping.";
      // If the runner was killed, we can expect to see this:
    } else if (rawLogs.includes("Killed (thread killed). Stopping")) {
      stoppperLine = "Killed (thread killed). Stopping";
      // ---> MEDUSA
    } else if (rawLogs.includes("Fuzzer stopped, test results follow below")) {
      stoppperLine = "Fuzzer stopped, test results follow below";
    }

    if (stoppperLine) {
      // Split the logs to keep the unshunken logs
      const [_, ...remainingLogs] = rawLogs.split(stoppperLine);
      const shrunkenLogsRaw = remainingLogs.join(stoppperLine);
      const shrunkenLogs = processLogs(shrunkenLogsRaw, fuzzer as Fuzzer);
      // Loop through the new broken properties and update the old ones
      for (const prop of shrunkenLogs.brokenProperties) {
        const matchingProp = jobData?.brokenProperties.find(
          (p: BrokenPropertyDB) => p.brokenProperty === prop.brokenProperty
        );
        console.log("matchingProp", matchingProp);
        console.log("new logs", prop.sequence);
        if (matchingProp) {
          await prisma.brokenProperty.update({
            where: {
              id: matchingProp.id,
            },
            data: {
              traces: prop.sequence,
            },
          });
        } else {
          console.log(
            `No matching broken property found for ${prop.brokenProperty}, in unshrunken logs`
          );
        }
      }
    }
  } catch (err) {
    console.error("Failed to clean up broken properties for Echidna", err);
  }
};

// Send coverage snapshot to backend for tracking coverage progress over time
export const sendCoverageSnapshot = async (
  jobId: string,
  coverageResult: CoverageResult
) => {
  try {
    await fetch(`${config.backend.url}/webhooks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: config.backend.token,
      },
      body: JSON.stringify({
        action: "coverage_snapshot",
        jobId,
        coveragePercent: coverageResult.totalCoverage,
        perFile: coverageResult.perFile,
        timestamp: new Date().toISOString(),
      }),
    });
    console.log(
      `[coverage] Sent snapshot for job ${jobId}: ${coverageResult.totalCoverage.toFixed(2)}%`
    );
  } catch (error) {
    console.error(`[coverage] Failed to send snapshot for job ${jobId}:`, error);
  }
};
