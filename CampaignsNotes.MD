# Test Flow

-> Create new account
-> Get Pro

// Test webhooks
-> Get webhook for Commit
-> Get webhook for PR

-> Create Recipe
-> Create Campaign

// Test Campaigns
-> Get webhook for Commit
-> Get webhook for PR

# PR Logic

"event":"pull_request", = Push to PR

action: 'opened', = Created a PR

payload.pull_request.id // Id to comment

// Origin / Head
Payload.head.ref = Branch / Commit
Payload.head.repo.name = recon-demo-3 (RepoName)
Payload.head.repo.full_name = GalloDaSballo/recon-demo-3 (OrgName/RepoName)

// Target / Base
Payload.base.ref = Branch / Commit
Payload.base.repo.name = recon-demo-3 (RepoName)
Payload.base.repo.full_name = GalloDaSballo/recon-demo-3 (OrgName/RepoName)

-----
// Run Job
// With Issue ID
// On End
// Comment to Issue ID
// For Demo, let's just link to Running Job (private)
-----


# UI

-> Create Recipe
-> Create Campaign
 - on PR to Branch X

--
Org
Repo
Branch
Recipe
--

# Webhooks

-> on webhook
-> Register the webhook (separate logic)
-> Check the Org, Repo and Branch (already written)
-> Given the initiator (TODO?), fetch the Campaign
-> If a Campaign is present, create a Job and add the IssueID to it


---
# Separate page to run with Recipe
Run with Recipe page

# Webhook Feature
-> Ui for Register Webhook should be:
- Run with Recipe (select recipe)

---





# NICE TO HAVE

Job queued from
-> SHA

If job created within an hour, and same SHA

On automatic, skip or smth