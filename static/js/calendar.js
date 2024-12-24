// API configuration
const API_BASE_URL = 'https://your-backend-api.herokuapp.com'; // You'll need to replace this with your actual API URL

class Calendar {
    constructor() {
        this.today = new Date();
        this.currentDate = new Date();
        this.currentDate.setDate(this.currentDate.getDate() - this.currentDate.getDay() + 1);
        this.notes = {};
        this.maxMonthsRange = 2;
        this.saveTimeout = null;
        this.currentModalContext = null;
        
        this.initializeCalendar();
        this.loadNotes();
        this.addEventListeners();
        this.initializeModal();
    }
    
    initializeCalendar() {
        this.updateWeekTitle();
        this.renderWeek();
    }
    
    async loadNotes() {
        try {
            const response = await fetch(`${API_BASE_URL}/calendar/notes`);
            if (!response.ok) throw new Error('Failed to load notes');
            const data = await response.json();
            this.notes = data;
            this.renderWeek();
        } catch (error) {
            console.error('Error loading notes:', error);
            alert('Failed to load calendar notes. Please try again later.');
        }
    }
    
    updateWeekTitle() {
        const startDate = new Date(this.currentDate);
        const endDate = new Date(this.currentDate);
        endDate.setDate(endDate.getDate() + 6);
        
        const formatDate = (date) => {
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            return `${months[date.getMonth()]} ${date.getDate()}`;
        };
        
        document.getElementById('currentWeek').textContent = 
            `${formatDate(startDate)} - ${formatDate(endDate)}`;
    }
    
    isDateInRange(date) {
        const minDate = new Date();
        const maxDate = new Date();
        minDate.setMonth(minDate.getMonth() - this.maxMonthsRange);
        maxDate.setMonth(maxDate.getMonth() + this.maxMonthsRange);
        return date >= minDate && date <= maxDate;
    }
    
