document.addEventListener('DOMContentLoaded', () => {
    const fuelLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
    const fuelData = [320, 300, 280, 310, 295, 350];
    const emissionsData = [540, 560, 530, 580, 610, 660];

    new Chart(document.getElementById('consumptionChart'), {
        type: 'line',
        data: {
            labels: fuelLabels,
            datasets: [{
                label: 'Fleet fuel usage (t)',
                data: fuelData,
                borderColor: '#0d6aa6',
                backgroundColor: 'rgba(13, 106, 166, 0.15)',
                tension: 0.35,
                fill: true,
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });

    new Chart(document.getElementById('emissionsChart'), {
        type: 'bar',
        data: {
            labels: fuelLabels,
            datasets: [{
                label: 'CO2 (t)',
                data: emissionsData,
                backgroundColor: '#2dbd9b',
            }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });

    fetch('/api/dashboard-data')
        .then((response) => response.json())
        .then((data) => {
            document.getElementById('totalShips').textContent = data.total_ships;
            document.getElementById('activeShips').textContent = data.active_ships;
            document.getElementById('fleetFuel').textContent = `${data.fleet_fuel} t`;
            document.getElementById('emissions').textContent = `${data.estimated_emissions} t`;
            document.getElementById('carbonBudget').textContent = `${data.carbon_budget}%`;
            document.getElementById('fuelAlerts').textContent = data.fuel_alerts;
            document.getElementById('emergencyAlerts').textContent = data.emergency_alerts;
            document.getElementById('trainingCompletion').textContent = `${data.training_completion}%`;
        })
        .catch(() => showToast('Dashboard summary unavailable.', 'warning'));
});
