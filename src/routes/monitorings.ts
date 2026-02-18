// Fetch Live monitoring for an org
import { Request, Response } from "express";
import express from "express";
import { onlyLoggedIn, orgCheck } from "../middleware/auth";
import { fetchMonitoringsForOrgWithData } from "../lib/monitorings";

const router = express.Router();
export default router;

// Get all Recurring Jobs for the org
router.get("/", onlyLoggedIn, orgCheck, async (req: Request, res: Response) => {
  const resultsToSend = await fetchMonitoringsForOrgWithData(
    req.user.userData!.organizationId
  );

  return res.json({
    message: "All your org monitorings data",
    data: resultsToSend,
  });
});
