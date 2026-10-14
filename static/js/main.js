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

// Design-foundation demo only: turns a demo card's options into result bars.
// Replaced by the real fetch-based voting flow in Faz 3.
function initDemoVotes() {
  document.querySelectorAll("[data-demo-vote]").forEach((button) => {
    button.addEventListener("click", () => {
      const options = button.closest(".options");
      const buttons = [...options.querySelectorAll("[data-demo-vote]")];
      const shares = [55, 30, 15, 10, 5];
      buttons.forEach((btn, index) => {
        const color = [...btn.classList].find((c) => c.startsWith("option--")).replace("option--", "");
        const result = document.createElement("div");
        result.className = "result result--" + color + (btn === button ? " result--mine" : "") + (index === 0 ? " result--leading" : "");
        result.innerHTML =
          '<span class="result__bar" style="--percent: 0%"></span>' +
          '<span class="result__label"></span><span class="result__value"></span>';
        result.querySelector(".result__label").textContent = (btn === button ? "✓ " : "") + btn.textContent.trim();
        result.querySelector(".result__value").textContent = shares[index] + "%";
        btn.replaceWith(result);
        requestAnimationFrame(() => requestAnimationFrame(() => {
          result.querySelector(".result__bar").style.setProperty("--percent", shares[index] + "%");
        }));
      });
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initDismissibleBanners();
  initDemoVotes();
});
