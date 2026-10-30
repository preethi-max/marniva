function showToast(message, variant = 'info') {
    const toast = document.createElement('div');
    toast.className = `alert alert-${variant} mt-3`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2600);
}

function safeJson(response) {
    return response.json().then((data) => ({ data, ok: response.ok }));
}
