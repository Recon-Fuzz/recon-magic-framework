import { Request, Response } from "express";
import express from "express";
import { onlyLoggedIn, orgCheck } from "../middleware/auth";
import {
  fetchAllJobsGivenRecurringJob,
  fetchAllRecurringJobs,
  toggleRecurringJob,
} from "../db/recurring";
import { sanitizeInput } from "../middleware/sanitizer";

const router = express.Router();
export default router;

// Get all Recurring Jobs for the org
router.get("/", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  const foundJob = await fetchAllRecurringJobs(
    req.user.userData!.organizationId
  );
  return res.json({
    message: "All your org recurring jobs",
    data: foundJob,
  });
});

// Get all Job Data, in reverse order for a specific Recurring Job
router.get(
  "/:recurringJobId",
  onlyLoggedIn,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { recurringJobId } = req.params;

    const foundJobsData = await fetchAllJobsGivenRecurringJob(
      req.user.userData!.organizationId,
      recurringJobId
    );

    return res.json({
      message: "All jobs for your recurring job",
      data: foundJobsData,
    });
  }
);

router.put("/:recurringJobId/toggle", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  const { recurringJobId } = req.params;
  try {
    const updatedRecurringJob = await toggleRecurringJob(
      req.user.userData!.organizationId,
      recurringJobId
    );
    res.status(200).json({ message: "Recurring Job updated", data: updatedRecurringJob });
  } catch (err) {
    res.status(500).json({ message: "Error updating recurring job" });
  }
});
