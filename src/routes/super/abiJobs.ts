import express from "express";
import { Request, Response } from "express";

import { fetchAllAbiJobs, reQueueJob } from "../../db/abiJobs";
import { runWorkerLoop } from "../..";
import { requireSuperAdmin } from "../../middleware/auth";
import { nodeEnv } from "../../config/config";

const router = express.Router();
export default router;

/**
 * /super/abiJobs/
 */

router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const allJobs = await fetchAllAbiJobs();

  return res.json({
    message: `Data of all jobs`,
    data: allJobs,
  });
});

router.post(
  "/requeue",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    if (nodeEnv != "development") {
      throw Error("Only in debugging!");
    }

    const { jobId } = req.body;

    const job = await reQueueJob(jobId);

    runWorkerLoop();

    return res.json({
      message: `Set Job Back to Start`,
      data: job,
    });
  }
);
