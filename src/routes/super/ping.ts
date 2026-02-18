import express from "express";
import { Request, Response } from "express";
import { requireSuperAdmin } from "../../middleware/auth";

const router = express.Router();
export default router;

// This route exist to make sure a user is a super admin without performing any action
router.get(
  "/",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    console.log("here in ping");
    res.status(200);
    return res.json({
      message: "pong",
    });
  });
