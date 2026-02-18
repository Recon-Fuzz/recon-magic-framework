import prisma from "./client";

// Fetch all services
export async function unsafeFetchAllServices() {
  return await prisma.service.findMany({});
}

// Create Service
export async function unsafeCreateService(data: any) {
  return await prisma.service.create({
    data,
  });
}

// Delete Service
// NOTE: Deleting a service delets all the Live Monitoring tied to it
export async function unsafeDeleteService(serviceId: string) {
  return await prisma.service.delete({
    where: {
      id: serviceId,
    },
  });
}