    renderWeek() {
        const weekDays = document.getElementById('weekDays');
        weekDays.innerHTML = '';
        
        const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
        
        for (let i = 0; i < 7; i++) {
            const date = new Date(this.currentDate);
            date.setDate(date.getDate() + i);
            
            if (!this.isDateInRange(date)) {
                continue;
            }
            
            const dateString = date.toISOString().split('T')[0];
            const isToday = date.toDateString() === this.today.toDateString();
            const note = this.notes[dateString] || {};
            const images = Array.isArray(note.images) ? note.images : [];
            const timestamp = Date.now();
            
            const dayCard = document.createElement('div');
            dayCard.className = `day-card${isToday ? ' today' : ''}`;
            dayCard.innerHTML = `
                <div class="day-header">
                    <div class="day-name">${days[date.getDay()]} <span class="date-number">${date.getDate()}</span></div>
                </div>
                <div class="day-content">
                    ${images.length > 0 ? `
                        <div class="image-grid">
                            ${images.slice(0, 3).map((img, index) => `
                                <div class="image-grid-item" data-index="${index}" data-image="${img}">
                                    <img src="${img}" alt="Daily image ${index + 1}">
                                    <button class="remove-image" data-date="${dateString}" data-index="${index}">
                                        <i class="fas fa-times"></i>
                                    </button>
                                    ${index === 2 && images.length > 3 ? `
                                        <div class="more-images">+${images.length - 3}</div>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                    <textarea class="day-note" data-date="${dateString}" 
                        placeholder="Write your note here...">${note.text || ''}</textarea>
                    <div class="image-upload-section">
                        <div class="image-actions">
                            <label for="image-${dateString}-${timestamp}" class="image-upload-label">
                                <i class="fas fa-image"></i>
                                <span>Upload Image</span>
                            </label>
                            <label for="camera-${dateString}-${timestamp}" class="image-upload-label">
                                <i class="fas fa-camera"></i>
                                <span>Take Photo</span>
                            </label>
                        </div>
                        <input type="file" id="image-${dateString}-${timestamp}" 
                            class="image-upload" accept="image/*" data-date="${dateString}">
                        <input type="file" id="camera-${dateString}-${timestamp}" 
                            class="image-upload" accept="image/*" capture="environment" data-date="${dateString}">
                    </div>
                </div>
                <div class="save-indicator">✓</div>
            `;
            
            // Add event listeners
            const textarea = dayCard.querySelector('.day-note');
            textarea.addEventListener('input', () => this.handleNoteChange(textarea));
            
            const imageInputs = dayCard.querySelectorAll('.image-upload');
            imageInputs.forEach(input => {
                input.addEventListener('change', (e) => this.handleImageUpload(e));
            });
            
            const removeButtons = dayCard.querySelectorAll('.remove-image');
            removeButtons.forEach(button => {
                button.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const index = parseInt(button.dataset.index);
                    this.removeImage(dateString, index);
                });
            });
            
            // Update image click handler
            const imageItems = dayCard.querySelectorAll('.image-grid-item');
            imageItems.forEach(item => {
                item.addEventListener('click', (e) => {
                    if (!e.target.matches('.remove-image, .remove-image *')) {
                        const index = parseInt(item.dataset.index);
                        const imageSrc = item.dataset.image;
                        openImageModal(imageSrc, index, images);
                    }
                });
            });
            
            weekDays.appendChild(dayCard);
        }
    }
    
    async handleImageUpload(event) {
        const file = event.target.files[0];
        const date = event.target.dataset.date;
        
        if (!file) return;
        
        try {
            const formData = new FormData();
            formData.append('image', file);
            formData.append('date', date);
            
            const response = await fetch(`${API_BASE_URL}/calendar/upload`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) throw new Error('Failed to upload image');
            
            const data = await response.json();
            const currentNote = this.notes[date] || {};
            const currentImages = Array.isArray(currentNote.images) ? currentNote.images : [];
            
            this.notes[date] = {
                ...currentNote,
                images: [...currentImages, data.image_url]
            };
            this.renderWeek();
        } catch (error) {
            console.error('Error uploading image:', error);
            alert('Failed to upload image. Please try again.');
        }
    }
    
    async removeImage(date, index) {
        try {
            const note = this.notes[date];
            if (!note || !note.images) return;
            
            const response = await fetch(`${API_BASE_URL}/calendar/remove-image`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ date, index })
            });
            
            if (!response.ok) throw new Error('Failed to remove image');
            
            note.images.splice(index, 1);
            if (note.images.length === 0) {
                delete note.images;
            }
            this.renderWeek();
        } catch (error) {
            console.error('Error removing image:', error);
            alert('Failed to remove image. Please try again.');
        }
    }
    
    async handleNoteChange(textarea) {
        const date = textarea.dataset.date;
        const text = textarea.value.trim();
        const saveIndicator = textarea.closest('.day-card').querySelector('.save-indicator');
        
        if (this.saveTimeout) {
            clearTimeout(this.saveTimeout);
        }
        
        this.saveTimeout = setTimeout(async () => {
            try {
                const currentNote = this.notes[date] || {};
                const noteToSave = {
                    text: text,
                    images: Array.isArray(currentNote.images) ? currentNote.images : []
                };
                
                const response = await fetch(`${API_BASE_URL}/calendar/notes`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        date: date,
                        note: noteToSave
                    })
                });
                
                if (!response.ok) throw new Error('Failed to save note');
                
                this.notes[date] = noteToSave;
                saveIndicator.classList.add('show');
                setTimeout(() => {
                    saveIndicator.classList.remove('show');
                }, 1000);
            } catch (error) {
                console.error('Error saving note:', error);
                alert('Failed to save note. Please try again.');
            }
        }, 500);
    }
    
    addEventListeners() {
        // Navigation
        document.getElementById('prevWeek').addEventListener('click', () => {
            const newDate = new Date(this.currentDate);
            newDate.setDate(newDate.getDate() - 7);
            if (this.isDateInRange(newDate)) {
                this.currentDate = newDate;
                this.initializeCalendar();
            }
        });
        
        document.getElementById('nextWeek').addEventListener('click', () => {
            const newDate = new Date(this.currentDate);
            newDate.setDate(newDate.getDate() + 7);
            if (this.isDateInRange(newDate)) {
                this.currentDate = newDate;
                this.initializeCalendar();
            }
        });
    }
    
    initializeModal() {
        if (!document.getElementById('imageModal')) {
            const modal = document.createElement('div');
            modal.id = 'imageModal';
            modal.className = 'image-modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <img class="modal-image" src="" alt="Full size image">
                    <button class="modal-close">&times;</button>
                    <button class="modal-nav prev">
                        <i class="fas fa-chevron-left"></i>
                    </button>
                    <button class="modal-nav next">
                        <i class="fas fa-chevron-right"></i>
                    </button>
                </div>
            `;
            document.body.appendChild(modal);

            // Event listeners
            modal.querySelector('.modal-close').addEventListener('click', () => this.closeModal());
            modal.querySelector('.modal-nav.prev').addEventListener('click', () => this.navigateModal(-1));
            modal.querySelector('.modal-nav.next').addEventListener('click', () => this.navigateModal(1));
            modal.addEventListener('click', (e) => {
                if (e.target === modal) this.closeModal();
            });

            // Keyboard navigation
            document.addEventListener('keydown', (e) => {
                if (!modal.classList.contains('active')) return;
                if (e.key === 'Escape') this.closeModal();
                if (e.key === 'ArrowLeft') this.navigateModal(-1);
                if (e.key === 'ArrowRight') this.navigateModal(1);
            });
        }
    }
    
    openModal(date, index) {
        const images = this.notes[date]?.images || [];
        if (!images.length) return;

        const modal = document.getElementById('imageModal');
        const modalImage = modal.querySelector('.modal-image');
        const navButtons = modal.querySelectorAll('.modal-nav');

        this.currentModalContext = { date, images, currentIndex: index };
        modalImage.src = images[index];
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Show/hide navigation buttons
        navButtons.forEach(btn => {
            btn.style.display = images.length > 1 ? 'flex' : 'none';
        });
    }
    
    closeModal() {
        const modal = document.getElementById('imageModal');
        modal.classList.remove('active');
        document.body.style.overflow = '';
        this.currentModalContext = null;
    }
    
    navigateModal(direction) {
        if (!this.currentModalContext) return;

        const { images, currentIndex } = this.currentModalContext;
        const newIndex = (currentIndex + direction + images.length) % images.length;
        
        this.currentModalContext.currentIndex = newIndex;
        const modalImage = document.querySelector('.modal-image');
        modalImage.src = images[newIndex];
    }
}

// Initialize calendar when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new Calendar();
}); 

