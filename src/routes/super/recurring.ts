import { Request, Response } from "express";
import express from "express";

import {
  superCreateAlertForRecurringJobs,
  unsafeCreateRecurringJobs,
  unsafeDeleteOneRecurringJob,
  unsafeFetchAllRecurringJobs,
} from "../../db/recurring";
import { requireSuperAdmin } from "../../middleware/auth";
import { superDeleteAlert, superToggleAlert } from "../../db/alerts";

const router = express.Router();
export default router;

// Get all Recurring Jobs for the org
router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const foundJob = await unsafeFetchAllRecurringJobs();

  return res.json({
    message: "All recurring jobs",
    data: foundJob,
  });
});

// Get all Job Data, in reverse order for a specific Recurring Job
router.post("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const { organizationId, recipeId, label, frequencyInSeconds } = req.body;

  const createdRecurringJobId = await unsafeCreateRecurringJobs(
    organizationId,
    recipeId,
    label,
    frequencyInSeconds
  );

  return res.json({
    message: "Created Recurring Job",
    data: createdRecurringJobId,
  });
});

router.post(
  "/alert/:recurringJobId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { recurringJobId } = req.params;
    const { threshold, webhookUrl } = req.body;
    try {
      const createdAlert = await superCreateAlertForRecurringJobs(
        recurringJobId,
        threshold,
        webhookUrl
      );
      res.status(200).json({ message: "Alert created", data: createdAlert });
    } catch (err) {
      res.status(500).json({ message: "Error creating alert" });
    }
  }
);

router.delete(
  "/alert/:alertId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { alertId } = req.params;
    try {
      const deletedAlert = await superDeleteAlert(alertId);
      res.status(200).json({ message: "Alert deleted", data: deletedAlert });
    } catch (err) {
      res.status(500).json({ message: "Error deleting alert" });
    }
  }
);


router.put(
  "/alert/:alertId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { alertId } = req.params;
    try {
      const toggleAlert = await superToggleAlert(alertId);
      res.status(200).json({ message: "Alert toggled", data: toggleAlert });
    } catch (err) {
      res.status(500).json({ message: "Error toggling alert" });
    }
  }
);

router.delete(
  "/:recurringJobId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { recurringJobId } = req.params;

    const deletedRecurringJobId = await unsafeDeleteOneRecurringJob(
      recurringJobId
    );

    return res.json({
      message: "Delete Recurring Job",
      data: deletedRecurringJobId,
    });
  }
);
