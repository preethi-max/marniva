document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('fleetForm');
    const container = document.getElementById('fleetAlternatives');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const payload = Object.fromEntries(new FormData(form).entries());
        const response = await fetch('/api/fleet-sim', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();

        if (!result.alternatives) {
            container.innerHTML = '<p class="text-danger">Unable to compare alternatives.</p>';
            return;
        }

        const recommended = result.alternatives[0];
        container.innerHTML = `
            <table class="table table-borderless">
                <thead>
                    <tr><th>Option</th><th>Speed</th><th>Fuel (t)</th><th>CO2 (t)</th><th>Cost (USD)</th></tr>
                </thead>
                <tbody>
                    ${result.alternatives.map((item) => `
                        <tr class="${item === recommended ? 'table-success' : ''}">
                            <td>${item.label}${item === recommended ? ' ★ Recommended' : ''}</td>
                            <td>${item.speed} kn</td>
                            <td>${item.fuel_consumed_tons}</td>
                            <td>${item.emissions_tco2}</td>
                            <td>$${item.estimated_cost_usd.toLocaleString()}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    });
});
