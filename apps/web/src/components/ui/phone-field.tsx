"use client";

import {
  getCountries,
  getCountryCallingCode,
  parsePhoneNumberFromString,
  type CountryCode,
} from "libphonenumber-js/min";
import i18nCountries from "i18n-iso-countries";
import { useMemo } from "react";
import fr from "i18n-iso-countries/langs/fr.json";

i18nCountries.registerLocale(fr);

export type PhoneDialCode = { code: string; dial: string; label: string };

const DEFAULT_COUNTRY = "CI";

export const PHONE_DIAL_CODES: PhoneDialCode[] = getCountries()
  .map((code) => ({
    code,
    dial: `+${getCountryCallingCode(code)}`,
    label: i18nCountries.getName(code, "fr") ?? code,
  }))
  .sort((a, b) => {
    if (a.code === DEFAULT_COUNTRY) return -1;
    if (b.code === DEFAULT_COUNTRY) return 1;
    return a.label.localeCompare(b.label, "fr");
  });

const DIALS = [...new Set(PHONE_DIAL_CODES.map((entry) => entry.dial))].sort(
  (a, b) => b.length - a.length,
);

const COUNTRY_OPTIONS = PHONE_DIAL_CODES.map((country) => (
  <option key={country.code} value={country.code}>
    {country.dial} {country.label}
  </option>
));

export function PhoneField({
  value,
  onChange,
  disabled = false,
  readOnly = false,
  required = false,
  autoComplete = "tel",
  placeholder = "07 00 00 00 00",
}: {
  value: string;
  onChange: (fullNumber: string) => void;
  disabled?: boolean;
  readOnly?: boolean;
  required?: boolean;
  autoComplete?: string;
  placeholder?: string;
}) {
  const { code, dial, national } = useMemo(() => splitPhone(value), [value]);

  if (readOnly) {
    return (
      <input
        autoComplete={autoComplete}
        className="form-input"
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        readOnly
        required={required}
        type="tel"
        value={value}
      />
    );
  }

  return (
    <div className="flex gap-2">
      <select
        aria-label="Indicatif du pays"
        className="form-input w-[8.5rem] shrink-0"
        disabled={disabled}
        onChange={(event) =>
          onChange(`+${getCountryCallingCode(event.target.value as CountryCode)}${national}`)
        }
        value={code}
      >
        {COUNTRY_OPTIONS}
      </select>
      <input
        aria-label="Numéro de téléphone"
        autoComplete={autoComplete}
        className="form-input min-w-0 flex-1"
        disabled={disabled}
        inputMode="tel"
        maxLength={14}
        onChange={(event) => {
          const digits = event.target.value.replace(/[^\d\s().-]/g, "");
          onChange(`${dial}${digits}`);
        }}
        placeholder={placeholder}
        required={required}
        type="tel"
        value={national}
      />
    </div>
  );
}

function splitPhone(value: string): { code: string; dial: string; national: string } {
  const candidate = (value ?? "").trim();
  if (candidate.startsWith("+")) {
    const parsed = parsePhoneNumberFromString(candidate);
    if (parsed?.country) {
      return {
        code: parsed.country,
        dial: `+${parsed.countryCallingCode}`,
        national: parsed.nationalNumber,
      };
    }
    const dial = DIALS.find((entry) => candidate.startsWith(entry));
    return {
      code: DEFAULT_COUNTRY,
      dial: PHONE_DIAL_CODES[0].dial,
      national: dial ? candidate.slice(dial.length).trim() : candidate,
    };
  }
  return { code: DEFAULT_COUNTRY, dial: PHONE_DIAL_CODES[0].dial, national: candidate };
}
