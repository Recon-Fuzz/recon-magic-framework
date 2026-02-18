import { Request, Response } from "express";

import express from "express";
import {  requireSuperAdmin } from "../../../middleware/auth";
import { createClaudeJob, deleteClaudeJob, fetchAllClaudeJobs, unsafeFetchClaudeJobById, updateClaudeJobStatus } from "../../../db/claudeJobs";
import { getCommitDiff } from "../../../github/claude-specific";


const router = express.Router();
export default router;


router.post("/", requireSuperAdmin, async (req: Request, res: Response) => {
    // NOTE: Duplicated code between here and claude/jobs.ts
    const { 
      organizationId,
  
      orgName,
      repoName,
      ref,
  
      workflowType,

      // TODO: Super can be allowed to do anything.
  
      // fuzzerName,
  
      // claudeOrgName,
      // claudeRepoName,
      // claudeRef,
  
      // claudePromptCommand,
      userHandles,
  
      optionalParams
     } = req.body;

  
     const fuzzerName = "echidna";
     const claudeOrgName = "Recon-Fuzz";
     const claudeRepoName = "ai-agent-primers";
     const claudeRef = "main";
  
     let claudePromptCommand = "";
     let workflowName = "Recon Magic";
  
     if(workflowType === "unit-0") {
      workflowName = `Unit Test - ${optionalParams.contractName}`;
      claudePromptCommand = `
  You are provided a repo at ./repo and custom agent definitions at ./.claude. 
  Please check the README in ./.claude then  Use ./repo as your working directory. 
  Run every agentic worfklow from unit-phase-0 to unit-phase-5 using the Task tool.
  Perform the agentic workflow on the contract ${optionalParams.contractName}.`;
     }
  
     if(workflowType === "phase-2") {
      workflowName = "Scaffold Coverage";
      claudePromptCommand = `
  You are provided a repo at ./repo and custom agent definitions at ./.claude. 
  Please check the README in ./.claude then
  Use ./repo as your working directory. 
  Run every agentic worfklow from coverage-phase-0 to coverage-phase-5 using the Task tool;
  `
    }

    if(workflowType === "properties-0") {
      workflowName = "Identify Invariants";
      claudePromptCommand = `
  You are provided a repo at ./repo and custom agent definitions at ./.claude. 
  Please check the README in ./.claude then
  Use ./repo as your working directory. 
  Run every agentic worfklow from properties-phase-0 to properties-phase-2 using the Task tool;
  `
    }
    
  if(workflowType === "audit-naive-0") {
    workflowName = "AI Powered Audit";
    claudePromptCommand = `
You are provided a repo at ./repo and custom agent definitions at ./.claude.
Please check the README in ./.claude then
Use ./repo as your working directory.
Run every agentic worfklow from audit-naive-phase-0 to audit-naive-phase-6 using the Task tool;
`
  }

  // coverage-v2 uses framework workflow mode
  let jobType = "directPrompt";

  if(workflowType === "scout-v2") {
    workflowName = "workflow-fuzzing-scouting";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "setup-v2") {
    workflowName = "workflow-fuzzing-setup";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "coverage-v2") {
    workflowName = "workflow-fuzzing-coverage";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  // Compositional workflows
  if(workflowType === "compose-setup-coverage") {
    workflowName = "compose-setup-coverage";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "compose-scout-setup-coverage") {
    workflowName = "compose-scout-setup-coverage";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "compose-setup-properties-coverage") {
    workflowName = "compose-setup-properties-coverage";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "compose-scout-setup-properties-coverage") {
    workflowName = "compose-scout-setup-properties-coverage";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "workflow-properties-full") {
    workflowName = "workflow-properties-full";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

  if(workflowType === "workflow-properties-full-opus") {
    workflowName = "workflow-properties-full-opus";
    jobType = "workflowName";
    claudePromptCommand = ""; // Not used in workflowName mode
  }

    // NOTE: Optional params are directory and preprocess, not currently used, spreading causes reverts
    // const enrichedOptionalParams = {
    //   ...(optionalParams || {})
    //  };

    const additionalData = {
      userHandles: userHandles, // TODO: Could we add even more?
      contractName: optionalParams?.contractName,
      foundryRoot: optionalParams?.foundryRoot,  // For monorepo support
      jobType,
    };
  
  
  
    // NOTE: Enforce by `requireProOrg`
    const job = await createClaudeJob(organizationId, orgName, repoName, ref, fuzzerName, claudeOrgName, claudeRepoName, claudeRef, claudePromptCommand, workflowName, {}, additionalData);
    return res.json({
      message: "Job created",
      data: job,
    });
  });

// GET: Returns list of jobs Claude needs to work on
router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
    const jobs = await fetchAllClaudeJobs();
    return res.json({
      message: "Here are the jobs",
      data: jobs,
    });
});

// NOTE: Different route!! Non conformant
router.get("/diff", requireSuperAdmin, async (req: Request, res: Response) => {
  const { jobId, organizationId } = req.body;
  const diff = await getCommitDiff(jobId, organizationId);
  return res.json({
    message: "Diff",
    data: diff,
  });
});
  
// NOTE: This must be put below as it uses :jobId
router.get("/:jobId", requireSuperAdmin, async (req: Request, res: Response) => {
    const { jobId } = req.params;
    const jobs = await unsafeFetchClaudeJobById(jobId);
    return res.json({
      message: "Here is the job",
      data: jobs,
    });
});




// Plausibly to gracefully stop a job
router.put("/status", requireSuperAdmin, async (req: Request, res: Response) => {
    const { jobId, status } = req.body;

    const job = await updateClaudeJobStatus(jobId, status);
    return res.json({
        message: "Job updated",
        data: job,
    });
});


// DELETE: Allows deleting a job
router.delete("/", requireSuperAdmin, async (req: Request, res: Response) => {
    const { jobId } = req.body;

    const job = await deleteClaudeJob(jobId);
    return res.json({
        message: "Job deleted",
        data: job,
    });
});