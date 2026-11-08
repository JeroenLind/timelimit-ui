import { apiFetch } from "./api.js";
import { t } from "./i18n.js";

export async function refreshOverview() {
  const list = document.getElementById("overview-list");
  const empty = document.getElementById("overview-empty");
  try {
    const data = await apiFetch("/api/overview");
    list.replaceChildren(
      ...data.items.map((item) => {
        const li = document.createElement("li");
        li.textContent = item.name;
        return li;
      }),
    );
    empty.hidden = data.items.length > 0;
  } catch (error) {
    empty.hidden = false;
    empty.textContent = t(`error.${error.code}`) || t("error.unknown");
  }
}
