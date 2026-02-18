-- CreateTable
CREATE TABLE "Job" (
    "id" SERIAL NOT NULL,
    "orgName" TEXT NOT NULL,
    "repoName" TEXT NOT NULL,
    "branch" TEXT NOT NULL,
    "status" TEXT NOT NULL,

    CONSTRAINT "Job_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ABIData" (
    "id" SERIAL NOT NULL,
    "identifier" TEXT NOT NULL,
    "commit" TEXT NOT NULL,
    "abiData" JSONB NOT NULL,

    CONSTRAINT "ABIData_pkey" PRIMARY KEY ("id")
);
