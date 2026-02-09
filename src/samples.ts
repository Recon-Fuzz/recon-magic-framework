import 'tsconfig-paths/register'
import prisma from "./services/prisma";

async function main(organizationName: string) {
  const organization = await prisma.organization.findFirstOrThrow({
    where: {
      name: organizationName,
    },
  });
  const job = await prisma.job.create({
    data: {
      organizationId: organization.id,
      fuzzer: "ECHIDNA",
      status: "STARTED",
      orgName: "aviggiano",
      repoName: "shrinking-mwe",
      ref: "main",
    },
  });
  console.log(job);
}

main("aviggiano");
