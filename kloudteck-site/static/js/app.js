// KLOUDTECK Global JavaScript
document.addEventListener('DOMContentLoaded', function() {

  // Scroll Progress Bar
  const progressBar = document.createElement('div');
  progressBar.className = 'scroll-progress';
  document.body.appendChild(progressBar);

  window.addEventListener('scroll', () => {
    const winScroll = document.documentElement.scrollTop;
    const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    const scrolled = (winScroll / height) * 100;
    progressBar.style.width = scrolled + '%';
  });

  // Back to Top
  const backToTop = document.getElementById('backToTop');
  if (backToTop) {
    window.addEventListener('scroll', () => {
      if (window.scrollY > 300) {
        backToTop.classList.add('show');
      } else {
        backToTop.classList.remove('show');
      }
    });

    backToTop.addEventListener('click', () => {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // Bootstrap Tooltips
  if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
  }

  // Quick Contact Form (Offcanvas)
  function initQuickForm() {
    const container = document.getElementById('quickFormContainer');
    if (!container) return;
    container.innerHTML = `
      <form id="quickContactForm">
        <div class="mb-3">
          <input type="text" class="form-control" placeholder="Full name *" required>
        </div>
        <div class="mb-3">
          <input type="email" class="form-control" placeholder="Work email *" required>
        </div>
        <div class="mb-3">
          <select class="form-select" required>
            <option value="">I'm interested in...</option>
            <option>Managed Network & Wi-Fi</option>
            <option>CCTV & Surveillance</option>
            <option>Access Control</option>
            <option>Structured Cabling</option>
            <option>Business Phone Systems</option>
            <option>TV & Digital Displays</option>
          </select>
        </div>
        <div class="mb-3">
          <textarea class="form-control" rows="2" placeholder="Brief description"></textarea>
        </div>
        <button type="submit" class="btn btn-teal w-100">Send request</button>
      </form>
    `;
    const quickForm = document.getElementById('quickContactForm');
    if (quickForm) {
      quickForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(quickForm);
        const data = Object.fromEntries(formData.entries());
        data.timestamp = new Date().toISOString();
        
        const submissions = JSON.parse(localStorage.getItem('kloudteck_submissions') || '[]');
        submissions.push(data);
        localStorage.setItem('kloudteck_submissions', JSON.stringify(submissions));
        
        const successModal = new bootstrap.Modal(document.getElementById('successModal'));
        successModal.show();
        
        const mailto = `mailto:support@kloudteck.com?subject=Quick%20contact&body=${encodeURIComponent(JSON.stringify(data, null, 2))}`;
        document.getElementById('mailtoFallback').href = mailto;
        document.getElementById('copyDetails').onclick = () => {
          navigator.clipboard.writeText(JSON.stringify(data, null, 2));
          alert('Details copied to clipboard');
        };
        
        const offcanvas = bootstrap.Offcanvas.getInstance(document.getElementById('offcanvasQuickContact'));
        if (offcanvas) offcanvas.hide();
        quickForm.reset();
      });
    }
  }
  initQuickForm();

  // UTM Capture
  const forms = document.querySelectorAll('form');
  const urlParams = new URLSearchParams(window.location.search);
  const utmParams = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];
  const utmValues = {};

  utmParams.forEach(param => {
    const value = urlParams.get(param);
    if (value) utmValues[param] = value;
  });

  utmValues.referrer = document.referrer || 'direct';
  utmValues.page_url = window.location.href;

  forms.forEach(form => {
    Object.keys(utmValues).forEach(key => {
      let input = form.querySelector(`input[name="${key}"]`);
      if (!input) {
        input = document.createElement('input');
        input.type = 'hidden';
        input.name = key;
        form.appendChild(input);
      }
      input.value = utmValues[key];
    });
  });

  // Intersection Observer for animations
  const animatedElements = document.querySelectorAll('.service-card, .testimonial-card, .industry-badge, .section-heading');
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = 1;
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, { threshold: 0.1 });

  animatedElements.forEach(el => {
    el.style.opacity = 0;
    el.style.transform = 'translateY(20px)';
    el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(el);
  });

  // Multi-step form for contact page
  if (document.getElementById('step1')) {
    let currentStep = 1;
    const totalSteps = 4;
    const formData = {};

    function showStep(step) {
      for (let i = 1; i <= totalSteps; i++) {
        const stepEl = document.getElementById(`step${i}`);
        if (stepEl) stepEl.style.display = i === step ? 'block' : 'none';
      }
      for (let i = 1; i <= totalSteps; i++) {
        const indicator = document.getElementById(`stepIndicator${i}`);
        if (indicator) {
          indicator.classList.remove('active', 'completed');
          if (i === step) indicator.classList.add('active');
          else if (i < step) indicator.classList.add('completed');
        }
      }
    }

    document.querySelectorAll('.next-step').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const currentStepEl = document.getElementById(`step${currentStep}`);
        const inputs = currentStepEl.querySelectorAll('input[required], select[required], textarea[required]');
        let valid = true;
        inputs.forEach(input => {
          if (!input.value.trim()) {
            input.classList.add('is-invalid');
            valid = false;
          } else {
            input.classList.remove('is-invalid');
          }
        });
        if (!valid) return;

        const formDataStep = new FormData(currentStepEl);
        for (let [key, value] of formDataStep.entries()) {
          formData[key] = value;
        }

        if (currentStep < totalSteps) {
          currentStep++;
          showStep(currentStep);
        }
      });
    });

    document.querySelectorAll('.prev-step').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        if (currentStep > 1) {
          currentStep--;
          showStep(currentStep);
        }
      });
    });

    const finalForm = document.getElementById('multiStepForm');
    if (finalForm) {
      finalForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const currentStepEl = document.getElementById(`step${currentStep}`);
        const inputs = currentStepEl.querySelectorAll('input[required], select[required]');
        let valid = true;
        inputs.forEach(input => {
          if (!input.value.trim()) {
            input.classList.add('is-invalid');
            valid = false;
          } else {
            input.classList.remove('is-invalid');
          }
        });
        if (!valid) return;

        const allData = new FormData(finalForm);
        for (let [key, value] of allData.entries()) {
          formData[key] = value;
        }

        Object.keys(utmValues).forEach(key => {
          formData[key] = utmValues[key];
        });

        const submissions = JSON.parse(localStorage.getItem('kloudteck_submissions') || '[]');
        submissions.push({ timestamp: new Date().toISOString(), data: formData });
        localStorage.setItem('kloudteck_submissions', JSON.stringify(submissions));

        const successModal = new bootstrap.Modal(document.getElementById('successModal'));
        successModal.show();

        const mailtoLink = `mailto:support@kloudteck.com?subject=Project%20intake&body=${encodeURIComponent(JSON.stringify(formData, null, 2))}`;
        document.getElementById('mailtoFallback').href = mailtoLink;
        document.getElementById('copyDetails').onclick = () => {
          navigator.clipboard.writeText(JSON.stringify(formData, null, 2));
          alert('Details copied to clipboard');
        };

        document.getElementById('successModal').addEventListener('hidden.bs.modal', () => {
          finalForm.reset();
          currentStep = 1;
          showStep(1);
        }, { once: true });
      });
    }

    showStep(1);
  }

  // Solution Finder
  if (document.getElementById('solutionFinder')) {
    const questions = [
      { q: "What is your primary need?", options: ["Connectivity", "Security", "Communication", "Infrastructure"] },
      { q: "How many locations?", options: ["Single site", "2-5 sites", "6-20 sites", "20+ sites"] },
      { q: "Industry?", options: ["Hospitality", "Retail", "Warehouse", "Office", "Multi-family"] }
    ];
    let step = 0;
    const answers = [];

    const container = document.getElementById('solutionFinder');
    container.innerHTML = `
      <div class="card p-4">
        <h4>Solution Finder</h4>
        <div id="finderStep"></div>
        <div class="mt-3">
          <button class="btn btn-outline-teal" id="finderPrev" style="display:none;">Previous</button>
          <button class="btn btn-teal" id="finderNext">Next</button>
        </div>
      </div>
    `;

    function renderStep() {
      const stepDiv = document.getElementById('finderStep');
      if (step < questions.length) {
        const q = questions[step];
        let optionsHtml = '';
        q.options.forEach(opt => {
          optionsHtml += `<div class="form-check"><input class="form-check-input" type="radio" name="finder" value="${opt}" id="opt${opt}"><label class="form-check-label" for="opt${opt}">${opt}</label></div>`;
        });
        stepDiv.innerHTML = `<h5>${q.q}</h5>${optionsHtml}`;
        document.getElementById('finderPrev').style.display = step > 0 ? 'inline-block' : 'none';
      } else {
        let rec = "Based on your needs, we recommend: ";
        if (answers.includes("Security")) rec += "CCTV & Access Control. ";
        if (answers.includes("Connectivity")) rec += "Managed Network & Wi-Fi. ";
        if (answers.includes("Communication")) rec += "Business Phone Systems. ";
        if (answers.includes("Infrastructure")) rec += "Structured Cabling & Fiber. ";
        stepDiv.innerHTML = `<h5>${rec}</h5><p>Our team can provide a tailored quote.</p>`;
        document.getElementById('finderNext').textContent = 'Start over';
        document.getElementById('finderPrev').style.display = 'none';
      }
    }

    document.getElementById('finderNext').addEventListener('click', () => {
      if (step < questions.length) {
        const selected = document.querySelector('input[name="finder"]:checked');
        if (!selected) {
          alert('Please select an option');
          return;
        }
        answers.push(selected.value);
        step++;
        if (step === questions.length) {
          renderStep();
          document.getElementById('finderNext').textContent = 'See results';
        } else {
          renderStep();
        }
      } else {
        step = 0;
        answers.length = 0;
        renderStep();
        document.getElementById('finderNext').textContent = 'Next';
      }
    });

    document.getElementById('finderPrev').addEventListener('click', () => {
      if (step > 0) {
        step--;
        answers.pop();
        renderStep();
        document.getElementById('finderNext').textContent = 'Next';
      }
    });

    renderStep();
  }

  // Case Studies Filter
  if (document.getElementById('caseStudiesGrid')) {
    const filterButtons = document.querySelectorAll('.filter-btn');
    const cards = document.querySelectorAll('.case-card');

    filterButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const filter = btn.getAttribute('data-filter');
        filterButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        cards.forEach(card => {
          if (filter === 'all' || card.classList.contains(filter)) {
            card.style.display = 'block';
          } else {
            card.style.display = 'none';
          }
        });
      });
    });
  }

  // Chip Selection
  document.addEventListener('click', function(e) {
    if (e.target.classList.contains('chip')) {
      e.target.classList.toggle('selected');
      const parent = e.target.closest('.chip-group');
      if (parent) {
        const hidden = parent.nextElementSibling;
        if (hidden && hidden.tagName === 'INPUT' && hidden.type === 'hidden') {
          const selected = [];
          parent.querySelectorAll('.chip.selected').forEach(c => selected.push(c.getAttribute('data-value')));
          hidden.value = selected.join(',');
        }
      }
    }
  });

});