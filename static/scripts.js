// Reveal elements as you scroll
const revealEls = document.querySelectorAll(".reveal");

const obs = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) e.target.classList.add("show");
  });
}, { threshold: 0.12 });

revealEls.forEach(el => obs.observe(el));
