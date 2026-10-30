function showToast(message, variant = 'info') {
    let region = document.querySelector('.toast-region');
    if (!region) {
        region = document.createElement('div');
        region.className = 'toast-region';
        document.body.appendChild(region);
    }
    const toast = document.createElement('div');
    toast.className = `marinva-toast ${variant}`;
    toast.innerHTML = `<span>${variant === 'success' ? '✓' : variant === 'error' || variant === 'danger' ? '!' : 'i'}</span><p>${message}</p>`;
    region.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('visible'));
    setTimeout(() => { toast.classList.remove('visible'); setTimeout(() => toast.remove(), 220); }, 3000);
}

function safeJson(response) {
    return response.json().then((data) => ({ data, ok: response.ok }));
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nav-link').forEach(link => {
        const icon = {Dashboard:'⌂', 'Green Fleet':'◉', 'AI Fuel':'◫', 'Emergency':'△', 'Training':'◆', 'Reports':'▥', 'Settings':'⚙'}[link.textContent.trim()];
        if (icon && !link.querySelector('.nav-icon')) link.insertAdjacentHTML('afterbegin', `<span class="nav-icon" aria-hidden="true">${icon}</span>`);
    });
    const topBar = document.querySelector('.top-bar');
    const sidebar = document.querySelector('.sidebar');
    if (topBar && sidebar && !topBar.querySelector('.mobile-menu-button')) {
        const button = document.createElement('button');
        button.className = 'mobile-menu-button'; button.type = 'button'; button.setAttribute('aria-label', 'Toggle navigation'); button.innerHTML = '☰';
        topBar.prepend(button);
        button.addEventListener('click', () => sidebar.classList.toggle('open'));
    }
    if (topBar && !topBar.querySelector('.global-search')) {
        const search = document.createElement('div'); search.className = 'global-search'; search.innerHTML = '<span>⌕</span>&nbsp; Search operations'; topBar.appendChild(search);
        const notification = document.createElement('button'); notification.type = 'button'; notification.className = 'notification-button'; notification.setAttribute('aria-label', 'View notifications'); notification.textContent = '◦'; notification.addEventListener('click', () => showToast('No new critical maritime alerts.', 'info')); topBar.appendChild(notification);
        const profile = document.createElement('div'); profile.className = 'top-profile'; profile.innerHTML = '<span class="top-profile-avatar">M</span><span class="top-profile-copy"><strong>MARINVA User</strong><small>Authenticated session</small></span>'; topBar.appendChild(profile);
    }
    document.querySelectorAll('.card .card-header-row > span:not(.status-chip)').forEach(label => label.classList.add('subtle-label'));
});
