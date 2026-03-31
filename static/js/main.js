// SafaraOne — Main JavaScript

// ─────────────── NAVBAR ───────────────
const navbar = document.getElementById('navbar');
const hamburger = document.getElementById('hamburger');
const navLinks = document.getElementById('nav-links');

window.addEventListener('scroll', () => {
  if (window.scrollY > 20) {
    navbar?.classList.add('scrolled');
  } else {
    navbar?.classList.remove('scrolled');
  }
  // scroll-to-top button
  const st = document.querySelector('.scroll-top');
  if (st) {
    st.classList.toggle('visible', window.scrollY > 400);
  }
});

hamburger?.addEventListener('click', () => {
  hamburger.classList.toggle('open');
  navLinks?.classList.toggle('open');
});

// Close mobile nav on link click
navLinks?.querySelectorAll('.nav-link').forEach(link => {
  link.addEventListener('click', () => {
    hamburger?.classList.remove('open');
    navLinks?.classList.remove('open');
  });
});

// ─────────────── SCROLL TO TOP ───────────────
document.querySelector('.scroll-top')?.addEventListener('click', () => {
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

// ─────────────── LUCIDE ICONS ───────────────
document.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    lucide.createIcons();
  }
});

// ─────────────── INTERSECTION OBSERVER (scroll animations) ───────────────
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.animation = 'fadeInUp 0.6s ease both';
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.card, .dest-card, .feature-item, .testimonial-card').forEach(el => {
  el.style.opacity = '0';
  observer.observe(el);
});

// ─────────────── FILTER PILLS ───────────────
document.querySelectorAll('.filter-pill').forEach(pill => {
  pill.addEventListener('click', () => {
    const group = pill.closest('.filter-bar');
    if (!group) return;
    const type = pill.dataset.filterType;
    if (type !== 'all' && type) {
      // For multi-group: only deactivate same-group pills
    }
    // Default: single-select within filter-bar
    group.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
  });
});

// ─────────────── HERO SEARCH ───────────────
const heroForm = document.getElementById('hero-search-form');
heroForm?.addEventListener('submit', (e) => {
  e.preventDefault();
  const dest = heroForm.querySelector('[name="destination"]')?.value;
  const type = heroForm.querySelector('[name="type"]')?.value || 'stays';
  if (dest) {
    window.location.href = `/${type}?destination=${dest}`;
  } else {
    window.location.href = '/destinations';
  }
});

// ─────────────── AI PLANNER ───────────────
const plannerForm = document.getElementById('planner-form');
const plannerResult = document.getElementById('planner-result');
const generateBtn = document.getElementById('generate-btn');

plannerForm?.addEventListener('submit', async (e) => {
  e.preventDefault();

  const destination_id = plannerForm.querySelector('[name="destination_id"]').value;
  const budget_usd    = parseFloat(plannerForm.querySelector('[name="budget_usd"]').value);
  const days          = parseInt(plannerForm.querySelector('[name="days"]').value);
  const travelers     = parseInt(plannerForm.querySelector('[name="travelers"]').value);

  if (!destination_id || !budget_usd || budget_usd < 50) {
    alert('Please fill in all fields. Minimum budget is $50.');
    return;
  }

  // Loading state
  generateBtn.disabled = true;
  generateBtn.innerHTML = '<span class="spinner" style="width:18px;height:18px;margin:0;border-width:2px;display:inline-block;"></span> Generating...';
  if (plannerResult) plannerResult.innerHTML = '<div class="spinner"></div>';

  try {
    const resp = await fetch('/api/generate-itinerary', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ destination_id, budget_usd, days, travelers })
    });
    const data = await resp.json();

    if (data.error) {
      plannerResult.innerHTML = `<p class="text-amber">Error: ${data.error}</p>`;
      return;
    }

    renderItinerary(data);
  } catch (err) {
    if (plannerResult) plannerResult.innerHTML = '<p class="text-amber">Something went wrong. Please try again.</p>';
  } finally {
    generateBtn.disabled = false;
    generateBtn.innerHTML = '<i data-lucide="sparkles" style="width:18px;height:18px"></i> Generate My Itinerary';
    lucide.createIcons();
  }
});

