import { Request, Response } from "express";
import express from "express";
import { requireSuperAdmin } from "../../middleware/auth";
import { fetchAllWebhooks } from "../../db/webhookJob";

const router = express.Router();
export default router;

router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const webhookJobs = await fetchAllWebhooks();

  return res.json({
    data: webhookJobs,
    message: "All webhooks",
  });
});

// TODO: Way to fetch with filters

// TODO: Way to push with filters
