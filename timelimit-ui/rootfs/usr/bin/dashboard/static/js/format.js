import { t } from "./i18n.js";

/** 3900000 ms -> "1 h 05 min" (nl: "1 u 05 min"); under an hour "45 min". */
export function formatDuration(ms) {
  const minutes = Math.round(ms / 60000);
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m} ${t("unit.min")}`;
  return `${h} ${t("unit.h")} ${String(m).padStart(2, "0")} ${t("unit.min")}`;
}

export function statusLabel(status) {
  return t(`status.${status}`);
}
