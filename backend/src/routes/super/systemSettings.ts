import express from "express";
import { Request, Response } from "express";
import { requireSuperAdmin } from "../../middleware/auth";
import { isMagicJobsPaused, setMagicJobsPaused } from "../../db/systemSettings";

const router = express.Router();
export default router;

// GET /super/system/magic-jobs-paused - Check if magic jobs are paused
router.get(
  "/magic-jobs-paused",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const paused = await isMagicJobsPaused();
    return res.json({
      message: "Magic jobs pause status",
      data: { paused },
    });
  }
);

// POST /super/system/magic-jobs-pause - Pause magic jobs processing
router.post(
  "/magic-jobs-pause",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    await setMagicJobsPaused(true);
    console.log(`[SystemSettings] Magic jobs PAUSED by super admin`);
    return res.json({
      message: "Magic jobs processing paused",
      data: { paused: true },
    });
  }
);

// POST /super/system/magic-jobs-unpause - Unpause magic jobs processing
router.post(
  "/magic-jobs-unpause",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    await setMagicJobsPaused(false);
    console.log(`[SystemSettings] Magic jobs UNPAUSED by super admin`);
    return res.json({
      message: "Magic jobs processing resumed",
      data: { paused: false },
    });
  }
);
