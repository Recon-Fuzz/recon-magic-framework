// src/index.ts
import express, { Express, NextFunction, Request, Response } from "express";
import cors from "cors";
import pino from "pino-http";
import dotenv from "dotenv";
import "express-async-errors";
import * as Sentry from "@sentry/node";

Sentry.init({
  dsn: "https://1afd5065e8870a26ea298041f7ab0efe@o4506744902254592.ingest.sentry.io/4506745128419328",
  integrations: [],
});

// - Load env
// Need to load earlier for `yarn dev` to work
dotenv.config();

import { findAndProcessAbiJobs } from "./db/abiJobs";
import startRunner from "./runner-starter/starter";

// ROUTES DEBUG
// TODO: Test that ensure these are never exposed in prod
import superRoutes from "./routes/super/debug";

// ROUTES PROD
import docsRoutes from "./routes/docs";
import claudeJobsRoutes from "./routes/claude/jobs";
import claudeInvitesRoutes from "./routes/claude/invites";
import abiRoutes from "./routes/abi";
import abiJobRoutes from "./routes/abiJobs";
import authRoutes from "./routes/auth";
import apiKeyRoutes from "./routes/apiKey";
import buildRoutes from "./routes/build";
import campaignsRoutes from "./routes/campaigns";
import installRoutes from "./routes/installs";
import jobsRoutes from "./routes/jobs";
import monitoringsRoutes from "./routes/monitorings";
import organizationRoutes from "./routes/organizations";
import orgInvitesRoutes from "./routes/orgInvites";
import recipesRoutes from "./routes/recipes";
import recurringRoutes from "./routes/recurring";
import sharesRoutes from "./routes/shares";
import subscriptionRoutes from "./routes/subscriptions";
import webhookRoutes from "./routes/webhooks";
import alertsRoutes from "./routes/alerts";
import telegramRoutes from "./routes/telegram";
import governanceFuzzingRoutes from "./routes/governanceFuzzing";
import githubRoutes from "./routes/github";
import reposRoutes from "./routes/repos";
import magicCreditsRoutes from "./routes/magicCredits";


// MORE STUFF TO REFACTOR
import { User } from "@prisma/client";
import runCron from "./cron-starter/starter";
import { allowedOrigins, apiPort, jobInterval } from "./config/config";

/**
 * Index
 * - Global Namespace
 * - Load Env
 * - Setup Basics
 * - Check Config
 * - Start Router
 * - Load Routes (by topic)
 * - Setup Cron Worker
 */

// TODO: I can't figure out how to put this in a separate file
declare global {
  namespace Express {
    interface Request {
      user: {
        login: string; // Used exclusively to create the org
        id: number; // Used for auth, it's the GH id
        token: string; // Auth
        userData: User | null; // User data from the DB
        authenticatedBy: "github" | "listener" | "apiKeyRead" | "apiKeyWrite";
      };
    }
  }
}

// - Setup Basics
const app: Express = express();

// NOTE: Above so we can use Raw Parser
app.use("/webhooks", webhookRoutes);

app.use(express.json());
app.use(cors({
  origin: function(origin, callback){
    if(!origin) return callback(null, true); // allow requests with no origin - like curl requests
    if(allowedOrigins.indexOf(origin) === -1){
      const msg = "The CORS policy for this site does not allow access from the specified Origin.";
      return callback(new Error(msg), false);
    }
    return callback(null, true);
  }
}));

const logger = pino({
  redact: ["req.headers"],
  level: "debug",
  transport: {
    target: "pino-pretty",
    options: {
      include: "time,responseTime,method,url,req",
    },
  },
});
app.use(logger);
app.use(Sentry.Handlers.requestHandler());

// - Start Router
app.listen(apiPort, () => {
  console.log(`[server]: Server is running at http://localhost:${apiPort}`);
});

// API Documentation at root
app.use("/", docsRoutes);

app.use("/super", superRoutes);

// TODO: REVIEW ROUTES IF THEY MAKE SENSE
// AND CLEANUP
app.use("/claude/jobs", claudeJobsRoutes);
app.use("/claude/invites", claudeInvitesRoutes);
app.use("/abi", abiRoutes);
app.use("/abiJobs", abiJobRoutes);
app.use("/auth", authRoutes);
app.use("/apiKey", apiKeyRoutes);
app.use("/build", buildRoutes);
app.use("/campaigns", campaignsRoutes);
app.use("/github", githubRoutes);
app.use("/repos", reposRoutes);

app.use("/installs", installRoutes);
app.use("/jobs", jobsRoutes);
app.use("/organizations", organizationRoutes);
app.use("/monitorings", monitoringsRoutes);

app.use("/orgInvites", orgInvitesRoutes);
app.use("/recipes", recipesRoutes);
app.use("/recurring", recurringRoutes);
app.use("/shares", sharesRoutes);
app.use("/subscriptions", subscriptionRoutes);
app.use("/alerts", alertsRoutes);
app.use("/telegram", telegramRoutes);
app.use("/governanceFuzzing", governanceFuzzingRoutes);
app.use("/magic-credits", magicCreditsRoutes);
// ABI
// TODO: REST + Permissions
// TODO: Permissions -> Only return data, if your permission token has given us access

// Error Handling
app.use(Sentry.Handlers.errorHandler());
export const errorHandler = (
  err: Error,
  req: Request,
  res: Response,
  next: NextFunction
) => {
  try {
    console.log("error", err);
  } catch {}
  res.status(500);
  return res.json({
    message: "Something went wrong",
    data: {},
  });
};


/////////////////////////
// CRON Jobs           //
/////////////////////////

let IS_ALREADY_RUNNING = false;

const interval = setInterval(async () => {
  console.log("Polling for fuzzing jobs");
  // Cron first so we queue
  await runCronLoop();

  // Starter second so we run the queue
  await runStarterLoop();

  // Worker loop last so we build
  await runWorkerLoop();
}, jobInterval);  // One minute by default

export async function runStarterLoop() {
  try {
    await startRunner();
  } catch (e) {
    console.log("Exception in Runner-Starter");
    console.log(e);
  }
}

export async function runCronLoop() {
  try {
    await runCron();
  } catch (e) {
    console.log("Exception in runCron");
    console.log(e);
  }
}

// NOTE: We use this to avoid double queuing jobs

// NOTE: Seperated so we can call it from above in certain scenarios
export async function runWorkerLoop() {
  console.log("Automated Job Check");
  if (IS_ALREADY_RUNNING) {
    console.info("Interval was elapsed, but job was already running, skip");
    return;
  }

  IS_ALREADY_RUNNING = true;
  try {
    await findAndProcessAbiJobs();
  } catch (e) {
    console.log("Exception in job queue", e);
  }

  IS_ALREADY_RUNNING = false;
}
