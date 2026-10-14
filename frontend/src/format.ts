// Formatting shared by the features.

/** An ISO 8601 datetime from the API, in the user's locale and time zone. */
export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString()
}
