import prisma from "./client";

export const deleteAlert = async (alertId: string, orgId: string) => {
  const alertToDelete = await prisma.alert.findFirstOrThrow({
    where: {
      id: alertId,
    },
  });

  if (alertToDelete.recipeId) {
    const recipe = await prisma.recipe.findFirstOrThrow({
      where: {
        id: alertToDelete.recipeId,
      },
    });
    if (recipe.organizationId !== orgId) {
      throw new Error("Alert does not belong to the organization");
    }
  }

  if (alertToDelete.recurringJobId) {
    const recurringJob = await prisma.recurringJob.findFirstOrThrow({
      where: {
        id: alertToDelete.recurringJobId,
      },
    });

    if (recurringJob.organizationId !== orgId) {
      throw new Error("Alert does not belong to the organization");
    }
  }

  try {
    await prisma.alert.delete({
      where: {
        id: alertId,
      },
    });
  } catch (err) {
    console.log(err);
    throw new Error("Failed to delete alert");
  }
};

export const superDeleteAlert = async (alertId: string) => {
  try {
    await prisma.alert.delete({
      where: {
        id: alertId,
      },
    });
  } catch (err) {
    console.log(err);
    throw new Error("Failed to delete alert");
  }
};

export const toggleAlert = async (alertId: string, orgId: string) => {
  const alertToDelete = await prisma.alert.findFirstOrThrow({
    where: {
      id: alertId,
    },
  });

  if (alertToDelete.recipeId) {
    const recipe = await prisma.recipe.findFirstOrThrow({
      where: {
        id: alertToDelete.recipeId,
      },
    });
    if (recipe.organizationId !== orgId) {
      throw new Error("Alert does not belong to the organization");
    }
  }

  if (alertToDelete.recurringJobId) {
    const recurringJob = await prisma.recurringJob.findFirstOrThrow({
      where: {
        id: alertToDelete.recurringJobId,
      },
    });

    if (recurringJob.organizationId !== orgId) {
      throw new Error("Alert does not belong to the organization");
    }
  }

  try {
    const alert = await prisma.alert.findFirstOrThrow({
      where: {
        id: alertId,
      },
    });
    if (!alert) {
      throw new Error("Alert not found");
    }

    const updatedAlert = await prisma.alert.update({
      where: {
        id: alertId,
      },
      data: {
        active: !alert.active,
      },
    });

    return updatedAlert;
  } catch (err) {
    console.log(err);
    throw new Error("Failed to toggle alert");
  }
};

export const editAlert = async (
  alertId: string,
  orgId: string,
  webhookUrl: string,
  threshold: string,
  telegramUsername?: string,
  chatId?: number
) => {
  const alertToDelete = await prisma.alert.findFirstOrThrow({
    where: {
      id: alertId,
    },
  });

  if (alertToDelete.recipeId) {
    const recipe = await prisma.recipe.findFirstOrThrow({
      where: {
        id: alertToDelete.recipeId,
      },
    });
    if (recipe.organizationId !== orgId) {
      throw new Error("Alert does not belong to the organization");
    }
  }

  if (alertToDelete.recurringJobId) {
    const recurringJob = await prisma.recurringJob.findFirstOrThrow({
      where: {
        id: alertToDelete.recurringJobId,
      },
    });

    if (recurringJob.organizationId !== orgId) {
      throw new Error("Alert does not belong to the organization");
    }
  }

  try {
    const alert = await prisma.alert.findFirstOrThrow({
      where: {
        id: alertId,
      },
    });
    if (!alert) {
      throw new Error("Alert not found");
    }

    const updatedAlert = await prisma.alert.update({
      where: {
        id: alertId,
      },
      data: {
        webhookUrl: webhookUrl,
        threshold: parseInt(threshold),
        telegramHandle: telegramUsername ? telegramUsername : null,
        telegramChatId: chatId ? chatId : null,
      },
    });

    return updatedAlert;
  } catch (err) {
    console.log(err);
    throw new Error("Failed to toggle alert");
  }
};

export const superToggleAlert = async (alertId: string) => {
  try {
    const alert = await prisma.alert.findFirstOrThrow({
      where: {
        id: alertId,
      },
    });
    if (!alert) {
      throw new Error("Alert not found");
    }

    const updatedAlert = await prisma.alert.update({
      where: {
        id: alertId,
      },
      data: {
        active: !alert.active,
      },
    });

    return updatedAlert;
  } catch (err) {
    console.log(err);
    throw new Error("Failed to toggle alert");
  }
};

export const getAlertById = async (alertId: string) => {
  try {
    return await prisma.alert.findFirstOrThrow({
      where: {
        id: alertId,
      },
    });
  } catch (err) {
    console.log(err);
    throw new Error("Failed to get alert");
  }
};

export const createAlertFromRecurringJobId = async (
  recurringJobId: string,
  threshold: number,
  webhookUrl: string,
  telegramUsername?: string,
  chatId?: number
) => {
  return await prisma.alert.create({
    data: {
      recurringJobId,
      threshold,
      webhookUrl,
      telegramHandle: telegramUsername,
      telegramChatId: chatId,
    },
  });
};

export const createAlertFromRecipeId = async (
  recipeId: string,
  threshold: number,
  webhookUrl: string,
  telegramUsername?: string,
  telegramChatId?: number
) => {
  return await prisma.alert.create({
    data: {
      recipeId,
      threshold,
      webhookUrl,
      telegramHandle: telegramUsername,
      telegramChatId,
    },
  });
};
