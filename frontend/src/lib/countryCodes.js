export const COUNTRY_CODES = [
  { dial: "91", label: "India (+91)" },
  { dial: "1", label: "USA / Canada (+1)" },
  { dial: "971", label: "UAE (+971)" },
  { dial: "44", label: "UK (+44)" },
  { dial: "65", label: "Singapore (+65)" },
  { dial: "61", label: "Australia (+61)" },
  { dial: "966", label: "Saudi Arabia (+966)" },
  { dial: "974", label: "Qatar (+974)" },
  { dial: "60", label: "Malaysia (+60)" },
  { dial: "49", label: "Germany (+49)" },
  { dial: "33", label: "France (+33)" },
  { dial: "977", label: "Nepal (+977)" },
  { dial: "880", label: "Bangladesh (+880)" },
  { dial: "94", label: "Sri Lanka (+94)" },
  { dial: "27", label: "South Africa (+27)" },
  { dial: "64", label: "New Zealand (+64)" },
];

// Split a stored full phone (e.g. "918111111101") into { dial, number }.
export function splitPhone(full) {
  const digits = (full || "").replace(/\D/g, "");
  const sorted = [...COUNTRY_CODES].sort((a, b) => b.dial.length - a.dial.length);
  for (const c of sorted) {
    if (digits.startsWith(c.dial)) return { dial: c.dial, number: digits.slice(c.dial.length) };
  }
  return { dial: "91", number: digits };
}
