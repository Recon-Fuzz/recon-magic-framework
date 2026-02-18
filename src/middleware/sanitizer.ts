import { Request, Response, NextFunction } from "express";
import { sanitizePreprocess } from "../sanitizePreprocess";

function sanitizeString(input: string): string {
  let sanitized = input.trim();
  sanitized = sanitized.replace(/[^a-zA-Z0-9-_.\/]/g, "");
  return sanitized;
}

function sanitizeObject(obj: Record<string, any>): void {
  Object.keys(obj).forEach((key) => {
    const value = obj[key];

    // For some reason we can't use OR when comparing keys
    // So we handle prepareContracts specifically
    if (key === "target") return;
    if (key === "replacement") return;
    if (key === "endOfTargetMarker") return;

    if (typeof value === "string") {
      let sanitized: string;
      if (key === "endOfTargetMarker") {
        sanitized = obj[key].trim().replace(/[^a-zA-Z0-9-_.;\/]/g, "");
      } else {
        sanitized = sanitizeString(value);
      }
      if (sanitized === "" && value !== "") {
        throw new Error(`Input for '${key}' cannot be empty after sanitization.`);
      }
      if (key !== "preprocess") {
        obj[key] = sanitized;
      }
    } else if (Array.isArray(value)) {
      value.forEach((item, index) => {
        if (typeof item === "string") {
          const sanitized = sanitizeString(item);
          if (sanitized === "" && item !== "") {
            throw new Error(`Input for '${key}[${index}]' cannot be empty after sanitization.`);
          }
          value[index] = sanitized;
        } else if (typeof item === "object" && item !== null) {
          sanitizeObject(item);
        }
      });
    } else if (typeof value === "object" && value !== null) {
      sanitizeObject(value);
    } else if (typeof value === "number") {
      if (isNaN(value)) {
        throw new Error(`Input for '${key}' must be a number`);
      }
      obj[key] = value;
    }
  });
}

export function sanitizeInput(req: Request, res: Response, next: NextFunction) {
  try {
    if (req.body) {
      sanitizeObject(req.body);
    }
    if (req.params) {
      sanitizeObject(req.params);
    }
    if (req.query) {
      sanitizeObject(req.query);
    }
    next();
  } catch (error) {
    if (error instanceof Error) {
      res.status(400).json({
        message: error.message,
        data: "Input validation error",
      });
    } else {
      res.status(400).json({
        message: "An unknown error occurred during input sanitization.",
        data: "Input validation error",
      });
    }
  }
}
