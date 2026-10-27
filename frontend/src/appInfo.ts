/**
 * Registered software name and version as the UI shows them. The full name is
 * localized under the i18n key `app.fullName`; the version comes from
 * package.json, which a backend test keeps equal to backend/app/version.py.
 */
export const APP_SHORT_NAME = "Evidence-Ladder";
export const APP_VERSION = __APP_VERSION__;

/** `1.0.0` -> `V1.0`, the form used on the registration documents. */
export function versionLabel(version: string): string {
  const [major = "0", minor = "0"] = version.split(".");
  return `V${major}.${minor}`;
}

export const APP_VERSION_LABEL = versionLabel(APP_VERSION);
