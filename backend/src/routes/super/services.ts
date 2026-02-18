import { Request, Response } from "express";
import express from "express";

import { requireSuperAdmin } from "../../middleware/auth";
import {
  unsafeCreateService,
  unsafeDeleteService,
  unsafeFetchAllServices,
} from "../../db/services";

const router = express.Router();
export default router;

// Get all services in the system
router.get("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const foundServices = await unsafeFetchAllServices();

  return res.json({
    message: "All services",
    data: foundServices,
  });
});

// NOTE: UNSANITIZED!
router.post("/", requireSuperAdmin, async (req: Request, res: Response) => {
  const foundServices = await unsafeCreateService(req.body);

  return res.json({
    message: "Created new service",
    data: foundServices,
  });
});

// Delete a service
// NOTE: Deleting a service will delete the corresponding Monitoring!
router.delete(
  "/:id",
  requireSuperAdmin,
  async (req: Request, res: Response) => {
    const { id } = req.params;
    const foundServices = await unsafeDeleteService(id);

    return res.json({
      message: "Deleted service",
      data: foundServices,
    });
  }
);
