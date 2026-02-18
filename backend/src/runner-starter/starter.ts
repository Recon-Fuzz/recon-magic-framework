import { ECSClient, RunTaskCommand } from "@aws-sdk/client-ecs";
import prisma from "./services/prisma";
import config from "./config";
import { getCloneUrlAndToken } from "../github/installations";
import { databaseUrl, fuzzTimeOut } from "../config/config";

const ecs = new ECSClient({
  region: config.aws.region,
  credentials: {
    accessKeyId: config.aws.accessKeyId,
    secretAccessKey: config.aws.secretAccessKey,
  },
});

export default async function startRunner() {
  // TODO: Change this to EDIT the Job to QUEUING (take the lock)
  const job = await prisma.job.findFirst({
    where: {
      status: "QUEUED",
    },
    orderBy: {
      updatedAt: "asc",
    },
  });
  if (!job) {
    return console.log("No jobs on queue");
  }

  // NOTE: Trying to see if this changes the updated at
  // TODO: More explicit recovery mechanism
  // ALSO: Need to lock the job here to prevent double queueing
  await prisma.job.update({
    where: { id: job.id },
    data: {
      status: "QUEUED",
    },
  });

  console.log("startRunner job.id", job.id);

  let url, token, lastJob;

  lastJob = "";

  try {
    const returnVal = await getCloneUrlAndToken(job.orgName, job.repoName);
    url = returnVal.url;
    token = returnVal.token;
  } catch (e) {
    console.log("Error in getting getCloneUrlAndToken: ", e);

    // If it fails the first time, then job.id !== lastJob
    // If it fails the second time, then lastJob was set and we update the status to not retry
    if (lastJob === job.id) {
      // Update the DB to not retry a failed clone
      await prisma.job.update({
        where: { id: job.id },
        data: {
          status: "ERROR",
        },
      });
    } else {
      lastJob = job.id;
    }

    // @ts-ignore
    if (e?.status! === 404) {
      // No installation for this job
      await prisma.job.update({
        where: { id: job.id },
        data: {
          status: "ERROR",
        },
      });
    }

    return console.log("Install or authorize Recon!");
  }

  const response = await ecs.send(
    new RunTaskCommand({
      cluster: config.aws.ecs.clusterName,
      launchType: "FARGATE",
      taskDefinition: config.aws.ecs.runnerTaskDefinition,
      tags: [
        {
          key: "JOB_ID",
          value: job.id,
        },
        {
          key: "ORG_REPO",
          value: `${job.orgName}/${job.repoName}`,
        },
      ],
      networkConfiguration: {
        awsvpcConfiguration: {
          subnets: config.aws.ecs.subnets.split(","),
          securityGroups: config.aws.ecs.securityGroup.split(","),
          assignPublicIp: "DISABLED",
        },
      },
      overrides: {
        containerOverrides: [
          {
            name: config.aws.ecs.containerName,
            command: ["--runner", "--job-id", job.id, "--url", url],
            environment: [
              {
                name: "DATABASE_URL",
                value: databaseUrl,
              },
              {
                name: "FUZZ_TIMEOUT",
                // Only use it if it's available
                value: job?.duration
                  ? String(job?.duration)
                  : fuzzTimeOut || "60",
              },
            ],
          },
        ],
      },
      count: 1,
      platformVersion: "LATEST",
    })
  );
  console.log(response);
  const tasks = response.tasks;
  if (!tasks) {
    return console.log("No tasks created");
  }
  const task = tasks[0];
  if (!task) {
    return console.log("No task created");
  }
  const taskArn = tasks[0].taskArn;
  if (!taskArn) {
    return console.log("No taskArn created");
  }

  await prisma.job.update({
    data: {
      status: "STARTED",
      taskArn: taskArn,
    },
    where: {
      id: job.id,
    },
  });
}
