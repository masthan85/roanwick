const ymd = (d: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/London" }).format(d);
export const today = () => ymd(new Date());
export const daysAgo = (n: number) => ymd(new Date(Date.now() - n * 86400000));
