export function dateFromEpochSeconds(timestamp: number): Date {
  return new Date(timestamp * 1_000);
}
