import { Request, Response } from "express";

import express from "express";
import { onlyLoggedIn, orgCheck } from "../middleware/auth";
import { fetchAllAbiJobsFromOrg, fetchOneAbiJobWithOrg } from "../db/abiJobs";
import { sanitizeInput } from "../middleware/sanitizer";

const router = express.Router();
export default router;

router.get("/", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  try {
    const foundJob = await fetchAllAbiJobsFromOrg(
      req.user.userData!.organizationId
    );
    if (!foundJob) {
      res.status(404);
      return res.json({ message: "No data found for abi jobs", data: {} });
    }
    return res.json({
      message: `Fetch all jobs for org: ${req.user.userData!.organizationId}`,
      data: foundJob,
    });
  } catch (error) {
    console.error("error getting the abi jobs:", error);
    res.status(500);
    return res.json({ message: "Error fetching all abi jobs", data: {} });
  }

});

// Given an ID, return it if it belongs to your org
router.get("/:id", onlyLoggedIn, orgCheck, sanitizeInput, async (req: Request, res: Response) => {
  const { id } = req.params;

  const foundJob = await fetchOneAbiJobWithOrg(
    id,
    req.user.userData!.organizationId
  );

  if (!foundJob) {
    res.status(404);
    return res.json({ message: `No data found for job ${id}`, data: {} });
  }
  return res.json({ message: `Data for job with id: ${id}`, data: foundJob });
});
