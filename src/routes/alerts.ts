import { Request, Response } from "express";
import express from "express";
import { onlyLoggedIn, orgCheck, requireProOrg } from "../middleware/auth";
import { createAlertForRecurringJobs } from "../db/recurring";
import {
  createAlertFromRecipeId,
  deleteAlert,
  editAlert,
  toggleAlert,
} from "../db/alerts";

const router = express.Router();
export default router;

// TODO 0XSI
// For later, not needed now
// router.post(
//   "/liveMonitoring",
//   onlyLoggedIn,
//   orgCheck,
//   async (req: Request, res: Response) => {
//     const { liveMonitoringId, threshold, webhookUrl } = req.body;
//     try {
//       const createdAlert = await createAlertForMonitoring(
//         liveMonitoringId,
//         parseInt(threshold),
//         webhookUrl
//       );
//       res.status(200).json({ message: "Alert created", data: createdAlert });
//     } catch (err) {
//       res.status(500).json({ message: "Error creating alert" });
//     }
//   }
// );

router.post(
  "/recurring",
  onlyLoggedIn,
  orgCheck,
  requireProOrg,
  async (req: Request, res: Response) => {
    const { recurringJobId, threshold, webhookUrl, telegramUsername, chatId } =
      req.body;
    const orgId = req.user.userData!.organizationId;

    try {
      const createdAlert = await createAlertForRecurringJobs(
        recurringJobId,
        parseInt(threshold),
        webhookUrl,
        orgId,
        telegramUsername,
        chatId
      );
      res.status(200).json({ message: "Alert created", data: createdAlert });
    } catch (err) {
      res.status(500).json({ message: "Error creating alert" });
    }
  }
);

router.post(
  "/recipe",
  onlyLoggedIn,
  orgCheck,
  requireProOrg,
  async (req: Request, res: Response) => {
    const { recipeId, threshold, webhookUrl, telegramUsername, chatId } =
      req.body;
    try {
      const createdAlert = await createAlertFromRecipeId(
        recipeId,
        parseInt(threshold),
        webhookUrl,
        telegramUsername,
        chatId
      );
      res.status(200).json({ message: "Alert created", data: createdAlert });
    } catch (err) {
      res.status(500).json({ message: "Error creating alert" });
    }
  }
);

router.delete(
  "/:alertId",
  onlyLoggedIn,
  orgCheck,
  async (req: Request, res: Response) => {
    const { alertId } = req.params;
    const orgId = req.user.userData!.organizationId;
    try {
      await deleteAlert(alertId, orgId);
      res.status(200).json({ message: "Alert deleted" });
    } catch (err) {
      console.log("error => ", err);
      res.status(500).json({ message: "Error deleting alert" });
    }
  }
);

router.put(
  "/edit/:alertId",
  onlyLoggedIn,
  orgCheck,
  requireProOrg,
  async (req: Request, res: Response) => {
    const { alertId, webhookUrl, threshold, telegramHandle, chatId } = req.body;
    const orgId = req.user.userData!.organizationId;

    try {
      await editAlert(
        alertId,
        orgId,
        webhookUrl,
        threshold,
        telegramHandle,
        chatId
      );
      res.status(200).json({ message: "Alert updated" });
    } catch (err) {
      res.status(500).json({ message: "Error updating alert" });
    }
  }
);

router.put(
  "/toggle/:alertId",
  onlyLoggedIn,
  orgCheck,
  async (req: Request, res: Response) => {
    const { alertId } = req.params;
    const orgId = req.user.userData!.organizationId;

    try {
      await toggleAlert(alertId, orgId);
      res.status(200).json({ message: "Alert toggled" });
    } catch (err) {
      res.status(500).json({ message: "Error updating alert" });
    }
  }
);
