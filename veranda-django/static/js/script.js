// ========== MOBILE NAVIGATION TOGGLE ==========
const navToggle = document.getElementById('navToggle');
const navMenu = document.getElementById('navMenu');

if (navToggle && navMenu) {
    navToggle.addEventListener('click', () => {
        navMenu.classList.toggle('active');
        navToggle.classList.toggle('active');
        
        // Animate hamburger to X
        const spans = navToggle.querySelectorAll('span');
        if (navToggle.classList.contains('active')) {
            spans[0].style.transform = 'rotate(45deg) translate(6px, 6px)';
            spans[1].style.opacity = '0';
            spans[2].style.transform = 'rotate(-45deg) translate(6px, -6px)';
        } else {
            spans[0].style.transform = 'none';
            spans[1].style.opacity = '1';
            spans[2].style.transform = 'none';
        }
    });
    
    // Close mobile menu when clicking on a link
    document.querySelectorAll('.nav-menu a').forEach(link => {
        link.addEventListener('click', () => {
            navMenu.classList.remove('active');
            navToggle.classList.remove('active');
            
            // Reset hamburger icon
            const spans = navToggle.querySelectorAll('span');
            spans[0].style.transform = 'none';
            spans[1].style.opacity = '1';
            spans[2].style.transform = 'none';
        });
    });
}

// ========== SMOOTH SCROLLING FOR ANCHOR LINKS ==========
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const targetId = this.getAttribute('href');
        
        if (targetId === '#' || targetId === '') return;
        
        const targetElement = document.querySelector(targetId);
        
        if (targetElement) {
            e.preventDefault();
            window.scrollTo({
                top: targetElement.offsetTop - 100,
                behavior: 'smooth'
            });
            
            // Update URL without page jump
            history.pushState(null, null, targetId);
        }
    });
});

// ========== FORM VALIDATION FOR CONTACT PAGE ==========
if (document.getElementById('contactForm')) {
    const contactForm = document.getElementById('contactForm');
    
    contactForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Get form values
        const name = document.getElementById('name').value.trim();
        const email = document.getElementById('email').value.trim();
        const phone = document.getElementById('phone').value.trim();
        const eventType = document.getElementById('eventType').value;
        const date = document.getElementById('date').value;
        const guests = document.getElementById('guests').value;
        const catering = document.getElementById('catering').value;
        const message = document.getElementById('message').value.trim();
        
        // Reset previous error states
        resetFormErrors();
        
        // Validate form
        let isValid = true;
        
        if (!name) {
            showError('name', 'Please enter your full name');
            isValid = false;
        }
        
        if (!email || !isValidEmail(email)) {
            showError('email', 'Please enter a valid email address');
            isValid = false;
        }
        
        if (!phone || !isValidPhone(phone)) {
            showError('phone', 'Please enter a valid phone number');
            isValid = false;
        }
        
        if (!eventType) {
            showError('eventType', 'Please select an event type');
            isValid = false;
        }
        
        if (!date) {
            showError('date', 'Please select a preferred date');
            isValid = false;
        }
        
        if (!guests) {
            showError('guests', 'Please select estimated guest count');
            isValid = false;
        }
        
        if (!catering) {
            showError('catering', 'Please select catering preference');
            isValid = false;
        }
        
        if (!message || message.length < 10) {
            showError('message', 'Please provide more details about your event (minimum 10 characters)');
            isValid = false;
        }
        
        if (isValid) {
            // In a real application, you would send data to a server here
            // For demo purposes, show success message
            
            const formData = {
                name,
                email,
                phone,
                eventType,
                date,
                guests,
                catering,
                message,
                timestamp: new Date().toISOString()
            };
            
            console.log('Form submitted:', formData);
            
            // Show success message
            showFormSuccess();
            
            // Reset form
            contactForm.reset();
            
            // Reset date restrictions
            if (document.getElementById('date')) {
                setDateRestrictions();
            }
        }
    });
    
    // Real-time validation
    const inputs = contactForm.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            validateField(this);
        });
        
        input.addEventListener('input', function() {
            clearError(this);
        });
    });
}

// Email validation function
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// Phone validation function (simple version)
function isValidPhone(phone) {
    const re = /^[\d\s\-\(\)\+]{10,}$/;
    return re.test(phone.replace(/[^\d]/g, '')) && phone.replace(/[^\d]/g, '').length >= 10;
}

