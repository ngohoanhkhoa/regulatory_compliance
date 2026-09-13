const KEY = "regcom_settings";

const DEFAULTS = {
  includeRepealed: false,
  language: "en",
};

export const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "fr", label: "Français" },
  { code: "vi", label: "Tiếng Việt" },
];

export function getSettings() {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : { ...DEFAULTS };
  } catch {
    return { ...DEFAULTS };
  }
}

export function setSetting(key, value) {
  const current = getSettings();
  current[key] = value;
  localStorage.setItem(KEY, JSON.stringify(current));
}
