// KararVeremedim — main.js (plain JS, no libraries)

// Dismissible invitation banner; remembers the choice in localStorage.
function initDismissibleBanners() {
  document.querySelectorAll("[data-dismissible]").forEach((banner) => {
    const key = "kv_dismissed_" + banner.dataset.dismissible;
    try {
      if (localStorage.getItem(key)) {
        banner.remove();
        return;
      }
    } catch (e) {
      // localStorage may be blocked; the banner simply stays visible.
    }
    banner.querySelector("[data-dismiss]")?.addEventListener("click", () => {
      banner.remove();
      try {
        localStorage.setItem(key, "1");
      } catch (e) {}
    });
  });
}

// "Daha fazla göster": fetches the next page fragment and appends it.
// Without JS the button is an ordinary link to the next page.
function initLoadMore() {
  const list = document.getElementById("poll-list");
  if (!list) return;

  list.addEventListener("click", async (event) => {
    const link = event.target.closest("[data-load-more]");
    if (!link) return;
    event.preventDefault();
    if (link.getAttribute("aria-busy") === "true") return;

    link.setAttribute("aria-busy", "true");
    const label = link.textContent;
    link.textContent = "Yükleniyor…";
    try {
      const url = new URL(link.href, window.location.href);
      url.searchParams.set("partial", "1");
      const response = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const template = document.createElement("template");
      template.innerHTML = await response.text();
      link.closest(".load-more-wrap").remove();
      list.append(template.content);
    } catch (error) {
      link.textContent = label;
      link.removeAttribute("aria-busy");
      window.location.href = link.href; // fall back to a normal page load
    }
  });
}

// Poll creation form: live character counters and 2-5 dynamic option fields.
function initPollForm() {
  const form = document.querySelector("[data-poll-form]");
  if (!form) return;

  form.querySelectorAll("[data-counter]").forEach((field) => {
    const limit = Number(field.dataset.counter);
    const counter = document.createElement("span");
    counter.className = "counter";
    counter.setAttribute("aria-live", "polite");
    field.insertAdjacentElement("afterend", counter);
    const update = () => {
      const length = field.value.length;
      counter.textContent = length + "/" + limit;
      counter.classList.toggle("counter--limit", length >= limit);
    };
    field.addEventListener("input", update);
    update();
  });

  const MIN = 2;
  const rows = [...form.querySelectorAll("[data-option-row]")];
  const addButton = form.querySelector("[data-add-option]");
  const inputOf = (row) => row.querySelector("input");
  const hasContent = (row) => inputOf(row).value.trim() !== "" || row.querySelector(".field__error");

  // Show the first two rows plus any row that is filled or has an error.
  let visible = MIN;
  rows.forEach((row, index) => {
    if (hasContent(row)) visible = Math.max(visible, index + 1);
  });

  function render() {
    rows.forEach((row, index) => {
      row.hidden = index >= visible;
      row.querySelector("[data-remove-option]").hidden = index < MIN; // x from the 3rd option on
    });
    addButton.hidden = visible >= rows.length;
  }

  addButton.addEventListener("click", () => {
    if (visible < rows.length) {
      visible += 1;
      render();
      inputOf(rows[visible - 1]).focus();
    }
  });

  rows.forEach((row, index) => {
    row.querySelector("[data-remove-option]").addEventListener("click", () => {
      if (visible <= MIN) return;
      // Shift later values up so no gap is left, then hide the last visible row.
      for (let i = index; i < visible - 1; i++) {
        inputOf(rows[i]).value = inputOf(rows[i + 1]).value;
      }
      inputOf(rows[visible - 1]).value = "";
      visible -= 1;
      render();
    });
  });

  render();

  // Block a second click while the first submit is in flight.
  const submitButton = form.querySelector("button[type=submit]");
  const submitLabel = submitButton.textContent;
  form.addEventListener("submit", () => {
    submitButton.disabled = true;
    submitButton.textContent = "Yayınlanıyor…";
  });
  // Restore the button if the browser brings this page back from its cache.
  window.addEventListener("pageshow", () => {
    submitButton.disabled = false;
    submitButton.textContent = submitLabel;
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initDismissibleBanners();
  initLoadMore();
  initPollForm();
});
