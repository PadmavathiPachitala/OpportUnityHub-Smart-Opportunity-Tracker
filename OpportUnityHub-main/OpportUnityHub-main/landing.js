// Landing page scroll animations and interactions

document.addEventListener("DOMContentLoaded", () => {
  // Intersection Observer for scroll-reveal
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
        }
      });
    },
    { threshold: 0.1 }
  );

  document.querySelectorAll(".feature-card, .step, .stat-card").forEach((el) => {
    el.style.opacity = "0";
    el.style.transform = "translateY(24px)";
    el.style.transition = "opacity 0.5s ease, transform 0.5s ease";
    observer.observe(el);
  });

  // Re-apply visible state
  document.querySelectorAll(".visible").forEach((el) => {
    el.style.opacity = "1";
    el.style.transform = "translateY(0)";
  });

  // Attach CSS class for animation
  const style = document.createElement("style");
  style.textContent = `.visible { opacity: 1 !important; transform: translateY(0) !important; }`;
  document.head.appendChild(style);

  // Nav scroll effect
  window.addEventListener("scroll", () => {
    const nav = document.querySelector(".nav");
    if (window.scrollY > 40) {
      nav.style.background = "rgba(8,11,20,0.92)";
      nav.style.boxShadow = "0 1px 32px rgba(0,0,0,0.4)";
    } else {
      nav.style.background = "rgba(8,11,20,0.7)";
      nav.style.boxShadow = "none";
    }
  });
});
