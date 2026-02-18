import express from "express";
import { Request, Response } from "express";
import { changeUserOrg } from "../../db/users";
import { deleteOrganizationIfEmpty, renameOrganization } from "../../db/organizations";
import { requireSuperAdmin } from "../../middleware/auth";
import { getOrgInfo } from "../../db/jobs";

const router = express.Router();
export default router;

/** SUPER ADMIN */
// SUPER ADMIN
router.post(
  "/super/adduser/",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { userId, organizationId } = req.body;
    const result = await changeUserOrg(userId, organizationId);

    res.send(result);
  }
);

// SUPER ADMIN
router.delete(
  "/super/:organizationId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    // Delete a new ORG
    const { organizationId } = req.params;

    try {
      const result = await deleteOrganizationIfEmpty(organizationId);
      if (result === null) {
        res.status(400);
        return res.json({ message: "Organization has users, cannot delete" });
      }
      return res.json({ message: "Organization deleted", data: result });
    } catch (e) {
      res.status(500);
      if (e instanceof Error) {
        return res.json({ message: e.message });
      } else {
        return res.json({ message: "Something went wrong" });
      }
    }
  }
);

router.put("/switchorg/:organizationId", requireSuperAdmin, async (req: Request, res: Response) => {
  const { organizationId } = req.params;
  const { userId } = req.body;

  try {
    const data = await changeUserOrg(userId, organizationId);
    res.status(200);
    res.json({data: data, message:"successfuly changed org"});
  } catch(err) {
    res.status(500);
    if (err instanceof Error) {
      return res.json({ message: err.message });
    } else {
      return res.json({ message: "Something went wrong" });
    }
  }
});

router.get("/getorgsinfo/:organizationId", requireSuperAdmin, async (req: Request, res: Response) => {
  try {
    const data = await getOrgInfo(req.params.organizationId);
    res.status(200);
    res.json(data);
  } catch(err) {
    res.status(500);
    if (err instanceof Error) {
      return res.json({ message: err.message });
    } else {
      return res.json({ message: "Something went wrong" });
    }
  }
});

router.post("/rename", requireSuperAdmin, async (req: Request, res: Response) => {
  const { organizationId, newName } = req.body;

  if (!organizationId || typeof organizationId !== "string") {
    res.status(400);
    return res.json({ message: "Organization ID is required" });
  }

  if (!newName || typeof newName !== "string" || newName.trim().length === 0) {
    res.status(400);
    return res.json({ message: "New name is required and must be a non-empty string" });
  }

  try {
    const updatedOrg = await renameOrganization(organizationId, newName.trim());
    res.status(200);
    res.json({ data: updatedOrg, message: "Organization renamed successfully" });
  } catch(err) {
    res.status(500);
    if (err instanceof Error) {
      return res.json({ message: err.message });
    } else {
      return res.json({ message: "Failed to rename organization" });
    }
  }
});

/** END TODO: SUPER ADMIN */
