document.addEventListener('DOMContentLoaded', () => {
    const shipSelect = document.getElementById('fuelShipSelect');
    const form = document.getElementById('fuelForm');
    const summaryBox = document.getElementById('fuelSummary');
    const portBox = document.getElementById('portCompatibility');

    async function loadFuelData() {
        const shipId = shipSelect.value;
        const response = await fetch(`/api/fuel-analysis?ship_id=${shipId}`);
        const data = await response.json();
        if (!data.ship) {
            summaryBox.innerHTML = '<p class="text-danger">Fuel data unavailable.</p>';
            return;
        }

        const ship = data.ship;
        summaryBox.innerHTML = `
            <div class="card bg-light p-3">
                <h6>${ship.name}</h6>
                <p>Fuel type: ${ship.fuel_type}</p>
                <p>Capacity: ${ship.fuel_capacity_tons} t</p>
                <p>Current quantity: ${ship.current_fuel_tons} t</p>
                <p>Consumption rate: ${ship.speed_knots * 4.8} t/day</p>
            </div>
        `;

        const portHtml = data.port_options.map((port) => `
            <div class="mini-alert ${port.compatible ? 'border-success' : 'border-danger'}">
                <strong>${port.port}</strong>
                <span>${port.fuel_type}</span>
                <small>${port.compatible ? 'Compatible fuel available' : 'Warning: incompatible fuel type'}</small>
            </div>
        `).join('');
        portBox.innerHTML = portHtml;

        const fuelLabels = ['Current', 'Predicted', 'Reserve', 'Voyage'];
        const fuelData = [ship.current_fuel_tons, data.prediction.predicted_fuel_tons, data.status.required_tons, data.status.remaining_range_nm];
        new Chart(document.getElementById('fuelPredictionChart'), {
            type: 'bar',
            data: {
                labels: fuelLabels,
                datasets: [{
                    label: 'Fuel estimate (t)',
                    data: fuelData,
                    backgroundColor: ['#0d6aa6', '#2dbd9b', '#f4b942', '#d84b5b'],
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }

    shipSelect.addEventListener('change', loadFuelData);

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const shipId = shipSelect.value;
        const params = new URLSearchParams({
            ship_id: shipId,
            distance: document.getElementById('distanceInput').value,
            speed: document.getElementById('speedInput').value,
            weather: document.getElementById('weatherInput').value,
            planned_distance: document.getElementById('plannedDistanceInput').value,
        });
        const response = await fetch(`/api/fuel-analysis?${params.toString()}`);
        const data = await response.json();
        const warning = data.status.warning;
        if (warning) {
            showToast(warning, data.status.sufficient_for_voyage ? 'success' : 'warning');
        }
        await loadFuelData();
    });

    loadFuelData();
});
