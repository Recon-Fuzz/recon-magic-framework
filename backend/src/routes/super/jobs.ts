import express from "express";
import { Request, Response } from "express";
import {
  createJob,
  deleteAJob,
  fetchAllJobs,
  fetchOneJob,
  getAllQueuedJob,
  getCountOfRunningJobs,
  stopJob,
  updateJobArbitrary,
} from "../../db/jobs";
import { requireSuperAdmin } from "../../middleware/auth";
import { runStarterLoop } from "../..";
import { getMetaData } from "../../utils/metadata";

const router = express.Router();
export default router;
/// @audit NOTE: Super admin can specify any preprocess!

/**
 * /super/jobs/
 */

router.get("/runningcount", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const runningJobs = await getCountOfRunningJobs();
    res.status(200).json({
      message: "All Running Jobs",
      count: runningJobs,
    });
  } catch (err) {
    res.status(500).json({
      message: "Something went wrong",
      data: null,
    });
  }
});

router.get(
  "/queued",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    try {
      const queuedJobs = await getAllQueuedJob();
      res.status(200).json({
        message: "All Queued Jobs",
        data: queuedJobs,
      });
    } catch (err) {
      return res.status(500).json({
        message: "Something went wrong",
        data: null,
      });
    }
  }
);

router.get(
  "/:jobId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;

    const found = await fetchOneJob(jobId);

    return res.json({
      message: `Data for job with id: ${jobId}`,
      data: found,
    });
  }
);

router.put(
  "/requeue/:jobId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;

    const oldJob = await fetchOneJob(jobId);

    const newJob = await updateJobArbitrary(
      oldJob.id,
      oldJob?.arbitraryCommand ? oldJob.arbitraryCommand : ""
    );

    // await runStarterLoop(); /// @audit Let's use the Cron to prevent double queueing

    return res.json({
      message: `Requeued Job for: ${newJob.id}`,
      data: newJob,
    });
  }
);

router.put(
  "/arbitrary/:jobId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;

    const { arbitraryCommand } = req.body;

    const oldJob = await fetchOneJob(jobId);

    const newJob = await updateJobArbitrary(oldJob.id, arbitraryCommand);

    // Do we need orgId, repoName and fuzzer?
    // No, because if we make a mistake we may expose client data to another orgId
    // Thus, we keep org name and repo name the same. If these change then the user can requeue a new job with no issues.

    // await runStarterLoop(); /// @audit Let's use the Cron to prevent double queueing

    return res.json({
      message: `Updated Arbitrary Command for: ${newJob.id}`,
      data: newJob,
    });
  }
);

// Allows a super user to stop jobs gracefully
router.put(
  "/stop/:jobId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;

    // Update the DB
    const job = await stopJob(jobId);

    return res.json({
      message: `The job has been stopped`,
      data: job,
    });
  }
);

// Requeue jobs with different params
router.post(
  "/clone/:jobId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;

    const {
      ref,
      directory,
      duration,
      fuzzerArgs,
      preprocess,
      arbitraryCommand,
      label,
    } = req.body;

    const oldJob = await fetchOneJob(jobId);

    let suppliedMetadata: any = {
      startedBy: "admin",
      method: "route",
    };

    let metadata;
    try {
      metadata = await getMetaData(
        suppliedMetadata,
        oldJob.orgName,
        oldJob.repoName,
        ref
      );
    } catch {
      console.log("Job: couldn't create access token");
    }

    const newJob = await createJob(
      oldJob.organizationId,
      oldJob.orgName,
      oldJob.repoName,
      ref! || oldJob.ref,
      oldJob.fuzzer,
      label,
      {
        fuzzerArgs: fuzzerArgs! || oldJob.fuzzerArgs,
        directory: directory || oldJob.directory,
        duration: duration || oldJob.duration,
        preprocess: preprocess! || oldJob.preprocess,
        arbitraryCommand,
        metadata: metadata ? metadata : suppliedMetadata, // there will always be metadata in this case
      }
    );

    // Do we need orgId, repoName and fuzzer?
    // No, because if we make a mistake we may expose client data to another orgId
    // Thus, we keep org name and repo name the same. If these change then the user can requeue a new job with no issues.

    // await runStarterLoop(); /// @audit Let's use the Cron to prevent double queueing

    return res.json({
      message: `Created Copy of job with id: ${newJob.id}`,
      data: newJob,
    });
  }
);

