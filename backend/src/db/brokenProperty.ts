import prisma from "./client";

export const getBrokenPropertiesForJob = async (jobId: string) => {
  return await prisma.brokenProperty.findMany({
    where: {
      jobId: jobId,
    },
  });
};

export const createBrokenProperty = async (
  jobId: string,
  brokenProperty: string,
  traces: string
) => {
  // TODO 0XSI
  // Check if the exact same brokenProp exist first maybe ?
  return await prisma.brokenProperty.create({
    data: {
      jobId: jobId,
      brokenProperty: brokenProperty,
      traces: traces,
    },
  });
};

export const updateJobRunData = async (
  jobId: string,
  testsDuration: string,
  testsCoverage: number,
  testsFailed: number,
  testsPassed: number,
  numberOfTests: number
) => {
  return await prisma.job.update({
    where: {
      id: jobId,
    },
    data: {
      testsDuration: testsDuration,
      testsCoverage: testsCoverage,
      testsFailed: testsFailed,
      testsPassed: testsPassed,
      numberOfTests: numberOfTests,
    },
  });
};
