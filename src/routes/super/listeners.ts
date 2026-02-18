import { Request, Response } from "express";
import express from "express";
import { requireSuperAdmin } from "../../middleware/auth";
import { fetchAllOrgListeners } from "../../db/listener";

const router = express.Router();
export default router;

router.get(
  "/",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const listeners = await fetchAllOrgListeners();
    return res.json({
      message: `All listeners`,
      data: listeners,
    });
  }
);
