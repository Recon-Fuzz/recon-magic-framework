import { Request, Response } from "express";
import express from "express";

const router = express.Router();
export default router;

router.get("/", async (req: Request, res: Response) => {
  const html = `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Documentation</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 2.5em;
        }
        .subtitle {
            color: #7f8c8d;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .auth-info {
            background: #e8f4f8;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin-bottom: 30px;
            border-radius: 4px;
        }
        .auth-info code {
            background: #d4e9f1;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Monaco', 'Courier New', monospace;
        }
        h2 {
            color: #2c3e50;
            margin-top: 40px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
        }
        .endpoint {
            margin-bottom: 25px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 4px;
            border-left: 3px solid #95a5a6;
        }
        .method {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 0.85em;
            margin-right: 10px;
            font-family: monospace;
        }
        .method.get { background: #61affe; color: white; }
        .method.post { background: #49cc90; color: white; }
        .method.put { background: #fca130; color: white; }
        .method.delete { background: #f93e3e; color: white; }
        .path {
            font-family: 'Monaco', 'Courier New', monospace;
            color: #2c3e50;
            font-weight: 500;
        }
        .description {
            margin-top: 8px;
            color: #555;
        }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.75em;
            margin-left: 8px;
            background: #e74c3c;
            color: white;
            font-weight: 600;
        }
        .note {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 12px;
            margin-top: 30px;
            border-radius: 4px;
            color: #856404;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>API Documentation</h1>
        <p class="subtitle">RESTful API for fuzzing operations and repository analysis</p>

        <div class="auth-info">
            <strong>Authentication:</strong> All endpoints require authentication via API Key.<br>
            Request a Key to an Admin or via the FE<br>
            Include your API key in the Authorization header: <code>Authorization: Bearer api_YOUR_API_KEY</code>
        </div>

        <h2>ABIs</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/abi</span>
            <div class="description">Get all ABIs for your organization</div>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/abi/:orgName/:repoName/:branch</span>
            <div class="description">Get ABI for a specific repository and branch</div>
        </div>

        <div class="endpoint">
            <span class="method delete">DELETE</span>
            <span class="path">/abi/:abiId</span>
            <div class="description">Delete an ABI by ID</div>
        </div>

        <h2>ABI Jobs</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/abiJobs</span>
            <div class="description">Get all ABI jobs for your organization</div>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/abiJobs/:id</span>
            <div class="description">Get a specific ABI job by ID</div>
        </div>

        <h2>Alerts</h2>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/alerts/recurring</span>
            <span class="badge">PRO</span>
            <div class="description">Create an alert for a recurring job. Requires: recurringJobId, threshold, webhookUrl (optional), telegramUsername (optional), chatId (optional)</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/alerts/recipe</span>
            <span class="badge">PRO</span>
            <div class="description">Create an alert for a recipe. Requires: recipeId, threshold, webhookUrl (optional), telegramUsername (optional), chatId (optional)</div>
        </div>

        <div class="endpoint">
            <span class="method delete">DELETE</span>
            <span class="path">/alerts/:alertId</span>
            <div class="description">Delete an alert</div>
        </div>

        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/alerts/edit/:alertId</span>
            <span class="badge">PRO</span>
            <div class="description">Edit an alert. Body: alertId, webhookUrl, threshold, telegramHandle, chatId</div>
        </div>

        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/alerts/toggle/:alertId</span>
            <div class="description">Toggle an alert on/off</div>
        </div>

        <h2>Campaigns</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/campaigns</span>
            <span class="badge">PRO</span>
            <div class="description">Get all campaigns for your organization</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/campaigns</span>
            <span class="badge">PRO</span>
            <div class="description">Create a new campaign. Requires: displayName, orgNames, repoNames, branchNames, recipeIds</div>
        </div>

        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/campaigns/togglecomments/:campaignId</span>
            <span class="badge">PRO</span>
            <div class="description">Toggle comments for a campaign. Body: comments (boolean)</div>
        </div>

        <div class="endpoint">
            <span class="method delete">DELETE</span>
            <span class="path">/campaigns/:campaignId</span>
            <span class="badge">PRO</span>
            <div class="description">Delete a campaign</div>
        </div>

        <h2>Governance Fuzzing</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/governanceFuzzing</span>
            <div class="description">Get all governance fuzzing configurations for your organization</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/governanceFuzzing</span>
            <span class="badge">PRO</span>
            <div class="description">Create governance fuzzing. Requires: contractAddress, topic, prepContract, recipeId, eventDefinition, chainId</div>
        </div>

        <div class="endpoint">
            <span class="method delete">DELETE</span>
            <span class="path">/governanceFuzzing/:id</span>
            <div class="description">Delete a governance fuzzing configuration</div>
        </div>

        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/governanceFuzzing/toggle/:id</span>
            <div class="description">Toggle governance fuzzing on/off</div>
        </div>

        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/governanceFuzzing</span>
            <span class="badge">PRO</span>
            <div class="description">Update governance fuzzing. Body: id, chainId, address, eventDefinition, topic, prepareContracts</div>
        </div>

        <h2>Jobs (Fuzzing)</h2>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/jobs/echidna</span>
            <span class="badge">PRO</span>
            <div class="description">Create an Echidna fuzzing job. Requires: orgName, repoName, ref, directory, duration, fuzzerArgs, preprocess, label, recipeId (optional)</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/jobs/medusa</span>
            <span class="badge">PRO</span>
            <div class="description">Create a Medusa fuzzing job. Requires: orgName, repoName, ref, directory, duration, fuzzerArgs, preprocess, label, recipeId (optional)</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/jobs/foundry</span>
            <span class="badge">PRO</span>
            <div class="description">Create a Foundry fuzzing job. Requires: orgName, repoName, ref, directory, duration, fuzzerArgs, preprocess, label, recipeId (optional)</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/jobs/halmos</span>
            <span class="badge">PRO</span>
            <div class="description">Create a Halmos fuzzing job. Requires: orgName, repoName, ref, directory, duration, fuzzerArgs, preprocess, label, recipeId (optional)</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/jobs/kontrol</span>
            <span class="badge">PRO</span>
            <div class="description">Create a Kontrol fuzzing job. Requires: orgName, repoName, ref, directory, duration, fuzzerArgs, preprocess, label, recipeId (optional)</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/jobs/canclone</span>
            <span class="badge">PRO</span>
            <div class="description">Check if repository can be cloned. Requires: orgName, repoName</div>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/jobs</span>
            <div class="description">Get all jobs for your organization</div>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/jobs/:jobId</span>
            <div class="description">Get a specific job by ID</div>
        </div>

        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/jobs/stop/:jobId</span>
            <div class="description">Stop a running job</div>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/jobs/brokenProperty/:jobId</span>
            <div class="description">Get broken properties for a job</div>
        </div>

        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/jobs/label/:jobId</span>
            <div class="description">Update job label. Body: newLabel</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/jobs/rerun/:jobId</span>
            <span class="badge">PRO</span>
            <div class="description">Rerun a job with the same configuration</div>
        </div>

        <h2>API Keys</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/apiKey</span>
            <div class="description">Get all API keys for your organization</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/apiKey</span>
            <div class="description">Create a new API key. Body: label, canWrite (boolean)</div>
        </div>

        <div class="endpoint">
            <span class="method delete">DELETE</span>
            <span class="path">/apiKey</span>
            <div class="description">Delete an API key. Query or Body: id</div>
        </div>

        <h2>Authentication</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/auth/me</span>
            <div class="description">Get current user information</div>
        </div>

        <h2>Build</h2>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/build</span>
            <div class="description">Trigger a build process. Body: orgName, repoName, ref</div>
        </div>

        <h2>GitHub Installations</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/installs</span>
            <div class="description">Get GitHub app installations for your account</div>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/github/:orgName/:repoName/:branch</span>
            <span class="badge">PRO</span>
            <div class="description">Get GitHub repository information for a specific branch</div>
        </div>

        <h2>Listeners</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/listeners</span>
            <div class="description">Get all listeners for your organization</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/listeners</span>
            <span class="badge">PRO</span>
            <div class="description">Create a new listener. Body: label, organizationId</div>
        </div>

        <div class="endpoint">
            <span class="method delete">DELETE</span>
            <span class="path">/listeners</span>
            <span class="badge">PRO</span>
            <div class="description">Delete a listener. Body: listenerId</div>
        </div>

        <h2>Monitorings</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/monitorings</span>
            <div class="description">Get all monitorings for your organization</div>
        </div>

        <h2>Organizations</h2>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/organizations</span>
            <div class="description">Create a new organization or join with invite code. Body: inviteCode (optional)</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/organizations/join</span>
            <div class="description">Join an organization using invite code. Requires: inviteCode</div>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/organizations/my</span>
            <div class="description">Get your organization details</div>
        </div>

        <h2>Organization Invites</h2>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/orgInvites</span>
            <span class="badge">PRO</span>
            <div class="description">Create an invite code for your organization</div>
        </div>

        <h2>Recipes</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/recipes</span>
            <div class="description">Get all recipes for your organization</div>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/recipes/orgName/:orgName</span>
            <div class="description">Get recipes filtered by GitHub organization name</div>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/recipes/repoName/:repoName</span>
            <div class="description">Get recipes filtered by repository name</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/recipes</span>
            <span class="badge">PRO</span>
            <div class="description">Create a new recipe. Requires: displayName and recipe configuration</div>
        </div>

        <div class="endpoint">
            <span class="method delete">DELETE</span>
            <span class="path">/recipes/:recipeId</span>
            <div class="description">Delete a recipe</div>
        </div>

        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/recipes/:recipeId</span>
            <span class="badge">PRO</span>
            <div class="description">Update a recipe. Body: recipeData</div>
        </div>

        <h2>Recurring Jobs</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/recurring</span>
            <div class="description">Get all recurring jobs for your organization</div>
        </div>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/recurring/:recurringJobId</span>
            <div class="description">Get all job executions for a specific recurring job</div>
        </div>

        <div class="endpoint">
            <span class="method put">PUT</span>
            <span class="path">/recurring/:recurringJobId/toggle</span>
            <div class="description">Toggle a recurring job on/off</div>
        </div>

        <h2>Shares</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/shares</span>
            <span class="badge">PRO</span>
            <div class="description">Get all shares for your organization</div>
        </div>

        <div class="endpoint">
            <span class="method post">POST</span>
            <span class="path">/shares</span>
            <span class="badge">PRO</span>
            <div class="description">Create a new share. Requires: jobId</div>
        </div>

        <div class="endpoint">
            <span class="method delete">DELETE</span>
            <span class="path">/shares/:shareId</span>
            <span class="badge">PRO</span>
            <div class="description">Delete a share</div>
        </div>

        <h2>Webhooks</h2>

        <div class="endpoint">
            <span class="method get">GET</span>
            <span class="path">/webhooks</span>
            <span class="badge">PRO</span>
            <div class="description">Get last five webhook jobs for your organization</div>
        </div>

        <div class="note">
            <strong>Note:</strong> Endpoints marked with <span class="badge">PRO</span> require a paid or trial organization plan.
        </div>
    </div>
</body>
</html>
  `;

  res.setHeader('Content-Type', 'text/html');
  return res.send(html);
});
