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

// Voting without a page reload. The form works as a plain POST without JS.
function csrfToken(form) {
  return form.querySelector("input[name=csrfmiddlewaretoken]")?.value || "";
}

function buildResults(results, myOptionId) {
  const colors = ["violet", "pink", "orange", "mint", "sky"];
  const top = Math.max(...results.map((r) => r.votes));
  const list = document.createElement("ul");
  list.className = "options";
  list.dataset.results = "";
  results.forEach((r, index) => {
    const item = document.createElement("li");
    const mine = r.id === myOptionId;
    item.className =
      "result result--" + colors[index % colors.length] + (mine ? " result--mine" : "") + (top > 0 && r.votes === top ? " result--leading" : "");
    const bar = document.createElement("span");
    bar.className = "result__bar";
    bar.style.setProperty("--percent", r.percent + "%");
    const label = document.createElement("span");
    label.className = "result__label";
    label.textContent = (mine ? "✓ " : "") + r.label; // textContent: user text is never parsed as HTML
    const value = document.createElement("span");
    value.className = "result__value";
    value.textContent = r.percent + "% · " + r.votes;
    item.append(bar, label, value);
    list.append(item);
  });
  return list;
}

function initVoting() {
  document.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-vote-form]");
    if (!form) return;
    const button = event.submitter;
    if (!button || !button.name) return;
    event.preventDefault();

    const buttons = [...form.querySelectorAll("button")];
    const errorBox = form.querySelector(".vote-error");
    buttons.forEach((b) => (b.disabled = true));
    errorBox.hidden = true;

    try {
      const body = new FormData();
      body.set("option_id", button.value);
      const response = await fetch(form.action, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(form), Accept: "application/json" },
        body,
        credentials: "same-origin",
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        errorBox.textContent = data.error || "Oy kaydedilemedi.";
        errorBox.hidden = false;
        buttons.forEach((b) => (b.disabled = false));
        return;
      }

      const card = form.closest(".poll-card");
      form.replaceWith(buildResults(data.results, data.my_option_id));
      const total = card.querySelector("[data-total-votes]");
      if (total) total.textContent = data.total;
      // Offer "Oyumu değiştir" (the change form lives on the detail page).
      const slot = card.querySelector("[data-change-slot]");
      if (slot && !slot.querySelector("[data-change-vote]")) {
        const detailUrl = card.querySelector(".poll-card__link")?.href || window.location.pathname;
        const link = document.createElement("a");
        link.dataset.changeVote = "";
        link.href = detailUrl + "?degistir=1";
        link.textContent = "Oyumu değiştir";
        link.className = card.classList.contains("poll-card--detail") ? "btn btn--soft btn--sm" : "muted-link";
        slot.prepend(link);
      }
      slot?.querySelector("[data-cancel-change]")?.remove();
      document.querySelector("[data-vote-hint]")?.remove();
    } catch (error) {
      form.submit(); // network or parsing problem: fall back to a normal form post
    }
  });
}

// Destructive forms (close/delete poll) ask for confirmation first.
function initConfirmForms() {
  document.addEventListener("submit", (event) => {
    const message = event.target.dataset?.confirm;
    if (message && !window.confirm(message)) event.preventDefault();
  });
}

// "Linki kopyala": native share sheet when available, clipboard otherwise.
function initShare() {
  document.querySelectorAll("[data-share]").forEach((button) => {
    button.hidden = false; // hidden in the HTML so it does not show up without JS
    const label = button.querySelector("[data-share-label]");
    const original = label.textContent;
    const flash = (text) => {
      label.textContent = text;
      setTimeout(() => (label.textContent = original), 2000);
    };
    button.addEventListener("click", async () => {
      const url = button.dataset.shareUrl;
      if (navigator.share) {
        try {
          await navigator.share({ title: button.dataset.shareTitle, url });
        } catch (error) {
          // The user closed the share sheet; nothing to do.
        }
        return;
      }
      try {
        await navigator.clipboard.writeText(url);
        flash("Kopyalandı ✓");
      } catch (error) {
        window.prompt("Linki kopyala:", url);
      }
    });
  });
}

// The user menu is a <details>; also close it when clicking elsewhere or pressing Escape.
function initUserMenu() {
  const menu = document.querySelector("[data-usermenu]");
  if (!menu) return;
  document.addEventListener("click", (event) => {
    if (menu.open && !menu.contains(event.target)) menu.open = false;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menu.open) {
      menu.open = false;
      menu.querySelector("summary").focus();
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initUserMenu();
  initDismissibleBanners();
  initLoadMore();
  initPollForm();
  initVoting();
  initConfirmForms();
  initShare();
});
