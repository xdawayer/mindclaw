const SANITIZE_RE = /[^a-z0-9_-]/g;

export function sanitizeUserId(userId: string): string {
  const safe = userId.toLowerCase().replace(SANITIZE_RE, "");
  if (!safe) {
    throw new Error("userId resolves to empty string after sanitization");
  }
  return safe;
}