router.delete(
  "/:jobId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { jobId } = req.params;
    try {
      await fetchOneJob(jobId);
    } catch (e) {
      return res.status(404).json({
        message: `Job not found`,
        data: null,
      });
    }

    try {
      const deleteJob = await deleteAJob(jobId);

      return res.json({
        message: `Delete job with id ${jobId}`,
        data: deleteJob,
      });
    } catch (err) {
      return res.status(500).json({
        message: `Error deleting job`,
        data: null,
      });
    }
  }
);

router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const allJobs = await fetchAllJobs();

  return res.json({
    message: `Data of all jobs`,
    data: allJobs,
  });
});

router.post(
  "/medusa",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    // Get params from Body
    const {
      orgName,
      repoName,
      ref,
      orgId,
      directory,
      duration,
      preprocess,
      fuzzerArgs,
      arbitraryCommand,
      label,
    } = req.body;

    let suppliedMetadata: any = {
      startedBy: "admin",
      method: "route",
    };

    let metadata;
    // Fetch the token
    try {
      metadata = await getMetaData(suppliedMetadata, orgName, repoName, ref);
    } catch {
      console.log("Job: couldn't create access token");
    }

    const job = await createJob(
      orgId,
      orgName,
      repoName,
      ref,
      "MEDUSA",
      label,
      {
        directory,
        duration,
        preprocess,
        arbitraryCommand,
        fuzzerArgs,
        metadata: metadata ? metadata : suppliedMetadata, // there will always be metadata in this case
      }
    );

    return res.json({
      message: `Created a Medusa Job for ${orgId}`,
      data: job,
    });
  }
);

router.post(
  "/echidna",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    // Get params from Body
    const {
      orgName,
      repoName,
      ref,
      orgId,
      directory,
      duration,
      preprocess,
      arbitraryCommand,
      fuzzerArgs,
      label,
    } = req.body;

    let suppliedMetadata: any = {
      startedBy: "admin",
      method: "route",
    };

    let metadata;
    // Fetch the token
    try {
      metadata = await getMetaData(suppliedMetadata, orgName, repoName, ref);
    } catch {
      console.log("Job: couldn't create access token");
    }

    const job = await createJob(
      orgId,
      orgName,
      repoName,
      ref,
      "MEDUSA",
      label,
      {
        directory,
        duration,
        preprocess,
        arbitraryCommand,
        fuzzerArgs,
        metadata: metadata ? metadata : suppliedMetadata, // there will always be metadata in this case
      }
    );

    return res.json({
      message: `Created a Medusa Job for ${orgId}`,
      data: job,
    });
  }
);

router.post(
  "/foundry",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    // Get params from Body
    const {
      orgName,
      repoName,
      ref,
      orgId,
      directory,
      duration,
      preprocess,
      arbitraryCommand,
      fuzzerArgs,
      label,
    } = req.body;

    let suppliedMetadata: any = {
      startedBy: "admin",
      method: "route",
    };

    let metadata;
    // Fetch the token
    try {
      metadata = await getMetaData(suppliedMetadata, orgName, repoName, ref);
    } catch {
      console.log("Job: couldn't create access token");
    }

    const job = await createJob(
      orgId,
      orgName,
      repoName,
      ref,
      "FOUNDRY",
      label,
      {
        directory,
        duration,
        preprocess,
        arbitraryCommand,
        fuzzerArgs,
        metadata: metadata ? metadata : suppliedMetadata, // there will always be metadata in this case
      }
    );

    return res.json({
      message: `Created a Foundry Job for ${orgId}`,
      data: job,
    });
  }
);
