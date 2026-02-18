import { Request, Response } from "express";
import express from "express";
import { onlyLoggedIn, requireProOrg, orgCheck } from "../middleware/auth";
import {
  createNewShare,
  deleteShareForOrg,
  fetchAllSharesForOrg,
  fetchOneShare,
} from "../db/shares";
import { getOneOrgJob } from "../db/jobs";
import { sanitizeInput } from "../middleware/sanitizer";

const router = express.Router();
export default router;

router.get(
  "/",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  async (req: Request, res: Response) => {
    const shares = await fetchAllSharesForOrg(req.user.userData!.organizationId);

    return res.json({
      message: "All Shares for your Org",
      data: shares,
    });
  }
);

// POST /JobId
router.post(
  "/",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { jobId } = req.body;

    try {
      // Find the job
      const job = await getOneOrgJob(req.user.userData!.organizationId, jobId);
      if (!job) {
        res.status(404);
        return res.json({
          message: `No job found for id: ${jobId}`,
          data: {},
        });
      }
      
      const createdShare = await createNewShare(
        req.user.userData!.organizationId,
        jobId
      );
      if (!createdShare) {
        res.status(404);
        return res.json({
          message: `No job found for id: ${jobId}`,
          data: {},
        });
      }
      return res.json({
        message: `Create new share with id: ${createdShare.id}`,
        data: createdShare,
      });
    } catch (error) {
      console.error("error creating share:", error);
      res.status(500);
      return res.json({ message: `Error creating share for job ${jobId}`, data: {} });
    }
  }
);

// DELETE /ShareID
router.delete(
  "/:shareId",
  onlyLoggedIn,
  requireProOrg,
  orgCheck,
  sanitizeInput,
  async (req: Request, res: Response) => {
    const { shareId } = req.params;

    try {
      const deletedShare = await deleteShareForOrg(
        req.user.userData!.organizationId,
        shareId
      );

      if (!deletedShare) {
        res.status(404);
        return res.json({
          message: `No Share found for id: ${shareId}`,
          data: {},
        });
      }

      return res.json({
        message: `No Longer sharing: ${deletedShare.id}`,
        data: deletedShare,
      });
    } catch (error) {
      console.error("error deleting share:", error);
      res.status(500);
      return res.json({ message: `Error deleting share ${shareId}`, data: {} });
    }
  }
);

// NOTE: Share is not logged in!
router.get("/:shareId", sanitizeInput, async (req: Request, res: Response) => {
  const { shareId } = req.params;

  const share = await fetchOneShare(shareId);

  if (!share?.jobId || !share?.organizationId) {
    res.status(404);
    return res.json({
      message: "No job for this share",
      data: {},
    });
  }

  // NOTE: We keep shares for old orgs, good behaviour from us
  // NOTE: We could write a script to delete some shares

  // Get org data
  const job = await getOneOrgJob(share.organizationId, share.jobId);

  return res.json({
    message: "One Share for your Org",
    data: {
      share,
      job,
    },
  });
});
