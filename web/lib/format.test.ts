import { describe, expect, it } from "vitest";
import { dateTime, hours, longDate, money, normalisePostcode, percent, POSTCODE_RE, timeFmt } from "./format";

describe("money", () => {
  it("formats pence as GBP", () => {
    expect(money(6600)).toBe("£66.00");
    expect(money(5)).toBe("£0.05");
    expect(money(123456)).toBe("£1,234.56");
  });
  it("never invents a number for missing data", () => {
    expect(money(null)).toBe("Not available");
    expect(money(undefined)).toBe("Not available");
  });
});

describe("UK dates and times", () => {
  it("uses Europe/London local time across the daylight saving change", () => {
    expect(timeFmt("2026-07-01T09:00:00Z")).toBe("10:00"); // BST
    expect(timeFmt("2026-12-01T09:00:00Z")).toBe("09:00"); // GMT
  });
  it("formats long dates the British way", () => {
    expect(longDate("2026-11-06T12:00:00Z")).toBe("Friday 6 November 2026");
    expect(dateTime("2026-11-06T10:30:00Z")).toContain("at 10:30");
  });
});

describe("durations", () => {
  it("formats whole and part hours", () => {
    expect(hours(120)).toBe("2 hours");
    expect(hours(60)).toBe("1 hour");
    expect(hours(150)).toBe("2h 30m");
  });
});

describe("postcodes", () => {
  it("accepts valid UK shapes and rejects nonsense", () => {
    for (const ok of ["SW11 1AB", "sw111ab", "W1A 1AA", "EC1A 1BB", "M1 1AE"]) expect(POSTCODE_RE.test(ok)).toBe(true);
    for (const bad of ["", "nonsense", "12345", "SW11", "SW11 1"]) expect(POSTCODE_RE.test(bad)).toBe(false);
  });
  it("normalises spacing and case", () => {
    expect(normalisePostcode("sw111ab")).toBe("SW11 1AB");
    expect(normalisePostcode("  w1a  1aa ")).toBe("W1A 1AA");
  });
});

describe("percent", () => {
  it("shows a clear message when there is no data", () => {
    expect(percent(null)).toBe("Not enough data");
    expect(percent(0.456)).toBe("45.6%");
  });
});
