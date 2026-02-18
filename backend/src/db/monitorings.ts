import prisma from "./client";

export async function unsafeCreateMonitoring(data: any) {
  return await prisma.liveMonitoring.create({
    data,
  });
}

export async function unsafeUpdateMonitoring(monitoringId: string, data: any) {
  return await prisma.liveMonitoring.update({
    where: {
      id: monitoringId,
    },
    data,
  });
}

export async function unsafeDeleteMonitoring(monitoringId: string) {
  return await prisma.liveMonitoring.delete({
    where: {
      id: monitoringId,
    },
  });
}

export async function unsafeFetchAllMonitorings() {
  return await prisma.liveMonitoring.findMany({
    orderBy: {
      updatedAt: "desc",
    },
  });
}

export async function fetchMonitoringsForOrg(organizationId: string) {
  return await prisma.liveMonitoring.findMany({
    where: {
      organizationId,
    },
    include: {
      service: true,
    },
    orderBy: {
      updatedAt: "desc",
    },
  });
}
