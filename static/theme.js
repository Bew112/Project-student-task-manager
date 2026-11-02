const themeToggle = document.querySelector(".theme-toggle");

if (themeToggle) {
  const themeIcon = themeToggle.querySelector(".theme-toggle-icon");

  function updateTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("studysync-theme", theme);
    const nextTheme = theme === "dark" ? "light" : "dark";
    const label = nextTheme === "dark" ? "Bật giao diện tối" : "Bật giao diện sáng";
    themeToggle.setAttribute("aria-label", label);
    themeToggle.setAttribute("title", label);
    themeToggle.setAttribute("aria-pressed", String(theme === "dark"));
    themeIcon.textContent = theme === "dark" ? "☀" : "☾";
  }

  updateTheme(document.documentElement.dataset.theme || "light");
  themeToggle.addEventListener("click", () => {
    const currentTheme = document.documentElement.dataset.theme || "light";
    updateTheme(currentTheme === "dark" ? "light" : "dark");
  });
}
