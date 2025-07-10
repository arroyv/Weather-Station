function fetchLatestData() {
    fetch('/latest-data')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('No data found');
                return;
            }

            document.getElementById('co2').textContent = data['CO2'];
            document.getElementById('pressure').textContent = data['Atmospheric Pressure'];
            document.getElementById('wind_speed').textContent = data['Wind Speed'];
            document.getElementById('wind_direction').textContent = data['Wind Direction'];
        })
        .catch(error => console.error('Error fetching data:', error));
}

// Fetch data every 5 seconds
setInterval(fetchLatestData, 5000);

// Fetch once on page load
fetchLatestData();