// Show error function
function showError(fieldId, message) {
    const field = document.getElementById(fieldId);
    const formGroup = field.closest('.form-group');
    
    if (formGroup) {
        // Remove existing error
        const existingError = formGroup.querySelector('.error-message');
        if (existingError) existingError.remove();
        
        // Add error class to input
        field.classList.add('error');
        
        // Create error message
        const errorElement = document.createElement('div');
        errorElement.className = 'error-message';
        errorElement.style.color = '#e74c3c';
        errorElement.style.fontSize = '0.9rem';
        errorElement.style.marginTop = '5px';
        errorElement.textContent = message;
        
        formGroup.appendChild(errorElement);
    }
}

// Clear error function
function clearError(field) {
    field.classList.remove('error');
    const formGroup = field.closest('.form-group');
    if (formGroup) {
        const errorElement = formGroup.querySelector('.error-message');
        if (errorElement) errorElement.remove();
    }
}

// Reset all form errors
function resetFormErrors() {
    const errors = document.querySelectorAll('.error-message');
    errors.forEach(error => error.remove());
    
    const errorFields = document.querySelectorAll('.error');
    errorFields.forEach(field => field.classList.remove('error'));
}

// Validate individual field
function validateField(field) {
    const value = field.value.trim();
    const fieldId = field.id;
    
    clearError(field);
    
    if (field.hasAttribute('required') && !value) {
        showError(fieldId, 'This field is required');
        return false;
    }
    
    if (fieldId === 'email' && value && !isValidEmail(value)) {
        showError(fieldId, 'Please enter a valid email address');
        return false;
    }
    
    if (fieldId === 'phone' && value && !isValidPhone(value)) {
        showError(fieldId, 'Please enter a valid phone number');
        return false;
    }
    
    if (fieldId === 'message' && value.length < 10) {
        showError(fieldId, 'Please provide more details (minimum 10 characters)');
        return false;
    }
    
    return true;
}

// Show form success message
function showFormSuccess() {
    // Create or show success message
    let successMessage = document.querySelector('.form-success-message');
    
    if (!successMessage) {
        successMessage = document.createElement('div');
        successMessage.className = 'form-success-message';
        successMessage.style.backgroundColor = '#27ae60';
        successMessage.style.color = 'white';
        successMessage.style.padding = '20px';
        successMessage.style.borderRadius = '5px';
        successMessage.style.marginTop = '20px';
        successMessage.style.textAlign = 'center';
        successMessage.style.fontSize = '1.1rem';
        successMessage.innerHTML = `
            <i class="fas fa-check-circle" style="font-size: 2rem; margin-bottom: 10px; display: block;"></i>
            <h3 style="margin-bottom: 10px;">Thank You!</h3>
            <p>Your inquiry has been submitted successfully. We will contact you within 24 hours.</p>
        `;
        
        const form = document.getElementById('contactForm');
        form.parentNode.insertBefore(successMessage, form.nextSibling);
    }
    
    successMessage.style.display = 'block';
    
    // Hide success message after 5 seconds
    setTimeout(() => {
        successMessage.style.display = 'none';
    }, 5000);
}

// ========== DATE PICKER RESTRICTIONS ==========
if (document.getElementById('date')) {
    function setDateRestrictions() {
        const dateInput = document.getElementById('date');
        const today = new Date();
        
        // Format date as YYYY-MM-DD
        const formatDate = (date) => {
            return date.toISOString().split('T')[0];
        };
        
        // Set min date to today
        dateInput.min = formatDate(today);
        
        // Set max date to 2 years from now
        const maxDate = new Date();
        maxDate.setFullYear(maxDate.getFullYear() + 2);
        dateInput.max = formatDate(maxDate);
        
        // Add date validation on change
        dateInput.addEventListener('change', function() {
            const selectedDate = new Date(this.value);
            const today = new Date();
            const maxDate = new Date();
            maxDate.setFullYear(maxDate.getFullYear() + 2);
            
            if (selectedDate < today) {
                showError('date', 'Please select a future date');
                this.value = '';
            } else if (selectedDate > maxDate) {
                showError('date', 'Please select a date within the next 2 years');
                this.value = '';
            } else {
                clearError(this);
            }
        });
    }
    
    setDateRestrictions();
}

