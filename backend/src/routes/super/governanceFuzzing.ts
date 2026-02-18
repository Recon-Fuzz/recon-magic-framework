import { Request, Response } from "express";
import express from "express";
import {
  requireSuperAdmin,
} from "../../middleware/auth";

import {
  getAllActiveGovFuzzing,
} from "../../db/govFuzzing";

const router = express.Router();
export default router;


router.get(
  "/allActive",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const jobs = await getAllActiveGovFuzzing();
    res.status(200).json({ message: "Jobs found", data: jobs });
  }
);
