// ============================================
// SMART PARKING — main.js
// ============================================

// --- CLOCK ---
function updateClock() {
    const el = document.getElementById('clock');
    if (!el) return;
    const now = new Date();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    el.textContent = `${h}:${m}:${s}`;
}
updateClock();
setInterval(updateClock, 1000);

// --- COUNTER ANIMATION for stat values ---
function animateCounter(el) {
    const target = parseInt(el.getAttribute('data-target')) || 0;
    if (target === 0) { el.textContent = '0'; return; }
    const duration = 900;
    const start = performance.now();
    function tick(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        // ease out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.floor(eased * target);
        if (progress < 1) requestAnimationFrame(tick);
        else el.textContent = target;
    }
    requestAnimationFrame(tick);
}

document.querySelectorAll('.stat-value[data-target]').forEach(el => {
    // trigger when element is visible
    const obs = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(el);
                obs.unobserve(el);
            }
        });
    }, { threshold: 0.3 });
    obs.observe(el);
});

// --- AUTO DISMISS ALERTS ---
document.querySelectorAll('.alert').forEach(el => {
    setTimeout(() => {
        el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        el.style.opacity = '0';
        el.style.transform = 'translateY(-8px)';
        setTimeout(() => el.remove(), 500);
    }, 3500);
});
