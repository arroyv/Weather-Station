// Utility: Convert month number (1-12) to short month name
function monthLabel(num) {
  const monthItself = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return monthItself[num - 1] || num;
}

// Fetch monthly stats JSON from Flask backend
fetch('/monthly-stats')
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(data => {

    const labels = data.months.map(m => monthLabel(m));

    // CO2 Chart
    new Chart(document.getElementById('co2Chart').getContext('2d'), {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'CO2 (ppm)',
          data: data["CO2"],
          backgroundColor: 'rgba(255, 99, 132, 0.6)',
          borderColor: 'rgba(255, 99, 132, 1)',
          borderWidth: 1,
          hoverBackgroundColor: 'rgba(255, 99, 132, 0.8)'
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: { 
            beginAtZero: true,
            title: { display: true, text: 'CO2 (ppm)' }
          },
          x: {
            title: { display: true, text: 'Month' }
          }
        }
      }
    });

    // Atmospheric Pressure Chart
    new Chart(document.getElementById('pressureChart').getContext('2d'), {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Atmospheric Pressure (hPa)',
          data: data['Atmospheric Pressure'],
          backgroundColor: 'rgba(54, 162, 235, 0.6)',
          borderColor: 'rgba(54, 162, 235, 1)',
          borderWidth: 1,
          hoverBackgroundColor: 'rgba(54, 162, 235, 0.8)'
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: { 
            beginAtZero: true,
            title: { display: true, text: 'Pressure (hPa)' }
          },
          x: {
            title: { display: true, text: 'Month' }
          }
        }
      }
    });

    // Wind Speed Chart
    new Chart(document.getElementById('windSpeedChart').getContext('2d'), {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Wind Speed (km/h)',
          data: data['Wind Speed'],
          backgroundColor: 'rgba(75, 192, 192, 0.6)',
          borderColor: 'rgba(75, 192, 192, 1)',
          borderWidth: 1,
          hoverBackgroundColor: 'rgba(75, 192, 192, 0.8)'
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: { 
            beginAtZero: true,
            title: { display: true, text: 'Wind Speed (MPH)' }
          },
          x: {
            title: { display: true, text: 'Month' }
          }
        }
      }
    });

    // Wind Direction Chart
    new Chart(document.getElementById('windDirectionChart').getContext('2d'), {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Wind Direction (MPH)',
          data: data['Wind Direction'],
          backgroundColor: 'rgba(153, 102, 255, 0.6)',
          borderColor: 'rgba(153, 102, 255, 1)',
          borderWidth: 1,
          hoverBackgroundColor: 'rgba(153, 102, 255, 0.8)'
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: { 
            beginAtZero: true,
            title: { display: true, text: 'Wind Direction (°)' }
          },
          x: {
            title: { display: true, text: 'Month' }
          }
        }
      }
    });

  })
  .catch(error => {
    console.error('Error loading monthly sensor stats:', error);
  });

