// NAV SCROLL
const nav = document.getElementById('nav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 40);
}, { passive: true });

// BURGER MENU
const burger = document.getElementById('burger');
const navLinks = document.getElementById('navLinks');
burger.addEventListener('click', () => {
  navLinks.classList.toggle('open');
});
navLinks.querySelectorAll('a').forEach(link => {
  link.addEventListener('click', () => navLinks.classList.remove('open'));
});

// REVEAL ON SCROLL
const revealEls = document.querySelectorAll('.reveal');
const revealObs = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      e.target.classList.add('visible');
      revealObs.unobserve(e.target);
    }
  });
}, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
revealEls.forEach(el => revealObs.observe(el));

// COUNTER ANIMATION
const statEls = document.querySelectorAll('.stat-num');
const counterObs = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      const el = e.target;
      const target = parseInt(el.dataset.target, 10);
      const duration = 1800;
      const step = Math.max(1, Math.floor(target / 60));
      let current = 0;
      const timer = setInterval(() => {
        current = Math.min(current + step, target);
        el.textContent = current;
        if (current >= target) clearInterval(timer);
      }, duration / 60);
      counterObs.unobserve(el);
    }
  });
}, { threshold: 0.5 });
statEls.forEach(el => counterObs.observe(el));

// BEFORE / AFTER SLIDER
function initSlider(sliderId, handleId) {
  const slider = document.getElementById(sliderId);
  const handle = document.getElementById(handleId);
  const after = slider.querySelector('.ba-after');
  if (!slider || !handle || !after) return;

  let dragging = false;

  function setPosition(x) {
    const rect = slider.getBoundingClientRect();
    let pct = Math.max(5, Math.min(95, ((x - rect.left) / rect.width) * 100));
    handle.style.left = pct + '%';
    after.style.clipPath = `inset(0 ${100 - pct}% 0 0)`;
  }

  handle.style.left = '50%';
  after.style.clipPath = 'inset(0 50% 0 0)';

  slider.addEventListener('mousedown', e => { dragging = true; setPosition(e.clientX); });
  slider.addEventListener('touchstart', e => { dragging = true; setPosition(e.touches[0].clientX); }, { passive: true });
  window.addEventListener('mousemove', e => { if (dragging) setPosition(e.clientX); });
  window.addEventListener('touchmove', e => { if (dragging) setPosition(e.touches[0].clientX); }, { passive: true });
  window.addEventListener('mouseup', () => { dragging = false; });
  window.addEventListener('touchend', () => { dragging = false; });
}

initSlider('slider1', 'handle1');
initSlider('slider2', 'handle2');

// CONTACT FORM (client-side only — email via mailto fallback)
const form = document.getElementById('contactForm');
const successDiv = document.getElementById('formSuccess');

form.addEventListener('submit', function(e) {
  e.preventDefault();
  const data = new FormData(form);
  const nom = data.get('nom');
  const tel = data.get('telephone');
  const email = data.get('email');
  const service = data.get('service') || 'Non précisé';
  const message = data.get('message');

  const body = encodeURIComponent(
    `Nouvelle demande de devis — Joe Nettoyage\n\nNom : ${nom}\nTéléphone : ${tel}\nEmail : ${email}\nPrestation : ${service}\n\nMessage :\n${message}`
  );
  const subject = encodeURIComponent(`Demande de devis — ${service} — ${nom}`);
  const mailtoLink = `mailto:medicdaniel796@gmail.com?subject=${subject}&body=${body}`;

  window.location.href = mailtoLink;

  setTimeout(() => {
    form.style.display = 'none';
    successDiv.style.display = 'flex';
  }, 500);
});

// SMOOTH ANCHOR SCROLL
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
  anchor.addEventListener('click', function(e) {
    const target = document.querySelector(this.getAttribute('href'));
    if (!target) return;
    e.preventDefault();
    const offset = 80;
    window.scrollTo({ top: target.offsetTop - offset, behavior: 'smooth' });
  });
});