// ========== GALLERY FILTER FUNCTIONALITY ==========
if (document.querySelector('.gallery-filter')) {
    const filterButtons = document.querySelectorAll('.filter-btn');
    const galleryRows = document.querySelectorAll('.gallery-row');
    
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Update active button
            filterButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            const filterValue = this.getAttribute('data-filter');
            
            // Show/hide gallery items
            galleryRows.forEach(row => {
                if (filterValue === 'all' || row.classList.contains(filterValue)) {
                    row.style.display = 'grid';
                    // Scroll to category heading
                    if (filterValue !== 'all') {
                        const categoryHeading = document.getElementById(filterValue);
                        if (categoryHeading) {
                            setTimeout(() => {
                                categoryHeading.scrollIntoView({
                                    behavior: 'smooth',
                                    block: 'start'
                                });
                            }, 100);
                        }
                    }
                } else {
                    row.style.display = 'none';
                }
            });
        });
    });
}

// ========== GALLERY LIGHTBOX FUNCTIONALITY ==========
if (document.querySelector('.gallery-item')) {
    // Create lightbox if it doesn't exist
    let lightbox = document.querySelector('.lightbox');
    
    if (!lightbox) {
        lightbox = document.createElement('div');
        lightbox.className = 'lightbox';
        lightbox.innerHTML = `
            <span class="lightbox-close">&times;</span>
            <div class="lightbox-content">
                <img src="" alt="">
                <div class="lightbox-caption"></div>
            </div>
        `;
        document.body.appendChild(lightbox);
    }
    
    const lightboxImg = lightbox.querySelector('img');
    const lightboxCaption = lightbox.querySelector('.lightbox-caption');
    const lightboxClose = lightbox.querySelector('.lightbox-close');
    
    // Add click event to all gallery items
    document.querySelectorAll('.gallery-item').forEach(item => {
        item.addEventListener('click', function() {
            const img = this.querySelector('img');
            const caption = this.querySelector('.gallery-caption');
            
            if (img) {
                lightboxImg.src = img.src;
                lightboxCaption.textContent = caption ? caption.textContent : '';
                lightbox.style.display = 'flex';
                document.body.style.overflow = 'hidden'; // Prevent scrolling
            }
        });
    });
    
    // Close lightbox
    function closeLightbox() {
        lightbox.style.display = 'none';
        document.body.style.overflow = 'auto'; // Re-enable scrolling
    }
    
    lightboxClose.addEventListener('click', closeLightbox);
    
    lightbox.addEventListener('click', function(e) {
        if (e.target === lightbox) {
            closeLightbox();
        }
    });
    
    // Close with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && lightbox.style.display === 'flex') {
            closeLightbox();
        }
    });
}

// ========== FAQ ACCORDION FUNCTIONALITY ==========
if (document.querySelector('.faq-item')) {
    const faqItems = document.querySelectorAll('.faq-item');
    
    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question');
        
        question.addEventListener('click', () => {
            // Close other open items
            faqItems.forEach(otherItem => {
                if (otherItem !== item && otherItem.classList.contains('active')) {
                    otherItem.classList.remove('active');
                }
            });
            
            // Toggle current item
            item.classList.toggle('active');
        });
    });
    
    // Open FAQ item if URL has hash
    window.addEventListener('load', function() {
        if (window.location.hash) {
            const faqId = window.location.hash.substring(1);
            const faqItem = document.getElementById(faqId);
            
            if (faqItem && faqItem.classList.contains('faq-item')) {
                // Open the FAQ item
                faqItem.classList.add('active');
                
                // Scroll to the FAQ item
                setTimeout(() => {
                    faqItem.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }, 100);
            }
        }
    });
}

