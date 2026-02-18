import prisma from "./client";

// System setting keys
export const SETTING_KEYS = {
  MAGIC_JOBS_PAUSED: "magic_jobs_paused",
} as const;

/**
 * Get a system setting value by key.
 * Returns null if the setting doesn't exist.
 */
export async function getSetting(key: string): Promise<string | null> {
  const setting = await prisma.systemSettings.findUnique({
    where: { key },
  });
  return setting?.value ?? null;
}

/**
 * Set a system setting value.
 * Creates the setting if it doesn't exist, updates if it does.
 */
export async function setSetting(key: string, value: string): Promise<void> {
  await prisma.systemSettings.upsert({
    where: { key },
    update: { value },
    create: { key, value },
  });
}

/**
 * Check if magic jobs processing is paused.
 * Returns false if the setting doesn't exist (default: not paused).
 */
export async function isMagicJobsPaused(): Promise<boolean> {
  const value = await getSetting(SETTING_KEYS.MAGIC_JOBS_PAUSED);
  return value === "true";
}

/**
 * Set the magic jobs paused state.
 */
export async function setMagicJobsPaused(paused: boolean): Promise<void> {
  await setSetting(SETTING_KEYS.MAGIC_JOBS_PAUSED, paused ? "true" : "false");
}
