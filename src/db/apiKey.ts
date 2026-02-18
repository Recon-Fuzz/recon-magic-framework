import prisma from "./client";

export async function createApiKey(userId: string, canWrite: boolean, label?: string) {
  return await prisma.apiKey.create({
    data: { 
      userId: userId,
      enabled: true,
      canWrite: canWrite,
      label: label || "",
    },
  });
}

export async function unsafeFetchAllApiKeys() {
  // Find all Org Listeners, since we delete them on success
  const apiKeys = await prisma.apiKey.findMany({
    where: {},
    orderBy: {
      createdAt: "desc", // Latest by definition
    },
  });

  return apiKeys.map((apiKey) => {
    if (apiKey.id) {
      apiKey.id = "api_" + apiKey.id;
    }
    return apiKey;
  });
}

export async function fetchApiKeysByUserId(userId: string) {
  const apiKeys = await prisma.apiKey.findMany({
    where: { userId: userId },
    orderBy: {
      createdAt: "desc", // Latest by definition
    },
  });

  return apiKeys.map((apiKey) => {
    if (apiKey.id) {
      apiKey.id = "api_" + apiKey.id;
    }
    return apiKey;
  });
}

export async function fetchApiKeyById(id: string) {
  const apiKeyId = id.split("api_")[1];
  const apiKey = await prisma.apiKey.findUnique({
      where: { id: apiKeyId },
    });

  if (apiKey?.id) {
    apiKey.id = "api_" + apiKey.id;
  }

  return apiKey;
}

export async function disableApiKey(apiKeyId: string, userId: string) {
  const filteredApiKeyId = apiKeyId.split("api_")[1];
  const apiKey = await prisma.apiKey.update({
    where: { id: filteredApiKeyId },
    data: { enabled: false, userId: userId },
  });

  if (apiKey?.id) {
    apiKey.id = "api_" + apiKey.id;
  }

  return apiKey;
}


export async function unsafeDeleteApiKey(apiKeyId: string) {
  const filteredApiKeyId = apiKeyId.split("api_")[1];
  const apiKey = await prisma.apiKey.delete({
    where: {
      id: filteredApiKeyId,
    },
  });

  if (apiKey?.id) {
    apiKey.id = "api_" + apiKey.id;
  }

  return apiKey;
}

export async function deleteApiKey(apiKeyId: string, userId: string) {
  const filteredApiKeyId = apiKeyId.split("api_")[1];
  const apiKey = await prisma.apiKey.delete({
    where: {
      id: filteredApiKeyId,
      userId: userId,
    },
  });

  if (apiKey?.id) {
    apiKey.id = "api_" + apiKey.id;
  }

  return apiKey;
}