function openImageModal(imageSrc, imageIndex, allImages) {
    const modal = document.querySelector('.image-modal');
    const modalImage = document.querySelector('.modal-image');
    const prevButton = document.querySelector('.modal-nav.prev');
    const nextButton = document.querySelector('.modal-nav.next');
    const closeButton = document.querySelector('.modal-close');
    
    currentImageIndex = imageIndex;
    currentDayImages = allImages;
    
    modalImage.src = imageSrc;
    modal.classList.add('show');
    document.body.classList.add('modal-open');
    
    // Update navigation buttons visibility
    updateNavigationButtons();
    
    // Add event listeners
    document.addEventListener('keydown', handleModalKeyPress);
    
    // Add close button event listener
    closeButton.addEventListener('click', closeImageModal);
    
    // Add click outside modal to close
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            closeImageModal();
        }
    });

    // Add navigation button event listeners
    prevButton.addEventListener('click', showPreviousImage);
    nextButton.addEventListener('click', showNextImage);
}

function closeImageModal() {
    const modal = document.querySelector('.image-modal');
    const closeButton = document.querySelector('.modal-close');
    const prevButton = document.querySelector('.modal-nav.prev');
    const nextButton = document.querySelector('.modal-nav.next');
    
    modal.classList.remove('show');
    document.body.classList.remove('modal-open');
    document.removeEventListener('keydown', handleModalKeyPress);
    closeButton.removeEventListener('click', closeImageModal);
    prevButton.removeEventListener('click', showPreviousImage);
    nextButton.removeEventListener('click', showNextImage);
}

function handleModalKeyPress(e) {
    if (e.key === 'Escape') {
        closeImageModal();
    } else if (e.key === 'ArrowLeft') {
        showPreviousImage();
    } else if (e.key === 'ArrowRight') {
        showNextImage();
    }
}

function showPreviousImage() {
    if (currentImageIndex > 0) {
        currentImageIndex--;
        const modalImage = document.querySelector('.modal-image');
        modalImage.src = currentDayImages[currentImageIndex];
        updateNavigationButtons();
    }
}

function showNextImage() {
    if (currentImageIndex < currentDayImages.length - 1) {
        currentImageIndex++;
        const modalImage = document.querySelector('.modal-image');
        modalImage.src = currentDayImages[currentImageIndex];
        updateNavigationButtons();
    }
}

function updateNavigationButtons() {
    const prevButton = document.querySelector('.modal-nav.prev');
    const nextButton = document.querySelector('.modal-nav.next');
    
    if (prevButton && nextButton) {
        prevButton.style.display = currentImageIndex === 0 ? 'none' : 'flex';
        nextButton.style.display = currentImageIndex === currentDayImages.length - 1 ? 'none' : 'flex';
    }
} 