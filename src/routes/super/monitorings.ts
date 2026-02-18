import { Request, Response } from "express";
import express from "express";

import { requireSuperAdmin } from "../../middleware/auth";
import {
  unsafeCreateMonitoring,
  unsafeDeleteMonitoring,
  unsafeFetchAllMonitorings,
} from "../../db/monitorings";
import { fetchMonitoringsForOrgWithData } from "../../lib/monitorings";

const router = express.Router();
export default router;

// Get all monitorings in the system
router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const foundMonitorings = await unsafeFetchAllMonitorings();

  return res.json({
    message: "All Monitorings",
    data: foundMonitorings,
  });
});

// Get any monitoring result for a specific org
// TODO: Fetch one, then get the data
router.get(
  "/:organizationId",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { organizationId } = req.params;

    const foundMonitorings = await fetchMonitoringsForOrgWithData(
      organizationId
    );

    return res.json({
      message: `All Monitorings for the organization ${organizationId}`,
      data: foundMonitorings,
    });
  }
);

// NOTE: UNSANITIZED!
router.post("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const newMonitoring = await unsafeCreateMonitoring(req.body);

  return res.json({
    message: "Created new monitoring",
    data: newMonitoring,
  });
});

// Delete a monitoring
router.delete(
  "/:id",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { id } = req.params;
    const deletedMonitoring = await unsafeDeleteMonitoring(id);

    return res.json({
      message: "Deleted monitoring",
      data: deletedMonitoring,
    });
  }
);
