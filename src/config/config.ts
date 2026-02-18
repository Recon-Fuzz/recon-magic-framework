import dotenv from "dotenv";
// - Load env
// Need to load earlier for `yarn dev` to work
dotenv.config();


//////////////////////////
// Github               //
//////////////////////////
export const githubAppId = process.env.GITHUB_APP_ID!;
export const githubAppPrivateKey = process.env.GITHUB_APP_PRIVATE_KEY!;
export const githubAppClientID = process.env.GITHUB_APP_CLIENT_ID!;
export const githubAppSecret = process.env.GITHUB_APP_SECRET!;
export const githubToken = process.env.GHTOKEN!;

//////////////////////////
// Webhooks             //
//////////////////////////
export const githubWebhookSecret = process.env.GITHUB_WEBHOOK_SECRET!;
//////////////////////////
// Api                  //
//////////////////////////
export const apiPort = process.env.PORT || 6969;
export const databaseUrl = process.env.DATABASE_URL!;
export const fuzzTimeOut = process.env.FUZZ_TIMEOUT || "60";
export const nodeEnv = process.env.NODE_ENV || "";
export const unsafeSkipAdminCheck = process.env.UNSAFE_SKIP_ADMIN_CHECKS!;

//////////////////////////
// Runner                //
//////////////////////////
export const ecsClusterName = process.env.ECS_CLUSTER_NAME!;
export const ecsRunnerTaskDefinition = process.env.ECS_RUNNER_TASK_DEFINITION!;
export const ecsSubnets = process.env.ECS_SUBNETS!;
export const ecsSecurityGroup = process.env.ECS_SECURITY_GROUP!;
export const ecsContainerName = process.env.ECS_CONTAINER_NAME!;
export const ecsRegion = process.env.AWS_REGION || 'us-east-1'!;
export const ecsAwsAccessKeyId = process.env.AWS_ACCESS_KEY_ID!;
export const ecsAwsSecretAccessKey = process.env.AWS_SECRET_ACCESS_KEY!;
export const jsonWebTokenSecretRunner = process.env.JSON_WEB_TOKEN_SECRET_RUNNER!;
//////////////////////////
// Job                  //
//////////////////////////
export const jobInterval = Number(process.env.JOB_START_INTERVAL || 60*1000);  // One minute by default
export const enableRunsOnCommit = process.env.ENABLE_RUNS_ON_COMMIT!;
export const linkPrefix = process.env.LINK_PREFIX! || "http://localhost:3000/dashboard/jobs/";

//////////////////////////
// AWS                  //
//////////////////////////
export const assetsUrl = process.env.AWS_ASSETS_URL!;
export const awsCloudFrondKeyPairId = process.env.AWS_CLOUDFRONT_KEY_PAIR_ID!;
export const awsCloudFrontPrivateKey = process.env.AWS_CLOUDFRONT_PRIVATE_KEY!.split(String.raw`\n`).join('\n');

//////////////////////////
// CORS                 //
//////////////////////////
//NB:
// This is gonna break if we ever add vercel previews
export const allowedOrigins = [
  "https://getrecon.xyz",
  "https://staging.getrecon.xyz",
  "http://localhost:3000"
];

//////////////////////////
// TELEGRAM             //
//////////////////////////
export const telegramBotToken = process.env.TELEGRAM_BOT_TOKEN!;

//////////////////////////
// FACTORY LISTENER     //
//////////////////////////
export const factoryListenerAddress = process.env.FACTORY_LISTENER_ADDRESS!;
export const factoryListenerSecret = process.env.FACTORY_LISTENER_SECRET!;


//////////////////////////
// CLAUDE               //
//////////////////////////
export const claudeSecret = process.env.CLAUDE_SECRET!;

