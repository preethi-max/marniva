document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('emergencyForm');
    const vesselBox = document.getElementById('assistingVessels');
    const portBox = document.getElementById('recommendedPorts');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const payload = {
            ship_id: document.getElementById('affectedShip').value,
            emergency_type: document.getElementById('emergencyType').value,
            weather: document.getElementById('emergencyWeather').value,
        };
        const response = await fetch('/api/emergency-sim', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();

        vesselBox.innerHTML = result.recommended_vessels.map((vessel) => `
            <div class="mini-alert">
                <strong>${vessel.name}</strong>
                <span>Distance: ${vessel.distance_nm} nm</span>
                <small>Arrival: ${vessel.arrival_hours} h | Suitability: ${vessel.suitability_score}</small>
            </div>
        `).join('');

        portBox.innerHTML = result.recommended_ports.map((port) => `
            <div class="mini-alert">
                <strong>${port.port_name}</strong>
                <span>Distance: ${port.distance_nm} nm</span>
                <small>${port.emergency_services} | Suitability: ${port.suitability_score}</small>
            </div>
        `).join('');
    });
});
