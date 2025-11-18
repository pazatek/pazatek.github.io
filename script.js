// Theme toggle functionality - follows system preference
const themeToggle = document.querySelector('.theme-toggle-nav');
const sunIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>';
const moonIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';

const updateThemeUI = (isDark) => {
  if (themeToggle) {
    themeToggle.innerHTML = isDark ? moonIcon : sunIcon;
  }
};

// Initialize theme based on system preference
const initTheme = () => {
  if (document.documentElement.classList.contains('dark-init')) {
    document.body.classList.add('dark');
    document.documentElement.classList.remove('dark-init');
  }
  updateThemeUI(document.body.classList.contains('dark'));
};

initTheme();

if (window.matchMedia) {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    document.body.classList.toggle('dark', e.matches);
    updateThemeUI(e.matches);
  });
}

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const isDark = document.body.classList.toggle('dark');
    updateThemeUI(isDark);
  });
}

// Copy to clipboard functionality
const setupCopyButtons = () => {
  ['email', 'phone'].forEach(type => {
    const textElement = document.getElementById(`${type}-text`);
    const copyButton = document.getElementById(`copy-${type}-btn`);
    const copiedMessage = document.getElementById(`copied-${type}-msg`);

    if (copyButton && textElement && copiedMessage) {
      copyButton.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(textElement.textContent);
          copiedMessage.style.opacity = '1';
          setTimeout(() => copiedMessage.style.opacity = '0', 1000);
        } catch (err) {
          console.error('Failed to copy:', err);
        }
      });
    }
  });
};

// Initialize all functionality once DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  // Hero image gallery - randomly select one image per page load
  const heroImages = [
    { src: 'images/zakopane.webp', date: '08-01-2024' },
    { src: 'images/persianshields.webp', date: '09-08-2024' },
    { src: 'images/garden.webp', date: '09-08-2024' }
  ];
  
  const randomImage = heroImages[Math.floor(Math.random() * heroImages.length)];
  const heroImage = document.getElementById('hero-image');
  const heroCaption = document.querySelector('.hero-caption');
  
  if (heroImage) {
    heroImage.style.backgroundImage = `url("${randomImage.src}")`;
  }
  if (heroCaption) {
    heroCaption.textContent = `taken by me on ${randomImage.date}`;
  }

  // Setup copy buttons
  setupCopyButtons();

  // Project collapse functionality
  document.querySelectorAll('.project-header-clickable').forEach(header => {
    const toggleProject = () => {
      const projectCard = header.closest('.project-card');
      const isExpanded = projectCard.classList.contains('expanded');

      if (isExpanded) {
        // Collapse
        projectCard.classList.remove('expanded');
        projectCard.classList.add('collapsed');
        header.setAttribute('aria-expanded', 'false');
      } else {
        // Expand
        projectCard.classList.add('expanded');
        projectCard.classList.remove('collapsed');
        header.setAttribute('aria-expanded', 'true');
      }
    };

    header.addEventListener('click', (e) => {
      // Don't trigger on links
      if (e.target.tagName === 'A' || e.target.closest('a')) return;
      toggleProject();
      e.stopPropagation();
    });

    // Keyboard navigation
    header.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleProject();
      }
    });
  });


  // PII Redaction Animation
  const [redactableElements, shieldStatus, shieldButton] = [
    document.querySelectorAll('.pii-redactable'),
    document.getElementById('shield-status'),
    document.getElementById('shield-toggle')
  ];

  if (redactableElements.length && shieldStatus && shieldButton) {
    let isRedacted = false;
    shieldStatus.classList.add('inactive');

    shieldButton.addEventListener('click', () => {
      isRedacted = !isRedacted;
      shieldStatus.classList.toggle('active', isRedacted);
      shieldStatus.classList.toggle('inactive', !isRedacted);
      shieldStatus.textContent = isRedacted ? 'ON' : 'OFF';

      redactableElements.forEach(element => {
        element.classList.toggle('redacted', isRedacted);
        element.textContent = isRedacted ? element.dataset.redacted : element.dataset.original;
      });
    });
  }
});
