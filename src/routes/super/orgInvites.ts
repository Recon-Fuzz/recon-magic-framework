import express from "express";
import { Request, Response } from "express";
import {
  createInviteToOrg,
  deleteOrgInvite,
  fetchAllOrgInvites,
  fetchOrgInvitesForOrg,
} from "../../db/orgInvites";
import { requireSuperAdmin } from "../../middleware/auth";

const router = express.Router();
export default router;

// Get all orgInvites for the OrgId
router.get(
  "/:orgId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { orgId } = req.params;
    const allOrgInvites = await fetchOrgInvitesForOrg(orgId);

    return res.json({
      message: `All org invites for org id: ${orgId}`,
      data: allOrgInvites,
    });
  }
);

router.delete(
  "/:id",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { id } = req.params;

    await deleteOrgInvite(id);

    return res.json({
      message: `Deleted OrgInvite with id: ${id}`,
      data: {},
    });
  }
);

// Create an orgInvite for the OrgId
router.post("/:id", requireSuperAdmin, async (req: Request, res: Response) => {
  const { id } = req.params;

  const invite = await createInviteToOrg(id);
  return res.json({
    code: invite.id,
  });
});

// Get all orgInvites for all orgs
router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const allInvites = await fetchAllOrgInvites();

  return res.json({
    message: `All invites for all orgs`,
    data: allInvites,
  });
});

/** END SUPER ADMIN */
