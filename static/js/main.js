document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("menuToggle");
  const nav = document.getElementById("mainNav");

  // Mobile navigation menu
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("nav-open");

      toggle.setAttribute("aria-expanded", String(open));
      toggle.textContent = open ? "×" : "☰";
    });
  }

  // Automatically hide flash messages
  document.querySelectorAll(".flash").forEach((message) => {
    window.setTimeout(() => {
      message.style.transition = "opacity .3s ease";
      message.style.opacity = "0";

      window.setTimeout(() => {
        message.remove();
      }, 350);
    }, 6000);
  });
});