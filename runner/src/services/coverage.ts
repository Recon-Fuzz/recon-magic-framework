import fs from "fs/promises";
import path from "path";

interface LineData {
  lineNumber: number;
  hitCount: number;
}

interface FileCoverage {
  file: string;
  lines: LineData[];
  linesHit: number;
  linesTotal: number;
}

export interface CoverageResult {
  totalCoverage: number;
  perFile: Record<string, { coverage: number; linesHit: number; linesTotal: number }>;
}

type ReconCoverageConfig = Record<string, string[]>; // file -> ["66-130", "133-173", ...]

/**
 * Parse an LCOV file into structured data
 */
function parseLcov(lcovContent: string): FileCoverage[] {
  const files: FileCoverage[] = [];
  let currentFile: FileCoverage | null = null;

  for (const line of lcovContent.split("\n")) {
    const trimmed = line.trim();

    if (trimmed.startsWith("SF:")) {
      currentFile = {
        file: trimmed.slice(3),
        lines: [],
        linesHit: 0,
        linesTotal: 0,
      };
    } else if (trimmed.startsWith("DA:") && currentFile) {
      // DA:lineNumber,hitCount
      const [lineNum, hitCount] = trimmed.slice(3).split(",").map(Number);
      currentFile.lines.push({ lineNumber: lineNum, hitCount });
    } else if (trimmed.startsWith("LH:") && currentFile) {
      currentFile.linesHit = parseInt(trimmed.slice(3), 10);
    } else if (trimmed.startsWith("LF:") && currentFile) {
      currentFile.linesTotal = parseInt(trimmed.slice(3), 10);
    } else if (trimmed === "end_of_record" && currentFile) {
      files.push(currentFile);
      currentFile = null;
    }
  }

  return files;
}

/**
 * Parse range string "66-130" into [start, end] tuple
 */
function parseRange(range: string): [number, number] {
  const [start, end] = range.split("-").map(Number);
  return [start, end ?? start]; // Handle single line case like "18"
}

/**
 * Check if a line number falls within any of the specified ranges
 */
function isLineInRanges(lineNumber: number, ranges: string[]): boolean {
  for (const range of ranges) {
    const [start, end] = parseRange(range);
    if (lineNumber >= start && lineNumber <= end) {
      return true;
    }
  }
  return false;
}

/**
 * Normalize file path for matching (handles src/foo.sol vs ./src/foo.sol)
 */
function normalizeFilePath(filePath: string): string {
  return filePath.replace(/^\.\//, "").replace(/\\/g, "/");
}

/**
 * Calculate coverage percentage from LCOV file, filtered by recon-coverage.json if provided.
 * Only counts lines that fall within the specified ranges in the config.
 */
export async function calculateFilteredCoverage(
  lcovPath: string,
  reconCoverageConfigPath: string
): Promise<CoverageResult> {
  const [lcovContent, configContent] = await Promise.all([
    fs.readFile(lcovPath, "utf8"),
    fs.readFile(reconCoverageConfigPath, "utf8"),
  ]);

  const config: ReconCoverageConfig = JSON.parse(configContent);
  const files = parseLcov(lcovContent);

  // Normalize config keys for matching
  const normalizedConfig: ReconCoverageConfig = {};
  for (const [file, ranges] of Object.entries(config)) {
    normalizedConfig[normalizeFilePath(file)] = ranges;
  }

  let totalHit = 0;
  let totalLines = 0;
  const perFile: CoverageResult["perFile"] = {};

  for (const fileCov of files) {
    const normalizedFile = normalizeFilePath(fileCov.file);

    // Find matching config entry (check if lcov file path ends with config path)
    const configEntry = Object.entries(normalizedConfig).find(
      ([configFile]) =>
        normalizedFile.endsWith(configFile) ||
        configFile.endsWith(normalizedFile)
    );

    if (!configEntry) {
      // File not in config, skip it
      continue;
    }

    const [matchedFile, ranges] = configEntry;

    // Filter lines to only those in specified ranges
    let fileHit = 0;
    let fileTotal = 0;

    for (const line of fileCov.lines) {
      if (isLineInRanges(line.lineNumber, ranges)) {
        fileTotal++;
        if (line.hitCount > 0) {
          fileHit++;
        }
      }
    }

    if (fileTotal > 0) {
      perFile[matchedFile] = {
        coverage: (fileHit / fileTotal) * 100,
        linesHit: fileHit,
        linesTotal: fileTotal,
      };
      totalHit += fileHit;
      totalLines += fileTotal;
    }
  }

  return {
    totalCoverage: totalLines > 0 ? (totalHit / totalLines) * 100 : 0,
    perFile,
  };
}

/**
 * Calculate coverage percentage from LCOV file without filtering.
 * Returns overall coverage and per-file breakdown.
 */
export async function calculateUnfilteredCoverage(
  lcovPath: string
): Promise<CoverageResult> {
  const lcovContent = await fs.readFile(lcovPath, "utf8");
  const files = parseLcov(lcovContent);

  let totalHit = 0;
  let totalLines = 0;
  const perFile: CoverageResult["perFile"] = {};

  for (const fileCov of files) {
    const normalizedFile = normalizeFilePath(fileCov.file);

    // Use DA lines for accurate counting
    let fileHit = 0;
    let fileTotal = fileCov.lines.length;

    for (const line of fileCov.lines) {
      if (line.hitCount > 0) {
        fileHit++;
      }
    }

    // Fallback to LH/LF if no DA lines parsed
    if (fileTotal === 0 && fileCov.linesTotal > 0) {
      fileTotal = fileCov.linesTotal;
      fileHit = fileCov.linesHit;
    }

    if (fileTotal > 0) {
      perFile[normalizedFile] = {
        coverage: (fileHit / fileTotal) * 100,
        linesHit: fileHit,
        linesTotal: fileTotal,
      };
      totalHit += fileHit;
      totalLines += fileTotal;
    }
  }

  return {
    totalCoverage: totalLines > 0 ? (totalHit / totalLines) * 100 : 0,
    perFile,
  };
}

/**
 * Main function to calculate coverage - uses filtered if config exists, unfiltered otherwise
 */
export async function calculateCoverage(
  lcovPath: string,
  projectPath: string
): Promise<CoverageResult> {
  const reconCoverageConfigPath = path.join(projectPath, "recon-coverage.json");

  try {
    await fs.access(reconCoverageConfigPath);
    console.log("[coverage] Using recon-coverage.json for filtered coverage");
    return calculateFilteredCoverage(lcovPath, reconCoverageConfigPath);
  } catch {
    console.log(
      "[coverage] No recon-coverage.json found, calculating full coverage"
    );
    return calculateUnfilteredCoverage(lcovPath);
  }
}