// ========== TESTIMONIAL CAROUSEL (Optional Enhancement) ==========
if (document.querySelector('.testimonial-grid') && window.innerWidth < 768) {
    const testimonialGrid = document.querySelector('.testimonial-grid');
    const testimonials = document.querySelectorAll('.testimonial-card');
    let currentIndex = 0;
    
    // Convert grid to carousel on mobile
    testimonialGrid.style.display = 'flex';
    testimonialGrid.style.overflowX = 'auto';
    testimonialGrid.style.scrollSnapType = 'x mandatory';
    testimonialGrid.style.gap = '0';
    
    testimonials.forEach(testimonial => {
        testimonial.style.flex = '0 0 100%';
        testimonial.style.scrollSnapAlign = 'start';
        testimonial.style.marginRight = '20px';
    });
    
    // Add navigation dots
    const carouselContainer = testimonialGrid.parentElement;
    const dotsContainer = document.createElement('div');
    dotsContainer.className = 'carousel-dots';
    dotsContainer.style.display = 'flex';
    dotsContainer.style.justifyContent = 'center';
    dotsContainer.style.marginTop = '20px';
    dotsContainer.style.gap = '10px';
    
    testimonials.forEach((_, index) => {
        const dot = document.createElement('button');
        dot.className = 'carousel-dot';
        dot.setAttribute('data-index', index);
        dot.style.width = '12px';
        dot.style.height = '12px';
        dot.style.borderRadius = '50%';
        dot.style.border = 'none';
        dot.style.backgroundColor = index === 0 ? 'var(--primary-color)' : '#ddd';
        dot.style.cursor = 'pointer';
        dot.style.transition = 'background-color 0.3s';
        
        dot.addEventListener('click', () => {
            goToSlide(index);
        });
        
        dotsContainer.appendChild(dot);
    });
    
    carouselContainer.appendChild(dotsContainer);
    
    // Auto-rotate testimonials
    let autoSlide = setInterval(nextSlide, 5000);
    
    function nextSlide() {
        currentIndex = (currentIndex + 1) % testimonials.length;
        goToSlide(currentIndex);
    }
    
    function goToSlide(index) {
        currentIndex = index;
        testimonialGrid.scrollTo({
            left: testimonialGrid.offsetWidth * index,
            behavior: 'smooth'
        });
        
        updateDots();
        
        // Reset auto-slide timer
        clearInterval(autoSlide);
        autoSlide = setInterval(nextSlide, 5000);
    }
    
    function updateDots() {
        const dots = dotsContainer.querySelectorAll('.carousel-dot');
        dots.forEach((dot, index) => {
            dot.style.backgroundColor = index === currentIndex ? 'var(--primary-color)' : '#ddd';
        });
    }
    
    // Pause auto-slide on hover
    testimonialGrid.addEventListener('mouseenter', () => {
        clearInterval(autoSlide);
    });
    
    testimonialGrid.addEventListener('mouseleave', () => {
        autoSlide = setInterval(nextSlide, 5000);
    });
}

// ========== ACTIVE NAV LINK BASED ON SCROLL POSITION ==========
function updateActiveNavLink() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-menu a');
    
    let currentSection = '';
    
    sections.forEach(section => {
        const sectionTop = section.offsetTop - 150;
        const sectionHeight = section.offsetHeight;
        
        if (window.scrollY >= sectionTop && window.scrollY < sectionTop + sectionHeight) {
            currentSection = section.getAttribute('id');
        }
    });
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        const href = link.getAttribute('href');
        
        if (href === `#${currentSection}` || 
            (currentSection === '' && href === 'index.html') ||
            (window.location.pathname.includes(href.replace('.html', '')) && href !== 'index.html' && !href.startsWith('#'))) {
            link.classList.add('active');
        }
    });
}

// Run on scroll and load
window.addEventListener('scroll', updateActiveNavLink);
window.addEventListener('load', updateActiveNavLink);

// ========== LAZY LOAD IMAGES ==========
if ('IntersectionObserver' in window) {
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src || img.src;
                img.classList.add('loaded');
                imageObserver.unobserve(img);
            }
        });
    }, {
        rootMargin: '50px 0px',
        threshold: 0.1
    });
    
    document.querySelectorAll('img[data-src]').forEach(img => {
        imageObserver.observe(img);
    });
}

// ========== INITIALIZE ON DOM LOAD ==========
document.addEventListener('DOMContentLoaded', function() {
    console.log('Veranda website loaded successfully');
    
    // Add loaded class to body for CSS transitions
    setTimeout(() => {
        document.body.classList.add('loaded');
    }, 100);
    
    // Set current year in footer
    const yearElement = document.querySelector('.footer-bottom p');
    if (yearElement) {
        const currentYear = new Date().getFullYear();
        yearElement.innerHTML = yearElement.innerHTML.replace('2024', currentYear);
    }
});