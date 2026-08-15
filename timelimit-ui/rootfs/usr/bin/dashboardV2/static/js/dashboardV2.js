/* DashboardV2 JavaScript - Essential interactions only */

/**
 * DashboardV2 JavaScript module
 * Provides minimal JavaScript for essential interactions:
 * - Form submissions
 * - Data refresh
 * - Server selection
 */

(function() {
    'use strict';

    // Configuration
    const API_BASE = '/api';
    
    /**
     * Make an API request
     * @param {string} endpoint - API endpoint
     * @param {string} method - HTTP method
     * @param {Object} data - Request data
     * @returns {Promise<Object>} Response data
     */
    async function apiRequest(endpoint, method = 'GET', data = null) {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(API_BASE + endpoint, options);
        return await response.json();
    }
    
    /**
     * Select a server
     * @param {string} serverKey - Server key (local, official, debug)
     */
    async function selectServer(serverKey) {
        try {
            await apiRequest('/select-server', 'POST', { server_key: serverKey });
            // Reload page to apply server selection
            location.reload();
        } catch (error) {
            console.error('Failed to select server:', error);
        }
    }
    
    /**
     * Refresh dashboard data
     */
    async function refreshData() {
        try {
            const response = await apiRequest('/time', 'POST', {});
            console.log('Server time:', response);
        } catch (error) {
            console.error('Failed to refresh data:', error);
        }
    }
    
    /**
     * Clear session
     */
    async function clearSession() {
        try {
            await apiRequest('/session/clear', 'POST');
            location.reload();
        } catch (error) {
            console.error('Failed to clear session:', error);
        }
    }
    
    // Expose functions globally
    window.dashboardV2 = {
        selectServer: selectServer,
        refreshData: refreshData,
        clearSession: clearSession,
        apiRequest: apiRequest
    };
    
    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        console.log('DashboardV2 initialized');
    });

})();