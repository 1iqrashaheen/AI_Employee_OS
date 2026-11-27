export const senderName = (from: string) => from.split("<")[0].trim().replace(/^"|"$/g, "") || from;
export const senderAddress = (from: string) => from.match(/<([^>]+)>/)?.[1] ?? "";

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Quick check so the UI can give instant feedback. The server does the real validation. */
export function isValidRecipient(value: string): boolean {
  const v = value.trim();
  if (!v || /[\r\n;,]/.test(v.replace(/"[^"]*"/g, ""))) return false;
  const address = v.match(/<([^>]+)>\s*$/)?.[1] ?? v;
  return /^[^@\s<>",;]+@[^@\s<>",;]+\.[^@\s<>",;]{2,}$/.test(address);
}
