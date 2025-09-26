/**
 * Project Elysian Fields - JavaScript Functionality
 * Handles view toggling, dynamic content loading, and user interactions
 */

// Wait for DOM to be fully loaded before executing script
document.addEventListener('DOMContentLoaded', function() {
    'use strict';

    // Sample cemetery data - represents different memorial plots
    const cemeteryData = [
        {
            id: 'plot-001',
            name: 'Memorial for Eleanor Johnson',
            plot: 'Section A, Plot 15',
            born: 'March 15, 1942',
            died: 'August 22, 2024',
            epitaph: 'Beloved mother, grandmother, and friend. Her kindness touched all who knew her.',
            imageURL: 'https://via.placeholder.com/300x200/800020/E0E0E0?text=Eleanor+Johnson'
        },
        {
            id: 'plot-002',
            name: 'Memorial for Robert Chen',
            plot: 'Section B, Plot 8',
            born: 'November 3, 1955',
            died: 'June 14, 2024',
            epitaph: 'Devoted husband, loving father, and respected community leader. His legacy lives on.',
            imageURL: 'https://via.placeholder.com/300x200/800020/E0E0E0?text=Robert+Chen'
        },
        {
            id: 'plot-003',
            name: 'Memorial for Margaret Williams',
            plot: 'Section C, Plot 22',
            born: 'July 8, 1938',
            died: 'September 5, 2024',
            epitaph: 'A gentle soul who brought joy to everyone she met. Forever in our hearts.',
            imageURL: 'https://via.placeholder.com/300x200/800020/E0E0E0?text=Margaret+Williams'
        }
    ];

    // DOM element references
    const customerPortal = document.getElementById('customer-portal-view');
    const employeePortal = document.getElementById('employee-portal-view');

    /**
     * Shows the customer portal view and hides the employee portal view
     */
    function showCustomerPortal() {
        customerPortal.style.display = 'block';
        employeePortal.style.display = 'none';
        console.log('Switched to Customer Portal view');
    }

    /**
     * Shows the employee portal view and hides the customer portal view
     */
    function showEmployeePortal() {
        customerPortal.style.display = 'none';
        employeePortal.style.display = 'block';
        console.log('Switched to Employee Portal view');
    }

    /**
     * Loads and displays memorial data for a specific plot
     * @param {string} plotId - The ID of the plot to display
     */
    function loadMemorialData(plotId) {
        // Find the plot data by ID
        const plotData = cemeteryData.find(plot => plot.id === plotId);
        
        if (!plotData) {
            console.error(`Plot with ID "${plotId}" not found`);
            return;
        }

        // Update the memorial heading
        const memorialHeading = customerPortal.querySelector('h1');
        if (memorialHeading) {
            memorialHeading.textContent = plotData.name;
        }

        // Update the memorial photo
        const memorialPhoto = customerPortal.querySelector('.memorial-photo img');
        if (memorialPhoto) {
            memorialPhoto.src = plotData.imageURL;
            memorialPhoto.alt = `Memorial photo of ${plotData.name.split(' ').slice(-1)[0]}`;
        }

        // Update the transcribed data
        const transcribedData = customerPortal.querySelector('.transcribed-data');
        if (transcribedData) {
            const paragraphs = transcribedData.querySelectorAll('p');
            if (paragraphs.length >= 3) {
                paragraphs[0].innerHTML = `<strong>Born:</strong> ${plotData.born}`;
                paragraphs[1].innerHTML = `<strong>Died:</strong> ${plotData.died}`;
                paragraphs[2].innerHTML = `<strong>Epitaph:</strong> "${plotData.epitaph}"`;
            }
        }

        console.log(`Loaded memorial data for ${plotData.name} (${plotData.plot})`);
    }

    /**
     * Handles the floral arrangement order button click
     */
    function handleFloralOrderClick() {
        alert('This feature would open a detailed order form for the customer.');
    }

    /**
     * Handles the work order details button click
     */
    function handleWorkOrderDetailsClick() {
        alert('This would navigate to a detailed work order page with a map and task checklist.');
    }

    /**
     * Sets up keyboard shortcuts for view switching
     */
    function setupKeyboardShortcuts() {
        document.addEventListener('keydown', function(event) {
            // Check if user is typing in an input field (ignore shortcuts in that case)
            if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
                return;
            }

            switch(event.key.toLowerCase()) {
                case 'c':
                    showCustomerPortal();
                    break;
                case 'e':
                    showEmployeePortal();
                    break;
                default:
                    // Do nothing for other keys
                    break;
            }
        });

        console.log('Keyboard shortcuts enabled: Press "C" for Customer Portal, "E" for Employee Portal');
    }

    /**
     * Sets up event listeners for interactive elements
     */
    function setupEventListeners() {
        // Floral arrangement order button
        const floralOrderButton = customerPortal.querySelector('.customer-actions button');
        if (floralOrderButton) {
            floralOrderButton.addEventListener('click', handleFloralOrderClick);
        }

        // Work order detail buttons
        const workOrderButtons = employeePortal.querySelectorAll('.work-order-card button');
        workOrderButtons.forEach(button => {
            button.addEventListener('click', handleWorkOrderDetailsClick);
        });

        console.log('Event listeners attached to interactive elements');
    }

    /**
     * Initializes the application
     */
    function initialize() {
        // Load initial memorial data (first plot)
        loadMemorialData('plot-001');
        
        // Set up keyboard shortcuts
        setupKeyboardShortcuts();
        
        // Set up event listeners
        setupEventListeners();
        
        // Log initialization complete
        console.log('Project Elysian Fields demo initialized successfully');
        console.log('Available plots:', cemeteryData.map(plot => `${plot.id}: ${plot.name}`));
    }

    // Initialize the application
    initialize();

    // Expose functions globally for potential external use (optional)
    window.ElysianFields = {
        showCustomerPortal,
        showEmployeePortal,
        loadMemorialData,
        cemeteryData
    };

});
