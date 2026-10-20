const warsawDate = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Warsaw" });

export function todayInWarsaw(): string {
  return warsawDate.format(new Date());
}

export function addDays(iso: string, days: number): string {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function tomorrowInWarsaw(): string {
  return addDays(todayInWarsaw(), 1);
}
