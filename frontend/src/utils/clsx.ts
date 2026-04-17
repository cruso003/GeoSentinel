// Tiny inline replacement for clsx — keeps the dep graph minimal.
export function clsx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ');
}
