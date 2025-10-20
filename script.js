// Theme toggle functionality - always follows system preference
const themeToggle = document.querySelector('.theme-toggle');
const sunIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>';
const moonIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

// Initialize theme based on system setting only
const initializeTheme = () => {
  // Check if dark mode was pre-initialized
  if (document.documentElement.classList.contains('dark-init')) {
    document.body.classList.add('dark');
    document.documentElement.classList.remove('dark-init');
  }
  
  // Set icon based on current state
  themeToggle.innerHTML = document.body.classList.contains('dark') ? moonIcon : sunIcon;
};

// Initialize theme immediately
initializeTheme();

// Listen for system theme changes and always follow them
if (window.matchMedia) {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (e.matches) {
      document.body.classList.add('dark');
      themeToggle.innerHTML = moonIcon;
    } else {
      document.body.classList.remove('dark');
      themeToggle.innerHTML = sunIcon;
    }
  });
}

// Toggle theme on click (temporary, will reset to system preference on reload)
themeToggle.addEventListener('click', () => {
  const isDark = document.body.classList.toggle('dark');
  themeToggle.innerHTML = isDark ? moonIcon : sunIcon;
});

// Copy to clipboard functionality
const setupCopyButton = (type) => {
  const textElement = document.getElementById(`${type}-text`);
  const copyButton = document.getElementById(`copy-${type}-icon`);
  const copiedMessage = document.getElementById(`copied-${type}-msg`);
  
  if (copyButton && textElement && copiedMessage) {
    copyButton.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(textElement.textContent);
        copiedMessage.style.opacity = '1';
        setTimeout(() => {
          copiedMessage.style.opacity = '0';
        }, 1000);
      } catch (err) {
        console.error('Failed to copy:', err);
      }
    });
  }
};

// Setup copy buttons for email and phone
setupCopyButton('email');
setupCopyButton('phone');

// PII Redaction Animation for Synchrony Shield demo
const piiAnimation = () => {
  const redactableElements = document.querySelectorAll('.pii-redactable');
  const shieldStatus = document.getElementById('shield-status');
  const shieldButton = document.getElementById('shield-toggle');
  
  if (!redactableElements.length || !shieldStatus || !shieldButton) return;
  
  // Set initial state
  let isRedacted = false;
  shieldStatus.classList.add('inactive');
  
  // Function to toggle redaction state
  const toggleRedaction = () => {
    
    isRedacted = !isRedacted;
    
    // Change content and color simultaneously - smooth color transition
    redactableElements.forEach((element) => {
      if (isRedacted) {
        element.classList.add('redacted');
        element.textContent = element.dataset.redacted;
      } else {
        element.classList.remove('redacted');
        element.textContent = element.dataset.original;
      }
    });
    
    // Update shield status
    if (isRedacted) {
      shieldStatus.textContent = 'ON';
      shieldStatus.classList.remove('inactive');
      shieldStatus.classList.add('active');
    } else {
      shieldStatus.textContent = 'OFF';
      shieldStatus.classList.remove('active');
      shieldStatus.classList.add('inactive');
    }
  };
  
  // Add click handler for manual toggle
  shieldButton.addEventListener('click', toggleRedaction);
};

// Start PII animation when page loads
window.addEventListener('load', piiAnimation);

// Hero image loader
document.addEventListener('DOMContentLoaded', () => {
  const heroImage = document.getElementById('hero-image');
  heroImage.style.backgroundImage = 'url("hero-image.webp")';
});

// Project collapse functionality
document.addEventListener('DOMContentLoaded', () => {
  const projectHeaders = document.querySelectorAll('.project-header-clickable');
  const projectCards = document.querySelectorAll('.project-card');
  
  // Collapse all projects on load
  projectCards.forEach(card => {
    card.classList.add('collapsed');
  });
  
  projectHeaders.forEach(header => {
    header.addEventListener('click', (e) => {
      // Don't toggle if clicking on a link
      if (e.target.tagName === 'A' || e.target.closest('a')) {
        return;
      }
      
      const projectCard = header.closest('.project-card');
      projectCard.classList.toggle('collapsed');
    });
  });
});

// Subtle entrance animations on scroll
document.addEventListener('DOMContentLoaded', () => {
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('fade-in-visible');
      }
    });
  }, observerOptions);

  // Observe intro section and project cards
  const introSection = document.querySelector('.intro-section');
  const projectsSection = document.querySelector('.projects-section');
  
  if (introSection) {
    introSection.classList.add('fade-in-element');
    observer.observe(introSection);
  }
  
  if (projectsSection) {
    projectsSection.classList.add('fade-in-element');
    observer.observe(projectsSection);
  }
});

