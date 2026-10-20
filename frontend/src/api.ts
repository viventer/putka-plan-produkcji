import { z } from "zod";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const ErrorBodySchema = z.object({
  detail: z.union([z.string(), z.array(z.object({ msg: z.string() }))]),
});

function errorMessage(status: number, body: unknown): string {
  const parsed = ErrorBodySchema.safeParse(body);
  if (!parsed.success) {
    return `HTTP ${status}`;
  }
  const { detail } = parsed.data;
  if (typeof detail === "string") {
    return detail !== "" ? detail : `HTTP ${status}`;
  }
  const message = detail
    .map((item) => item.msg)
    .filter((msg) => msg !== "")
    .join("; ");
  return message !== "" ? message : `HTTP ${status}`;
}

export async function fetchJson<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = undefined;
    }
    throw new Error(errorMessage(response.status, body));
  }

  let json: unknown;
  try {
    json = await response.json();
  } catch {
    throw new Error("Nieprawidłowa odpowiedź serwera");
  }
  const parsed = schema.safeParse(json);
  if (!parsed.success) {
    console.error("Unexpected API response", parsed.error);
    throw new Error("Nieprawidłowa odpowiedź serwera");
  }
  return parsed.data;
}
