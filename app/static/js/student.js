// Student Feedback Form Interactive Handling

document.addEventListener('DOMContentLoaded', function () {
  const ratingInputs = document.querySelectorAll('.star-rating-input input[type="radio"]');
  const ratingDescription = document.getElementById('rating-description');
  const commentsInput = document.getElementById('comments');
  const charCounter = document.getElementById('char-counter');

  const ratingLabels = {
    '5': '⭐⭐⭐⭐⭐ (5 - Excellent)',
    '4': '⭐⭐⭐⭐ (4 - Good)',
    '3': '⭐⭐⭐ (3 - Average)',
    '2': '⭐⭐ (2 - Poor)',
    '1': '⭐ (1 - Terrible)'
  };

  // Sync star rating selection with text description
  if (ratingInputs && ratingDescription) {
    ratingInputs.forEach(function (radio) {
      if (radio.checked) {
        ratingDescription.textContent = ratingLabels[radio.value] || '';
      }
      radio.addEventListener('change', function () {
        if (this.checked) {
          ratingDescription.textContent = ratingLabels[this.value] || '';
          ratingDescription.classList.add('text-primary');
        }
      });
    });
  }

  // Comments live character counter
  if (commentsInput && charCounter) {
    const updateCounter = function () {
      const len = commentsInput.value.length;
      charCounter.textContent = `${len} / 1000 characters`;
      if (len > 1000) {
        charCounter.classList.add('text-danger');
        charCounter.classList.remove('text-muted');
      } else {
        charCounter.classList.remove('text-danger');
        charCounter.classList.add('text-muted');
      }
    };

    commentsInput.addEventListener('input', updateCounter);
    updateCounter();
  }

  // Auto-sync assigned faculty when a subject/course is selected
  const courseSelect = document.getElementById('course_id');
  const facultySelect = document.getElementById('faculty_id');
  if (courseSelect && facultySelect && window.COURSE_FACULTY_MAP) {
    courseSelect.addEventListener('change', function () {
      const selectedCourseId = this.value;
      const assignedFacultyId = window.COURSE_FACULTY_MAP[selectedCourseId];
      if (assignedFacultyId) {
        facultySelect.value = assignedFacultyId;
      }
    });

    // If pre-selected on page load
    if (courseSelect.value && window.COURSE_FACULTY_MAP[courseSelect.value]) {
      facultySelect.value = window.COURSE_FACULTY_MAP[courseSelect.value];
    }
  }
});
