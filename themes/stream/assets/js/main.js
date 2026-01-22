// Convert timestamps to relative time
function timeAgo(timestamp) {
    const now = Math.floor(Date.now() / 1000);
    const seconds = now - timestamp;

    if (seconds < 60) {
        return 'just now';
    }

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) {
        return minutes === 1 ? '1 minute ago' : `${minutes} minutes ago`;
    }

    const hours = Math.floor(minutes / 60);
    if (hours < 24) {
        return hours === 1 ? '1 hour ago' : `${hours} hours ago`;
    }

    const days = Math.floor(hours / 24);
    if (days < 30) {
        return days === 1 ? '1 day ago' : `${days} days ago`;
    }

    const months = Math.floor(days / 30);
    if (months < 12) {
        return months === 1 ? '1 month ago' : `${months} months ago`;
    }

    const years = Math.floor(months / 12);
    return years === 1 ? '1 year ago' : `${years} years ago`;
}

// Update all timestamps on the page
function updateTimestamps() {
    const timeElements = document.querySelectorAll('time[data-timestamp]');
    timeElements.forEach(el => {
        const timestamp = parseInt(el.getAttribute('data-timestamp'));
        el.textContent = timeAgo(timestamp);
    });
}

// Update timestamps when page loads and every minute
document.addEventListener('DOMContentLoaded', () => {
    updateTimestamps();
    setInterval(updateTimestamps, 60000); // Update every minute
});