function renderItinerary(data) {
  if (!plannerResult) return;

  const utilColor = data.budget_utilization_pct > 100 ? '#EF4444' : (data.budget_utilization_pct > 90 ? '#F59E0B' : '#34D399');
  const barWidth = Math.min(data.budget_utilization_pct, 100);

  const daysHtml = data.itinerary.map(day => {
    let items = '';
    if (day.accommodation) {
      items += `
        <div class="day-item">
          <div class="day-item-icon hotel"><i data-lucide="bed-double" style="width:16px;height:16px"></i></div>
          <div class="day-item-info">
            <div class="day-item-name">${day.accommodation.name}</div>
            <div class="day-item-sub">${day.accommodation.type} · ${day.accommodation.tier}</div>
          </div>
          <div class="day-item-cost">$${day.accommodation.price_per_night_usd}/night</div>
        </div>`;
    }
    if (day.experience) {
      items += `
        <div class="day-item">
          <div class="day-item-icon exp"><i data-lucide="map-pin" style="width:16px;height:16px"></i></div>
          <div class="day-item-info">
            <div class="day-item-name">${day.experience.title}</div>
            <div class="day-item-sub">${day.experience.duration_hours}h · ${day.experience.category}</div>
          </div>
          <div class="day-item-cost">$${day.experience.price_usd}</div>
        </div>`;
    }
    if (day.guide) {
      items += `
        <div class="day-item">
          <div class="day-item-icon guide"><i data-lucide="user-check" style="width:16px;height:16px"></i></div>
          <div class="day-item-info">
            <div class="day-item-name">Guide: ${day.guide.name}</div>
            <div class="day-item-sub">${day.guide.specializations.join(', ')}</div>
          </div>
          <div class="day-item-cost">$${day.guide.price_per_day_usd}/day</div>
        </div>`;
    }

    return `
      <div class="itinerary-day">
        <div class="day-label">${day.date_label}</div>
        <div class="day-items">${items}</div>
        <div style="text-align:right;margin-top:12px;font-size:0.8rem;color:var(--text-muted)">
          Day total: <strong style="color:var(--amber)">$${day.day_cost_usd.toFixed(2)}</strong>
        </div>
      </div>`;
  }).join('');

  plannerResult.innerHTML = `
    <div class="itinerary-result">
      <div class="itinerary-header">
        <div>
          <div class="section-label"><i data-lucide="sparkles" style="width:14px;height:14px"></i> AI Generated Plan</div>
          <h3 style="font-family:'Outfit',sans-serif;font-size:1.4rem;margin-top:4px">${data.destination.name} · ${data.days}-Day Trip</h3>
          <p style="color:var(--text-secondary);font-size:0.85rem;margin-top:6px">${data.travelers} traveler${data.travelers > 1 ? 's' : ''} · AI-optimized budget</p>
        </div>
        <div class="budget-ring-wrap" style="text-align:right">
          <div style="font-size:0.75rem;color:var(--text-muted);letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px">Total Cost</div>
          <div class="budget-number" style="${data.budget_utilization_pct > 100 ? 'color:#EF4444' : ''}">$${data.total_cost_usd.toFixed(0)}</div>
          <div style="font-size:0.78rem;color:var(--text-muted)">of $${data.budget_usd} budget</div>
          <div class="savings-badge" style="margin-top:8px;float:right;${data.savings_usd < 0 ? 'color:#EF4444;background:rgba(239, 68, 68, 0.1);border-color:rgba(239, 68, 68, 0.2);' : ''}">
            <i data-lucide="piggy-bank" style="width:12px;height:12px"></i>
            ${data.savings_usd < 0 ? '+$' + Math.abs(data.savings_usd).toFixed(0) + ' over' : '$' + data.savings_usd.toFixed(0) + ' saved'}
          </div>
        </div>
      </div>

      <div style="background:rgba(255,255,255,0.04);border-radius:8px;padding:8px;margin-bottom:24px">
        <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:0.8rem;color:var(--text-muted)">
          <span>Budget used</span><span style="color:${utilColor}">${data.budget_utilization_pct}%</span>
        </div>
        <div style="height:6px;background:rgba(255,255,255,0.06);border-radius:6px;overflow:hidden">
          <div style="height:100%;width:${barWidth}%;background:${utilColor};border-radius:6px;transition:width 1s ease"></div>
        </div>
      </div>

      ${daysHtml}

      <div class="tip-box">
        <div class="tip-box-icon"><i data-lucide="lightbulb" style="width:18px;height:18px"></i></div>
        <div><strong style="color:var(--amber)">Local Tip:</strong> ${data.summary.tip}</div>
      </div>

      <div style="margin-top:24px;display:flex;gap:12px;flex-wrap:wrap">
        <a href="/stays?destination=${data.destination.id}" class="btn btn-primary btn-sm">
          <i data-lucide="bed-double" style="width:15px;height:15px"></i> Book ${data.summary.accommodation_tier} Stay
        </a>
        <a href="/experiences?destination=${data.destination.id}" class="btn btn-ocean btn-sm">
          <i data-lucide="zap" style="width:15px;height:15px"></i> Browse Experiences
        </a>
        <a href="/guides?destination=${data.destination.id}" class="btn btn-outline btn-sm">
          <i data-lucide="user-check" style="width:15px;height:15px"></i> Find a Guide
        </a>
      </div>
    </div>`;

  // Re-run lucide after DOM update
  setTimeout(() => lucide.createIcons(), 50);
  plannerResult.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ─────────────── NUMBER COUNTER ANIMATION ───────────────
const counters = document.querySelectorAll('[data-count]');
const countObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    const el = entry.target;
    const target = parseInt(el.dataset.count, 10);
    const duration = 1800;
    const step = target / (duration / 16);
    let current = 0;
    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      el.textContent = Math.floor(current).toLocaleString();
      if (current >= target) clearInterval(timer);
    }, 16);
    countObserver.unobserve(el);
  });
}, { threshold: 0.5 });

counters.forEach(el => countObserver.observe(el));

// ─────────────── AUTH TABS ───────────────
document.querySelectorAll('.auth-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const form = tab.dataset.form;
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.auth-form-panel').forEach(p => p.style.display = 'none');
    tab.classList.add('active');
    const panel = document.getElementById(`form-${form}`);
    if (panel) panel.style.display = 'block';
  });
});

// ─────────────── STAR RENDERING ───────────────
function renderStars(rating, maxStars = 5) {
  let stars = '';
  for (let i = 1; i <= maxStars; i++) {
    stars += `<span style="color:${i <= Math.round(rating) ? '#FCD34D' : 'rgba(255,255,255,0.2)'}">★</span>`;
  }
  return stars;
}
