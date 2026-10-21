// Administrator Analytics with Chart.js

document.addEventListener('DOMContentLoaded', function () {
  const ratingDistCanvas = document.getElementById('ratingDistributionChart');
  const facultyRatingsCanvas = document.getElementById('facultyRatingsChart');
  const courseRatingsCanvas = document.getElementById('courseRatingsChart');

  if (!ratingDistCanvas && !facultyRatingsCanvas && !courseRatingsCanvas) {
    return;
  }

  fetch('/admin/analytics/data')
    .then(response => {
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      return response.json();
    })
    .then(data => {
      // 1. Rating Distribution Chart (Doughnut)
      if (ratingDistCanvas) {
        const counts = data.rating_distribution;
        new Chart(ratingDistCanvas, {
          type: 'doughnut',
          data: {
            labels: ['1 Star (Terrible)', '2 Stars (Poor)', '3 Stars (Average)', '4 Stars (Good)', '5 Stars (Excellent)'],
            datasets: [{
              data: [counts['1'], counts['2'], counts['3'], counts['4'], counts['5']],
              backgroundColor: [
                '#ef4444', // Red
                '#f97316', // Orange
                '#f59e0b', // Amber
                '#10b981', // Green
                '#059669'  // Dark green
              ],
              borderWidth: 2,
              borderColor: '#ffffff'
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: {
                position: 'bottom',
                labels: {
                  boxWidth: 14,
                  font: { size: 12 }
                }
              },
              tooltip: {
                callbacks: {
                  label: function (context) {
                    const label = context.label || '';
                    const value = context.parsed || 0;
                    return ` ${label}: ${value} submissions`;
                  }
                }
              }
            }
          }
        });
      }

      // 2. Faculty Average Ratings Chart (Horizontal Bar)
      if (facultyRatingsCanvas && data.faculty_ratings.labels.length > 0) {
        new Chart(facultyRatingsCanvas, {
          type: 'bar',
          data: {
            labels: data.faculty_ratings.labels,
            datasets: [{
              label: 'Average Rating (out of 5.0)',
              data: data.faculty_ratings.averages,
              backgroundColor: 'rgba(79, 70, 229, 0.85)',
              borderColor: '#4338ca',
              borderWidth: 1,
              borderRadius: 6
            }]
          },
          options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                min: 0,
                max: 5,
                ticks: { stepSize: 1 },
                grid: { color: '#e2e8f0' }
              },
              y: {
                grid: { display: false }
              }
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: function (ctx) {
                    return ` Average Rating: ${ctx.parsed.x} / 5.0`;
                  }
                }
              }
            }
          }
        });
      }

      // 3. Course Average Ratings Chart (Vertical Bar)
      if (courseRatingsCanvas && data.course_ratings.labels.length > 0) {
        new Chart(courseRatingsCanvas, {
          type: 'bar',
          data: {
            labels: data.course_ratings.labels,
            datasets: [{
              label: 'Course Rating',
              data: data.course_ratings.averages,
              backgroundColor: 'rgba(16, 185, 129, 0.85)',
              borderColor: '#059669',
              borderWidth: 1,
              borderRadius: 6
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              y: {
                min: 0,
                max: 5,
                ticks: { stepSize: 1 },
                grid: { color: '#e2e8f0' }
              },
              x: {
                grid: { display: false }
              }
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: function (ctx) {
                    return ` Average Rating: ${ctx.parsed.y} / 5.0`;
                  }
                }
              }
            }
          }
        });
      }
    })
    .catch(err => {
      console.error('Error fetching analytics data:', err);
    });
});
