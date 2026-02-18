import { Request, Response } from "express";
import express from "express";
import { requireSuperAdmin } from "../../middleware/auth";
import { createNewShare, deleteShare, fetchAllShares } from "../../db/shares";

const router = express.Router();
export default router;

router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const shares = await fetchAllShares();

  return res.json({
    message: "All Shares in the system",
    data: shares,
  });
});

// Create a Share for any org
router.post("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const { jobId, organizationId } = req.body;

  const createdShare = await createNewShare(organizationId, jobId);

  return res.json({
    message: `Create new share with id: ${createdShare.id}`,
    data: createdShare,
  });
});

// DELETE /ShareID
router.delete(
  "/:shareId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { shareId } = req.params;

    const deletedShare = await deleteShare(shareId);

    return res.json({
      message: `No Longer sharing: ${deletedShare.id}`,
      data: deletedShare,
    });
  }
);
