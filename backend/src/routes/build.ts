import { Request, Response } from "express";
import express from "express";
import { onlyLoggedIn, orgCheck } from "../middleware/auth";
import { sanitizeInput } from "../middleware/sanitizer";

const router = express.Router();
export default router;

router.post("/", onlyLoggedIn, orgCheck, sanitizeInput, async (req: Request, res: Response) => {
  return res.status(400).json({ message: "Build is disabled", data: {} });
});
