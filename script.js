// Theme toggle functionality
const themeToggle = document.querySelector('.theme-toggle');
const sunIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>';
const moonIcon = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

// Set initial icon
themeToggle.innerHTML = document.body.classList.contains('dark') ? moonIcon : sunIcon;

// Toggle theme on click
themeToggle.addEventListener('click', () => {
  const isDark = document.body.classList.toggle('dark');
  themeToggle.innerHTML = isDark ? moonIcon : sunIcon;
});

// Fade-in animation with staggered delay
window.addEventListener('load', () => {
  document.querySelectorAll('.fade-in-element').forEach((element, index) => {
    element.style.animationDelay = `${index * 0.1}s`;
  });
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

// Projects section scroll reveal effect
const projectsSection = document.getElementById('projects-section');

const handleScroll = () => {
  const scrollPosition = window.scrollY || document.documentElement.scrollTop;
  
  // Fade in projects section after scrolling a bit
  if (scrollPosition > 100) {
    projectsSection.classList.add('expanded');
  } else {
    projectsSection.classList.remove('expanded');
  }
};

window.addEventListener('scroll', handleScroll);
// Initial check
handleScroll();

// PII Redaction Animation for Synchrony Shield demo
const piiAnimation = () => {
  const redactableElements = document.querySelectorAll('.pii-redactable');
  const shieldStatus = document.getElementById('shield-status');
  const shieldButton = document.getElementById('shield-toggle');
  
  if (!redactableElements.length || !shieldStatus || !shieldButton) return;
  
  // Set initial state - add blinking animation
  let isRedacted = false;
  let isFirstClick = true;
  shieldStatus.classList.add('inactive');
  
  // Add blinking class to all PII elements initially
  redactableElements.forEach((element) => {
    element.classList.add('blinking');
  });
  
  // Function to toggle redaction state
  const toggleRedaction = () => {
    // Remove blinking on first click
    if (isFirstClick) {
      redactableElements.forEach((element) => {
        element.classList.remove('blinking');
      });
      isFirstClick = false;
    }
    
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

