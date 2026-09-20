/* DashboardV2 JavaScript - Essential interactions only */

/**
 * DashboardV2 JavaScript module
 * Provides minimal JavaScript for essential interactions:
 * - Form submissions
 * - Data refresh
 * - Server selection
 * - Users & Devices dashboard
 * 
 * Key change: Using device_auth_token as primary key instead of family_id,
 * matching the official Android app's approach where the server looks up
 * family from device using deviceAuthToken.
 */

(function() {
    'use strict';

    // Configuration
    const API_BASE = '/api';
    
    // Track authentication status
    let isAuthenticated = false;
    
    // Track whether parent password hash is set (required for device removal)
    let hasParentPasswordHash = false;
    
    // Store parent password hash in session (cleared on logout)
    let parentPasswordHash = null;
    
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
     * Check if user is authenticated
     * @returns {Promise<Object>} Session status data
     */
    async function checkAuthentication() {
        try {
            const response = await fetch('/api/session/status');
            const data = await response.json();
            isAuthenticated = data.authenticated || false;
            return data;
        } catch (error) {
            isAuthenticated = false;
            return { authenticated: false };
        }
    }
    
    /**
     * Show an alert message to the user
     * @param {string} message - Alert message
     * @param {string} type - Alert type: 'success', 'error', 'warning'
     */
    function showAlert(message, type) {
        const container = document.getElementById('alert-container');
        if (!container) return;
        
        const alert = document.createElement('div');
        alert.className = 'alert ' + type;
        alert.innerHTML = `
            ${message}
            <button class="alert-close" onclick="this.parentElement.remove()">&times;</button>
        `;
        
        container.appendChild(alert);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alert.parentElement) {
                alert.remove();
            }
        }, 5000);
    }
    
    /**
     * Update login status banner at the top of the dashboard
     * @param {Object} data - Session status data from API
     */
    function updateLoginStatusBanner(data) {
        const banner = document.getElementById('login-status-banner');
        const indicator = document.getElementById('login-banner-indicator');
        const message = document.getElementById('login-banner-message');
        
        if (!banner || !indicator || !message) {
            return;
        }
        
        if (data.login_error) {
            banner.style.display = 'block';
            indicator.className = 'status-indicator status-error';
            message.textContent = 'Login Failed: ' + data.login_error;
            message.style.color = '#f44336';
        } else if (data.authenticated) {
            banner.style.display = 'block';
            indicator.className = 'status-indicator status-success';
            message.textContent = 'Authenticated - Successfully logged in to family';
            message.style.color = '#00ff88';
        } else {
            banner.style.display = 'block';
            indicator.className = 'status-indicator status-warning';
            message.textContent = 'Not Authenticated - Please log in to access family data';
            message.style.color = '#ff9800';
        }
    }
    
    /**
     * Update session overview display with validation status
     * @param {Object} data - Session status data from API
     */
    function updateSessionOverview(data) {
        if (!data) {
            console.error('updateSessionOverview: No data provided');
            return;
        }
        
        // Update top Server Status section
        const statusIndicator = document.getElementById('status-indicator');
        const statusContent = document.getElementById('status-content');
        const errorMessage = document.getElementById('error-message');
        if (statusIndicator && statusContent) {
            if (data.server_url) {
                statusIndicator.className = 'status-indicator status-success';
                statusContent.innerHTML = '<div class="server-info">' +
                    '<span class="server-label">Server:</span>' +
                    '<span class="server-url" style="color: #00ff88; font-family: monospace; font-size: 12px;"> ' + escapeHtml(data.server_url) + '</span>' +
                    '</div>';
                if (errorMessage) {
                    errorMessage.style.display = 'none';
                }
            } else {
                statusIndicator.className = 'status-indicator status-warning';
                statusContent.innerHTML = '<div class="server-info">' +
                    '<span class="server-label">Server:</span>' +
                    '<span class="server-url" style="color: #ff9800; font-family: monospace; font-size: 12px;"> Not available</span>' +
                    '</div>';
                if (errorMessage) {
                    errorMessage.style.display = 'none';
                }
            }
        }
        
        // Update server status indicator and text
        const serverIndicator = document.getElementById('server-status-indicator');
        const serverStatusText = document.getElementById('server-status-text');
        if (serverIndicator && serverStatusText) {
            if (data.server_url) {
                serverIndicator.className = 'status-indicator status-success';
                serverStatusText.textContent = 'Server: ' + data.server_url;
            } else {
                serverIndicator.className = 'status-indicator status-warning';
                serverStatusText.textContent = 'Server: Not selected';
            }
        }
        
        // Update auth status indicator and text
        const authIndicator = document.getElementById('auth-status-indicator');
        const authStatusText = document.getElementById('auth-status-text');
        if (authIndicator && authStatusText) {
            if (data.has_device_auth_token) {
                authIndicator.className = 'status-indicator status-success';
                authStatusText.textContent = 'Auth: Authenticated';
            } else {
                authIndicator.className = 'status-indicator status-error';
                authStatusText.textContent = 'Auth: Not authenticated';
            }
        }
        
        // Update device auth token status indicator and text
        const deviceTokenIndicator = document.getElementById('device-token-status-indicator');
        const deviceTokenStatusText = document.getElementById('device-token-status-text');
        if (deviceTokenIndicator && deviceTokenStatusText) {
            if (data.has_device_auth_token) {
                deviceTokenIndicator.className = 'status-indicator status-success';
                deviceTokenStatusText.textContent = 'Device Token: Authenticated';
            } else {
                deviceTokenIndicator.className = 'status-indicator status-error';
                deviceTokenStatusText.textContent = 'Device Token: Not authenticated';
            }
        }
        
        // Update detailed field values and statuses
        // Server URL
        const serverUrlField = document.getElementById('field-server-url');
        const serverUrlStatus = document.getElementById('server-url-status');
        if (serverUrlField && serverUrlStatus) {
            if (data.server_url) {
                serverUrlField.textContent = data.server_url;
                serverUrlField.style.color = '#00ff88';
                serverUrlStatus.textContent = 'Valid - Server URL configured';
                serverUrlStatus.style.color = '#4caf50';
            } else {
                serverUrlField.textContent = '-';
                serverUrlField.style.color = '#888';
                serverUrlStatus.textContent = 'Missing - Select a server first';
                serverUrlStatus.style.color = '#ff9800';
            }
        }
        
        // Device Auth Token
        const deviceTokenField = document.getElementById('field-device-token');
        const deviceTokenStatus = document.getElementById('device-token-status');
        if (deviceTokenField && deviceTokenStatus) {
            if (data.has_device_auth_token && data.device_auth_token) {
                deviceTokenField.textContent = data.device_auth_token;
                deviceTokenField.style.color = '#00ff88';
                deviceTokenStatus.textContent = 'Valid - Device authenticated';
                deviceTokenStatus.style.color = '#4caf50';
            } else {
                deviceTokenField.textContent = '-';
                deviceTokenField.style.color = '#888';
                deviceTokenStatus.textContent = 'Missing - Sign in to get device token';
                deviceTokenStatus.style.color = '#ff9800';
            }
        }
        
        // Own Device ID
        const deviceIdField = document.getElementById('field-device-id');
        const deviceIdStatus = document.getElementById('device-id-status');
        if (deviceIdField && deviceIdStatus) {
            if (data.own_device_id) {
                deviceIdField.textContent = data.own_device_id;
                deviceIdField.style.color = '#00ff88';
                deviceIdStatus.textContent = 'Valid - Own device registered';
                deviceIdStatus.style.color = '#4caf50';
            } else {
                deviceIdField.textContent = '-';
                deviceIdField.style.color = '#888';
                deviceIdStatus.textContent = 'Missing - Device ID not set';
                deviceIdStatus.style.color = '#ff9800';
            }
        }
        
        // Update Mail Auth Token field
        const mailTokenField = document.getElementById('field-mail-token');
        const mailTokenStatus = document.getElementById('mail-token-status');
        if (mailTokenField && mailTokenStatus) {
            if (data.has_mail_auth_token && data.mail_auth_token) {
                mailTokenField.textContent = data.mail_auth_token;
                mailTokenField.style.color = '#00ff88';
                mailTokenStatus.textContent = 'Valid - Mail authentication token available';
                mailTokenStatus.style.color = '#4caf50';
            } else {
                mailTokenField.textContent = '-';
                mailTokenField.style.color = '#888';
                mailTokenStatus.textContent = 'Not available - Token cleared after family creation';
                mailTokenStatus.style.color = '#666';
            }
        }
        
        // Update Login Status field
        const loginStatusField = document.getElementById('field-login-status');
        const loginStatusMessage = document.getElementById('login-status-message');
        if (loginStatusField && loginStatusMessage) {
            if (data.login_error) {
                loginStatusField.textContent = 'Login Failed';
                loginStatusField.style.color = '#f44336';
                loginStatusMessage.textContent = 'Error: ' + data.login_error;
                loginStatusMessage.style.color = '#f44336';
            } else if (data.authenticated) {
                loginStatusField.textContent = 'Authenticated';
                loginStatusField.style.color = '#00ff88';
                loginStatusMessage.textContent = 'Successfully logged in to family';
                loginStatusMessage.style.color = '#4caf50';
            } else {
                loginStatusField.textContent = 'Not Authenticated';
                loginStatusField.style.color = '#ff9800';
                loginStatusMessage.textContent = 'Please log in to access family data';
                loginStatusMessage.style.color = '#ff9800';
            }
        }
        
        // Update Configured App Version field
        const appVersionField = document.getElementById('field-app-version');
        const appVersionStatus = document.getElementById('app-version-status');
        if (appVersionField && appVersionStatus) {
            if (data.configured_app_version !== undefined && data.configured_app_version !== null) {
                appVersionField.textContent = data.configured_app_version;
                appVersionField.style.color = '#667eea';
                appVersionStatus.textContent = 'Dashboard will report this version to server';
                appVersionStatus.style.color = '#667eea';
            } else {
                appVersionField.textContent = '0';
                appVersionField.style.color = '#888';
                appVersionStatus.textContent = 'Default version (0) - set DASHBOARD_APP_VERSION env var';
                appVersionStatus.style.color = '#888';
            }
        }
        
        // Update Parent Password Hash field (for device removal operations)
        const parentPasswordHashField = document.getElementById('field-parent-password-hash');
        const parentPasswordHashStatus = document.getElementById('parent-password-hash-status');
        if (parentPasswordHashField && parentPasswordHashStatus) {
            if (data.has_parent_password_second_hash) {
                parentPasswordHashField.textContent = data.parent_password_second_hash || '***';
                parentPasswordHashField.style.color = '#00ff88';
                parentPasswordHashStatus.textContent = 'Valid - Hash available for device removal';
                parentPasswordHashStatus.style.color = '#4caf50';
                // Update global flag for device removal
                hasParentPasswordHash = true;
            } else {
                parentPasswordHashField.textContent = '-';
                parentPasswordHashField.style.color = '#888';
                parentPasswordHashStatus.textContent = 'Not set - Required for device removal operations';
                parentPasswordHashStatus.style.color = '#ff9800';
                // Update global flag for device removal
                hasParentPasswordHash = false;
            }
        }
        
        // Update Signing Key field (for device registration)
        const signingKeyField = document.getElementById('field-signing-key');
        const signingKeyStatus = document.getElementById('signing-key-status');
        if (signingKeyField && signingKeyStatus) {
            if (data.has_signing_key) {
                signingKeyField.textContent = 'Available';
                signingKeyField.style.color = '#00ff88';
                signingKeyStatus.textContent = 'Curve25519 signing key generated for device';
                signingKeyStatus.style.color = '#4caf50';
            } else {
                signingKeyField.textContent = 'Not generated';
                signingKeyField.style.color = '#888';
                signingKeyStatus.textContent = 'Will be generated on first sync';
                signingKeyStatus.style.color = '#666';
            }
        }
        
        // Update Client Level field
        const clientLevelField = document.getElementById('field-client-level');
        const clientLevelStatus = document.getElementById('client-level-status');
        if (clientLevelField && clientLevelStatus) {
            clientLevelField.textContent = data.client_level || 7;
            clientLevelField.style.color = '#667eea';
            clientLevelStatus.textContent = 'Client version level for sync protocol';
            clientLevelStatus.style.color = '#667eea';
        }
        
        // Show/hide action links based on authentication status
        const createFamilyLink = document.getElementById('create-family-link');
        const loginExistingFamilyLink = document.getElementById('login-existing-family-link');
        const recoverPasswordLink = document.getElementById('recover-password-link');
        const signoutLink = document.getElementById('signout-link');
        const signInSection = document.getElementById('sign-in-section');
        
        if (createFamilyLink && loginExistingFamilyLink && recoverPasswordLink) {
            if (data.authenticated) {
                createFamilyLink.style.display = 'none';
                loginExistingFamilyLink.style.display = 'none';
                recoverPasswordLink.style.display = 'none';
                if (signoutLink) {
                    signoutLink.style.display = 'block';
                }
                // Hide the prominent sign-in section when authenticated
                if (signInSection) {
                    signInSection.style.display = 'none';
                }
            } else {
                createFamilyLink.style.display = 'block';
                loginExistingFamilyLink.style.display = 'block';
                recoverPasswordLink.style.display = 'block';
                if (signoutLink) {
                    signoutLink.style.display = 'none';
                }
                // Show the prominent sign-in section when not authenticated
                if (signInSection) {
                    signInSection.style.display = 'block';
                }
            }
        }
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
            showAlert('Failed to select server: ' + error.message, 'error');
        }
    }
    
    /**
     * Refresh dashboard data
     */
    async function refreshData() {
        try {
            await apiRequest('/time', 'POST', {});
        } catch (error) {
            console.error('Failed to refresh data:', error);
        }
    }
    
    /**
     * Clear session
     */
    async function clearSession() {
        try {
            const response = await apiRequest('/session/clear', 'POST');
            
            // Check if the response indicates success
            if (response && response.status === 'ok') {
                // Clear stored password hash
                parentPasswordHash = null;
                
                // Update authentication status
                isAuthenticated = false;
                
                // Update login status banner and session overview
                const sessionData = { authenticated: false };
                updateLoginStatusBanner(sessionData);
                updateSessionOverview(sessionData);
                
                // Show success message
                showAlert('Signed out successfully. Please sign in to continue.', 'success');
                
                // Stay on dashboard page - do NOT redirect to landing page
                // The user can manually navigate away if needed
            } else {
                showAlert('Failed to clear session: ' + (response?.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            showAlert('Failed to clear session: ' + error.message, 'error');
        }
    }
    
    /**
     * Clear all local data for a fresh start
     * @returns {Promise<Object>} Response data
     */
    async function clearAllData() {
        const response = await fetch('/api/clear-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        return await response.json();
    }
    
    /**
     * Show confirmation dialog and clear all data
     */
    async function confirmClearAllData() {
        const confirmed = confirm(
            'Clear All Local Data\n\n' +
            'This will permanently delete:\n' +
            '- All family users and devices\n' +
            '- All categories and settings\n' +
            '- Authentication tokens\n' +
            '- Server selection\n' +
            '- All local database records\n\n' +
            'This action cannot be undone.\n\n' +
            'Are you sure you want to continue?'
        );
        
        if (!confirmed) {
            return;
        }
        
        // Show loading state
        showAlert('Clearing all local data...', 'warning');
        
        try {
            const result = await clearAllData();
            
            if (result.status === 'ok') {
                showAlert('All local data cleared successfully. You will be redirected to the login page.', 'success');
                // Reload page to clear session and show login options
                setTimeout(() => {
                    location.reload();
                }, 2000);
            } else {
                showAlert('Failed to clear data: ' + (result.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            console.error('Failed to clear all data:', error);
            showAlert('Failed to clear all data: ' + error.message, 'error');
        }
    }
    
    // ============================================================================
    // Users & Devices Dashboard Functions
    // ============================================================================
    
    /**
     * Escape HTML to prevent XSS
     * @param {string} str - String to escape
     * @returns {string} Escaped string
     */
    function escapeHtml(str) {
        if (!str) return 'N/A';
        return String(str)
            .replace(/&/g, '&')
            .replace(/</g, '<')
            .replace(/>/g, '>')
            .replace(/"/g, '"')
            .replace(/'/g, '&#039;');
    }
    
    /**
     * Map protection level integer to user-friendly label
     * Based on official Android app's ProtectionLevel enum
     * @param {number} level - Protection level integer (0-3)
     * @returns {string} User-friendly protection level label
     */
    function getProtectionLevelLabel(level) {
        const protectionLevels = {
            0: 'None',
            1: 'Simple Device Admin',
            2: 'Password Device Admin',
            3: 'Device Owner'
        };
        return protectionLevels[level] || 'Unknown';
    }
    
    /**
     * Load users from the API
     */
    async function loadUsers() {
        const container = document.getElementById('unified-view-container');
        if (!container) {
            return;
        }
        
        // Check authentication first
        if (!isAuthenticated) {
            container.innerHTML = '<div style="text-align: center; padding: 40px; color: #ccc;">Please log in to view users</div>';
            return;
        }
        
        try {
            const response = await fetch('/api/dashboard/unified-view');
            const data = await response.json();
            
            if (data.status === 'ok') {
                renderUnifiedView(data.users);
            } else if (data.error) {
                container.innerHTML = '<div style="text-align: center; padding: 40px; color: #f44336;">' + escapeHtml(data.error) + '</div>';
            } else {
                container.innerHTML = '<div style="text-align: center; padding: 40px; color: #f44336;">Failed to load users - API endpoint not available</div>';
            }
        } catch (error) {
            console.error('Failed to load users:', error);
            container.innerHTML = '<div style="text-align: center; padding: 40px; color: #f44336;">Error loading users: ' + escapeHtml(error.message) + '</div>';
        }
    }
    
    /**
     * Toggle collapsible section expand/collapse
     * @param {string} sectionId - The ID of the collapsible section to toggle
     */
    function toggleCollapsible(sectionId) {
        const header = document.getElementById(sectionId + '-header');
        const content = document.getElementById(sectionId + '-content');
        const toggle = document.getElementById(sectionId + '-toggle');
        
        if (!content) return;
        
        const isExpanded = !content.classList.contains('hidden');
        
        if (isExpanded) {
            content.classList.add('hidden');
            if (toggle) toggle.classList.remove('active');
        } else {
            content.classList.remove('hidden');
            if (toggle) toggle.classList.add('active');
        }
    }
    
    /**
     * Render unified view with user cards
     * @param {Array} users - Array of user objects with associated rules and devices
     */
    function renderUnifiedView(users) {
        const container = document.getElementById('unified-view-container');
        if (!container) return;
        
        if (!users || users.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 40px; color: #ccc;">No users found</div>';
            return;
        }
        
        container.innerHTML = users.map(user => {
            const typeLabel = user.type === 'parent' ? 'Parent' : 'Child';
            const typeBadgeClass = user.type === 'parent' ? 'parent' : 'child';
            const limitsDisabled = user.disable_limits_until && user.disable_limits_until > 0;
            
            // Get associated rules for this user
            const userRules = user.rules || [];
            const userDevices = user.devices || [];
            
            // Check if current device is assigned to this user
            const currentDeviceId = user.current_device_id;
            const hasCurrentDevice = currentDeviceId && userDevices.some(d => d.id === currentDeviceId);
            
            return `
                <div class="user-card" id="user-card-${user.id}">
                    <div class="user-card-header">
                        <h3>
                            ${escapeHtml(user.name)}
                            <span class="user-type-badge ${typeBadgeClass}">${typeLabel}</span>
                            ${hasCurrentDevice ? '<span class="current-device-badge"><span class="check-icon">✓</span> Current Device</span>' : ''}
                        </h3>
                        <button class="collapsible-toggle" id="section-${user.id}-toggle" onclick="window.dashboardV2.toggleCollapsible('section-${user.id}')" aria-label="Toggle section">
                            <span>▶</span>
                        </button>
                    </div>
                    <div class="user-card-body">
                        <div class="user-info">
                            <div class="user-name">${escapeHtml(user.name)}</div>
                            <div class="user-email">${escapeHtml(user.mail)}</div>
                            <div class="user-status">
                                <span>🕒 Time Zone: ${escapeHtml(user.time_zone || 'N/A')}</span>
                                ${limitsDisabled ? '<span style="color: #ffc107; font-weight: 500;">Limits Disabled</span>' : ''}
                            </div>
                        </div>
                        
                        <div class="collapsible-section">
                            <div class="collapsible-header" id="section-${user.id}-header" onclick="window.dashboardV2.toggleCollapsible('section-${user.id}')">
                                <h4 style="margin: 0; font-size: 14px; color: var(--color-text-primary);">
                                    📋 Rules (${userRules.length})
                                </h4>
                                <span class="collapsible-toggle" id="section-${user.id}-toggle"></span>
                            </div>
                            <div class="collapsible-content hidden" id="section-${user.id}-content">
                                ${userRules.length > 0 ? userRules.map(rule => `
                                    <div class="rule-item">
                                        <div class="rule-item-header">
                                            <span class="rule-category">${escapeHtml(rule.category_name || 'Unknown')}</span>
                                            <span class="rule-duration">${rule.limit_minutes} min</span>
                                        </div>
                                        <div class="rule-time-range">
                                            ${rule.days_of_week ? rule.days_of_week.join(', ') : 'All days'}
                                        </div>
                                        <div class="rule-days">
                                            ${rule.days_of_week ? rule.days_of_week.map(day => `<span class="rule-day">${day.substring(0, 3)}</span>`).join('') : ''}
                                        </div>
                                        <div class="rule-actions">
                                            <button class="rule-edit-btn" onclick="window.dashboardV2.editUserRule('${user.id}', '${rule.id}')">✏️</button>
                                            <button class="rule-delete-btn" onclick="window.dashboardV2.deleteUserRule('${user.id}', '${rule.id}')">🗑️</button>
                                        </div>
                                    </div>
                                `).join('') : '<div style="text-align: center; color: #6c757d; padding: 10px;">No rules assigned</div>'}
                            </div>
                        </div>
                        
                        <div class="collapsible-section">
                            <div class="collapsible-header" id="section-${user.id + '-devices'}-header" onclick="window.dashboardV2.toggleCollapsible('section-${user.id + '-devices'}')">
                                <h4 style="margin: 0; font-size: 14px; color: var(--color-text-primary);">
                                    📱 Devices (${userDevices.length})
                                </h4>
                                <span class="collapsible-toggle" id="section-${user.id + '-devices'}-toggle"></span>
                            </div>
                            <div class="collapsible-content hidden" id="section-${user.id + '-devices'}-content">
                                ${userDevices.length > 0 ? userDevices.map(device => `
                                    <div class="device-item">
                                        <div class="device-info">
                                            <div class="device-name">${escapeHtml(device.name)}</div>
                                            <div class="device-model">${escapeHtml(device.model || 'Unknown')}</div>
                                        </div>
                                        <div class="device-actions">
                                            ${device.id === currentDeviceId ? '<span style="color: #28a745; font-weight: 500;">(Current)</span>' : ''}
                                        </div>
                                    </div>
                                `).join('') : '<div style="text-align: center; color: #6c757d; padding: 10px;">No devices assigned</div>'}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    /**
     * Refresh unified view data
     */
    async function refreshUnifiedView() {
        const btn = document.getElementById('refresh-users-btn');
        if (btn) {
            btn.classList.add('loading');
        }
        
        try {
            await loadUsers();
        } finally {
            if (btn) {
                btn.classList.remove('loading');
            }
        }
    }
    
    /**
     * Refresh users data (alias for refreshUnifiedView)
     * This function exists for backward compatibility and API consistency
     */
    async function refreshUsers() {
        await refreshUnifiedView();
    }
    
    /**
     * Load devices from the API
     */
    async function loadDevices() {
        const tbody = document.getElementById('devices-body');
        if (!tbody) return;
        
        // Check authentication first
        if (!isAuthenticated) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #ccc;">Please log in to view devices</td></tr>';
            return;
        }
        
        try {
            const response = await fetch('/api/dashboard/devices');
            const data = await response.json();
            
            if (data.status === 'ok') {
                renderDevicesTable(data.devices, data.own_device_id, data.has_parent_password_second_hash);
            } else if (data.error) {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #f44336;">' + escapeHtml(data.error) + '</td></tr>';
            } else {
                tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #f44336;">Failed to load devices - API endpoint not available</td></tr>';
            }
        } catch (error) {
            console.error('Failed to load devices:', error);
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #f44336;">Error loading devices: ' + escapeHtml(error.message) + '</td></tr>';
        }
    }
    
    /**
     * Render devices table
     * @param {Array} devices - Array of device objects
     * @param {string} ownDeviceId - The ID of the current device (for highlighting)
     * @param {boolean} hasParentPasswordHash - Whether parent password hash is set (for device removal)
     */
    function renderDevicesTable(devices, ownDeviceId, hasParentPasswordHashParam) {
        const tbody = document.getElementById('devices-body');
        if (!tbody) return;
        
        if (!devices || devices.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #ccc;">No devices found</td></tr>';
            return;
        }
        
        // Update global flag from API response (ensures confirmRemoveDevice works correctly)
        hasParentPasswordHash = hasParentPasswordHashParam || false;
        
        tbody.innerHTML = devices.map(device => {
            const addedAt = device.created_at ? new Date(device.created_at).toLocaleString() : 'N/A';
            const platform = device.platform_type || 'Unknown';
            const platformLevel = device.platform_level || 'N/A';
            const protectionLevel = device.current_protection_level !== undefined ? device.current_protection_level : 0;
            const protectionLevelLabel = getProtectionLevelLabel(protectionLevel);
            
            // Format signing key (public_key) - show first 16 chars with ellipsis if longer
            const publicKey = device.public_key || '';
            const signingKeyDisplay = publicKey
                ? (publicKey.length > 16 ? publicKey.substring(0, 16) + '...' : publicKey)
                : 'N/A';
            
            // Check if this is the current device
            const isCurrentDevice = device.id === ownDeviceId;
            const currentDeviceBadge = isCurrentDevice ? ' <span style="color: #4caf50; font-weight: bold; margin-left: 8px;">(Current)</span>' : '';
            
            // Add highlight class for current device
            const rowClass = isCurrentDevice ? 'device-current' : '';
            
            // Can't delete current device or if parent password hash is not set
            const canDelete = !isCurrentDevice && hasParentPasswordHash;
            
            // Show tooltip or disabled state if parent password hash is not set
            let deleteButton;
            if (!hasParentPasswordHash) {
                deleteButton = '<span style="color: #ccc; cursor: not-allowed;" title="Set parent password hash first to enable device removal">🗑️</span>';
            } else if (canDelete) {
                deleteButton = `<button class="delete-btn" onclick="confirmRemoveDevice('${device.id}', '${escapeHtml(device.name)}')">🗑️</button>`;
            } else {
                deleteButton = '<span style="color: #ccc;">-</span>';
            }
            
            return `
                <tr class="${rowClass}">
                    <td>${escapeHtml(device.name)}${currentDeviceBadge}</td>
                    <td>${escapeHtml(device.model)}</td>
                    <td>${escapeHtml(device.current_user_name)}</td>
                    <td>${protectionLevelLabel}</td>
                    <td>${device.current_app_version || 'N/A'}</td>
                    <td>${platform} (v${platformLevel})</td>
                    <td class="time-cell" style="font-family: monospace; font-size: 12px; color: #888;">${escapeHtml(signingKeyDisplay)}</td>
                    <td class="time-cell">${addedAt}</td>
                    <td>
                        ${deleteButton}
                    </td>
                </tr>
            `;
        }).join('');
    }
    
    /**
     * Refresh devices data
     */
    async function refreshDevices() {
        const btn = document.getElementById('refresh-devices-btn');
        if (btn) {
            btn.classList.add('loading');
        }
        
        try {
            await loadDevices();
        } finally {
            if (btn) {
                btn.classList.remove('loading');
            }
        }
    }
    
    /**
     * Load connected devices from the API
     */
    async function loadConnectedDevices() {
        const tbody = document.getElementById('connected-devices-body');
        if (!tbody) return;
        
        // Check authentication first
        if (!isAuthenticated) {
            tbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: #ccc;">Please log in to view connected devices</td></tr>';
            return;
        }
        
        try {
            const response = await fetch('/api/dashboard/connected-devices');
            const data = await response.json();
            
            if (data.status === 'ok') {
                renderConnectedDevicesTable(data.devices);
            } else if (data.error) {
                tbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: #f44336;">' + escapeHtml(data.error) + '</td></tr>';
            } else {
                tbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: #f44336;">Failed to load connected devices - API endpoint not available</td></tr>';
            }
        } catch (error) {
            console.error('Failed to load connected devices:', error);
            tbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: #f44336;">Error loading connected devices: ' + escapeHtml(error.message) + '</td></tr>';
        }
    }
    
    /**
     * Render connected devices table
     * @param {Array} devices - Array of device objects with device_id, name, and last_seen
     */
    function renderConnectedDevicesTable(devices) {
        const tbody = document.getElementById('connected-devices-body');
        if (!tbody) return;
        
        if (!devices || devices.length === 0) {
            tbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: #ccc;">No connected devices</td></tr>';
            return;
        }
        
        tbody.innerHTML = devices.map(device => {
            const lastSeen = device.last_seen ? new Date(device.last_seen).toLocaleString() : 'N/A';
            // Show device ID as fallback when name is not available
            const deviceName = device.name ? escapeHtml(device.name) : (device.device_id ? escapeHtml(device.device_id) : 'N/A');
            return `
                <tr>
                    <td>${deviceName}</td>
                    <td class="time-cell">${lastSeen}</td>
                </tr>
            `;
        }).join('');
    }
    
    /**
     * Refresh connected devices data
     */
    async function refreshConnectedDevices() {
        const btn = document.getElementById('refresh-connected-btn');
        if (btn) {
            btn.classList.add('loading');
        }
        
        try {
            await loadConnectedDevices();
        } finally {
            if (btn) {
                btn.classList.remove('loading');
            }
        }
    }
    
    /**
     * Trigger manual sync
     */
    async function triggerSync() {
        // Check authentication first
        if (!isAuthenticated) {
            showAlert('Cannot sync: You are not authenticated. Please log in first.', 'error');
            return;
        }
        
        try {
            const response = await fetch('/api/sync/pull', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            if (data.status === 'ok') {
                showAlert('Sync completed successfully', 'success');
                // Reload all data after sync
                await Promise.all([
                    loadUsers(),
                    loadDevices(),
                    loadConnectedDevices()
                ]);
            } else {
                showAlert('Sync failed: ' + (data.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            showAlert('Failed to trigger sync: ' + error.message, 'error');
        }
    }
    
    /**
     * Connect to SSE endpoint for real-time updates
     */
    function connectSSE() {
        // Only connect SSE if authenticated
        if (!isAuthenticated) {
            return;
        }
        
        const eventSource = new EventSource('/api/dashboard/stream');
        
        eventSource.addEventListener('sync_complete', function(event) {
            // Reload data after sync
            loadUsers();
            loadDevices();
            loadConnectedDevices();
        });
        
        eventSource.addEventListener('error', function(event) {
            // Try to reconnect after a delay
            setTimeout(() => {
                connectSSE();
            }, 5000);
        });
    }
    
    /**
     * Refresh all dashboard data
     */
    async function refreshAll() {
        await Promise.all([
            loadUsers(),
            loadDevices(),
            loadConnectedDevices()
        ]);
    }
    
    /**
     * Remove device from server
     * @param {string} deviceId - Device ID to remove
     * @returns {Promise<Object>} Response data
     */
    async function removeDevice(deviceId) {
        const response = await fetch('/api/dashboard/devices/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                deviceId: deviceId
            })
        });
        return await response.json();
    }
    
    /**
     * Hide the add user modal
     */
    function hideAddUserModal() {
        const modal = document.getElementById('add-user-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
    
    /**
     * Show the add user modal
     */
    function showAddUserModal() {
        const modal = document.getElementById('add-user-modal');
        if (modal) {
            modal.style.display = 'block';
            modal.style.opacity = '1';
        }
    }
    
    /**
     * Submit the add user form
     */
    async function submitAddUserForm() {
        const form = document.getElementById('add-user-form');
        const nameInput = document.getElementById('add-user-name');
        const deviceNameInput = document.getElementById('add-user-device-name');
        const deviceModelInput = document.getElementById('add-user-device-model');
        const errorDiv = document.getElementById('add-user-name-error');
        
        // Validate user name
        const userName = nameInput.value.trim();
        if (!userName) {
            if (errorDiv) {
                errorDiv.textContent = 'User name is required';
                errorDiv.style.display = 'block';
            }
            return;
        }
        
        if (errorDiv) {
            errorDiv.style.display = 'none';
        }
        
        // Show loading state
        const submitBtn = document.getElementById('add-user-submit-btn');
        if (submitBtn) {
            submitBtn.classList.add('loading');
        }
        
        try {
            const response = await fetch('/api/dashboard/users/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: userName,
                    device_name: deviceNameInput.value.trim() || null,
                    device_model: deviceModelInput.value.trim() || null
                })
            });
            const data = await response.json();
            
            if (data.status === 'ok') {
                showAlert('User added successfully', 'success');
                hideAddUserModal();
                // Refresh the unified view
                await refreshUnifiedView();
            } else {
                showAlert('Failed to add user: ' + (data.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            showAlert('Failed to add user: ' + error.message, 'error');
        } finally {
            if (submitBtn) {
                submitBtn.classList.remove('loading');
            }
        }
    }
    
    /**
     * Hide the rule form modal
     */
    function hideRuleForm() {
        const modal = document.getElementById('rule-form-modal');
        if (modal) {
            modal.style.display = 'none';
            modal.style.opacity = '0';
        }
    }
    
    /**
     * Show the rule form modal
     * @param {string} userId - User ID to create rule for (optional)
     */
    function showRuleForm(userId = null) {
        const modal = document.getElementById('rule-form-modal');
        const title = document.getElementById('rule-form-title');
        
        if (modal) {
            modal.style.display = 'flex';
            modal.style.opacity = '1';
        }
        
        if (title) {
            title.textContent = userId ? 'Edit Time Limit Rule' : 'Add Time Limit Rule';
        }
        
        // Populate user select if userId is provided
        if (userId) {
            const userSelect = document.getElementById('rule-user-select');
            if (userSelect) {
                // Find and select the user
                const option = userSelect.querySelector(`option[value="${userId}"]`);
                if (option) {
                    option.selected = true;
                }
            }
        }
    }
    
    /**
     * Submit the rule form
     */
    async function submitRuleForm() {
        const form = document.getElementById('rule-form');
        const userSelect = document.getElementById('rule-user-select');
        const categorySelect = document.getElementById('rule-category-select');
        const limitMinutesInput = document.getElementById('rule-limit-minutes');
        const startTimeInput = document.getElementById('rule-start-time');
        const endTimeInput = document.getElementById('rule-end-time');
        
        // Get selected days
        const daysOfWeek = [];
        const dayNames = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
        dayNames.forEach((day, index) => {
            const checkbox = document.getElementById(`rule-day-${day}`);
            if (checkbox && checkbox.checked) {
                daysOfWeek.push(day.charAt(0).toUpperCase() + day.slice(1));
            }
        });
        
        // Validate form
        if (!userSelect.value || !categorySelect.value) {
            showAlert('Please select both user and category', 'error');
            return;
        }
        
        // Show loading state
        const saveBtn = document.getElementById('save-rule-btn');
        if (saveBtn) {
            saveBtn.classList.add('loading');
        }
        
        try {
            const response = await fetch('/api/dashboard/time-limit-rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userSelect.value,
                    category_id: categorySelect.value,
                    limit_minutes: parseInt(limitMinutesInput.value),
                    days_of_week: daysOfWeek,
                    start_time: startTimeInput.value,
                    end_time: endTimeInput.value
                })
            });
            const data = await response.json();
            
            if (data.status === 'ok') {
                showAlert('Rule saved successfully', 'success');
                hideRuleForm();
                // Refresh the unified view
                await refreshUnifiedView();
            } else {
                showAlert('Failed to save rule: ' + (data.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            showAlert('Failed to save rule: ' + error.message, 'error');
        } finally {
            if (saveBtn) {
                saveBtn.classList.remove('loading');
            }
        }
    }
    
    /**
     * Edit a user rule
     * @param {string} userId - User ID
     * @param {string} ruleId - Rule ID to edit
     */
    async function editUserRule(userId, ruleId) {
        // Show the rule form with the user pre-selected
        showRuleForm(userId);
        // Note: For editing, we would need to fetch the existing rule data
        // and populate the form. This is a simplified implementation.
    }
    
    /**
     * Delete a user rule
     * @param {string} userId - User ID
     * @param {string} ruleId - Rule ID to delete
     */
    async function deleteUserRule(userId, ruleId) {
        if (!confirm('Are you sure you want to delete this rule?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/dashboard/time-limit-rules/${ruleId}`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            if (data.status === 'ok') {
                showAlert('Rule deleted successfully', 'success');
                // Refresh the unified view
                await refreshUnifiedView();
            } else {
                showAlert('Failed to delete rule: ' + (data.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            showAlert('Failed to delete rule: ' + error.message, 'error');
        }
    }
    
    /**
     * Create a backup of auth tokens
     * @returns {Promise<Object>} Response data
     */
    async function createBackup() {
        const btn = document.getElementById('backup-btn');
        const statusEl = document.getElementById('backup-status');
        
        if (btn) {
            btn.classList.add('loading');
        }
        if (statusEl) {
            statusEl.textContent = 'Creating backup...';
            statusEl.style.color = '#ff9800';
        }
        
        try {
            const response = await fetch('/api/auth/backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            if (data.status === 'ok' && data.backup_successful) {
                if (statusEl) {
                    statusEl.textContent = 'Backup created successfully. Device token: ' +
                        (data.has_device_auth_token ? 'Yes' : 'No') +
                        ', Own device ID: ' + (data.has_own_device_id ? 'Yes' : 'No');
                    statusEl.style.color = '#4caf50';
                }
                showAlert('Auth token backup created successfully', 'success');
            } else {
                if (statusEl) {
                    statusEl.textContent = 'Backup failed: ' + (data.error || 'Unknown error');
                    statusEl.style.color = '#f44336';
                }
                showAlert('Failed to create backup: ' + (data.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            if (statusEl) {
                statusEl.textContent = 'Error: ' + error.message;
                statusEl.style.color = '#f44336';
            }
            showAlert('Failed to create backup: ' + error.message, 'error');
        } finally {
            if (btn) {
                btn.classList.remove('loading');
            }
        }
    }
    
    /**
     * Restore auth tokens from backup
     * @returns {Promise<Object>} Response data
     */
    async function restoreBackup() {
        const btn = document.getElementById('restore-btn');
        const statusEl = document.getElementById('backup-status');
        
        if (btn) {
            btn.classList.add('loading');
        }
        if (statusEl) {
            statusEl.textContent = 'Restoring backup...';
            statusEl.style.color = '#ff9800';
        }
        
        try {
            const response = await fetch('/api/auth/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            if (data.status === 'ok' && data.restore_successful) {
                if (statusEl) {
                    statusEl.textContent = 'Restore completed successfully. Device token: ' +
                        (data.has_device_auth_token ? 'Yes' : 'No') +
                        ', Own device ID: ' + (data.has_own_device_id ? 'Yes' : 'No');
                    statusEl.style.color = '#4caf50';
                }
                showAlert('Auth tokens restored successfully. You may need to refresh the page.', 'success');
                // Reload page to apply restored tokens
                setTimeout(() => {
                    location.reload();
                }, 1500);
            } else {
                if (statusEl) {
                    statusEl.textContent = 'Restore failed: ' + (data.error || 'Unknown error');
                    statusEl.style.color = '#f44336';
                }
                showAlert('Failed to restore backup: ' + (data.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            if (statusEl) {
                statusEl.textContent = 'Error: ' + error.message;
                statusEl.style.color = '#f44336';
            }
            showAlert('Failed to restore backup: ' + error.message, 'error');
        } finally {
            if (btn) {
                btn.classList.remove('loading');
            }
        }
    }
    
    /**
     * Clear the auth token backup file
     * @returns {Promise<Object>} Response data
     */
    async function clearBackup() {
        const btn = document.getElementById('clear-backup-btn');
        const statusEl = document.getElementById('backup-status');
        
        if (btn) {
            btn.classList.add('loading');
        }
        if (statusEl) {
            statusEl.textContent = 'Clearing backup...';
            statusEl.style.color = '#ff9800';
        }
        
        try {
            const response = await fetch('/api/auth/clear-backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            
            if (data.status === 'ok' && data.cleared) {
                if (statusEl) {
                    statusEl.textContent = 'Backup cleared successfully';
                    statusEl.style.color = '#4caf50';
                }
                showAlert('Auth token backup cleared successfully', 'success');
            } else {
                if (statusEl) {
                    statusEl.textContent = 'Failed to clear backup';
                    statusEl.style.color = '#f44336';
                }
                showAlert('Failed to clear backup', 'error');
            }
        } catch (error) {
            if (statusEl) {
                statusEl.textContent = 'Error: ' + error.message;
                statusEl.style.color = '#f44336';
            }
            showAlert('Failed to clear backup: ' + error.message, 'error');
        } finally {
            if (btn) {
                btn.classList.remove('loading');
            }
        }
    }
    
    /**
     * Toggle hamburger menu sidebar
     */
    function toggleMenu() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        const menuToggle = document.getElementById('menu-toggle');
        
        if (!sidebar || !overlay || !menuToggle) {
            return;
        }
        
        const isOpen = sidebar.classList.contains('active');
        
        if (isOpen) {
            closeMenu();
        } else {
            sidebar.classList.add('active');
            sidebar.setAttribute('aria-hidden', 'false');
            overlay.classList.add('active');
            overlay.removeAttribute('aria-hidden');
            menuToggle.setAttribute('aria-expanded', 'true');
            
            // Focus first menu item
            const firstMenuItem = sidebar.querySelector('[role="menuitem"]');
            if (firstMenuItem) {
                firstMenuItem.focus();
            }
        }
    }
    
    /**
     * Close hamburger menu sidebar
     */
    function closeMenu() {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        const menuToggle = document.getElementById('menu-toggle');
        
        if (!sidebar || !overlay || !menuToggle) return;
        
        sidebar.classList.remove('active');
        sidebar.setAttribute('aria-hidden', 'true');
        overlay.classList.remove('active');
        overlay.setAttribute('aria-hidden', 'true');
        menuToggle.setAttribute('aria-expanded', 'false');
        
        // Refocus the menu toggle button
        menuToggle.focus();
    }
    
    /**
     * Check if user has admin privileges (has parent password hash)
     * @returns {Promise<boolean>} True if user is admin
     */
    async function checkAdminVisibility() {
        try {
            const response = await fetch('/api/session/status');
            const data = await response.json();
            
            // User is admin if they have parent password hash set
            const isAdmin = data.has_parent_password_second_hash === true;
            
            // Update admin section visibility
            updateAdminSectionVisibility(isAdmin);
            
            // Update admin-only elements visibility
            updateAdminOnlyElements(isAdmin);
            
            return isAdmin;
        } catch (error) {
            console.error('Failed to check admin visibility:', error);
            // On error, hide admin section for security
            updateAdminSectionVisibility(false);
            updateAdminOnlyElements(false);
            return false;
        }
    }
    
    /**
     * Update admin section visibility based on admin status
     * @param {boolean} isAdmin - Whether user has admin privileges
     */
    function updateAdminSectionVisibility(isAdmin) {
        const adminSection = document.getElementById('admin-section');
        if (!adminSection) return;
        
        if (isAdmin) {
            adminSection.classList.add('visible');
        } else {
            adminSection.classList.remove('visible');
        }
    }
    
    /**
     * Update visibility of admin-only elements throughout the dashboard
     * @param {boolean} isAdmin - Whether user has admin privileges
     */
    function updateAdminOnlyElements(isAdmin) {
        // Select all elements with admin-only class
        const adminOnlyElements = document.querySelectorAll('.admin-only');
        
        adminOnlyElements.forEach(function(element) {
            if (isAdmin) {
                element.classList.remove('hidden');
            } else {
                element.classList.add('hidden');
            }
        });
    }
    
    /**
         * Load family overview data from API
         */
        async function loadFamilyOverview() {
            try {
                const response = await fetch('/api/dashboard/family-overview');
                const data = await response.json();
                
                if (data.status === 'ok') {
                    renderFamilyOverview(data);
                } else {
                    console.error('Failed to load family overview:', data.error);
                }
            } catch (error) {
                console.error('Error loading family overview:', error);
            }
        }
    
        /**
         * Render the Family Overview card
         * @param {Object} data - Family overview data
         * @param {string} data.family_email - Family email address
         * @param {number} data.devices_count - Number of devices in the family
         * @param {number} data.users_count - Number of users in the family
         * @param {string} data.last_sync - Last sync timestamp (ISO string)
         */
        function renderFamilyOverview(data) {
            if (!data) {
                console.error('renderFamilyOverview: No data provided');
                return;
            }
    
            // Update family email display with truncation
            const emailDisplay = document.getElementById('family-email-display');
            if (emailDisplay) {
                const email = data.family_email || 'No family email';
                const truncatedEmail = email.length > 40 ? email.substring(0, 37) + '...' : email;
                emailDisplay.innerHTML = '<span class="email-text ellipsis" title="' + escapeHtml(email) + '">' + escapeHtml(truncatedEmail) + '</span>';
            }
    
            // Update devices count
            const devicesCount = document.getElementById('devices-count');
            if (devicesCount) {
                devicesCount.textContent = data.devices_count !== undefined ? data.devices_count : 0;
            }
    
            // Update users count
            const usersCount = document.getElementById('users-count');
            if (usersCount) {
                usersCount.textContent = data.users_count !== undefined ? data.users_count : 0;
            }
    
            // Update last sync timestamp
            const lastSync = document.getElementById('last-sync-timestamp');
            if (lastSync && data.last_sync) {
                const syncDate = new Date(data.last_sync);
                const syncTime = syncDate.toLocaleString();
                lastSync.textContent = 'Last sync: ' + syncTime;
            }
        }
    
    /**
     * Show device removal confirmation dialog
     * @param {string} deviceId - Device ID to remove
     * @param {string} deviceName - Device name for display
     */
     async function confirmRemoveDevice(deviceId, deviceName) {
        // Check if parent password hash is set before allowing removal
        if (!hasParentPasswordHash) {
            showAlert('Parent password hash is required. Please set it in the session settings first.', 'warning');
            return;
        }
        
        // Show confirmation modal
        const confirmed = confirm(
            'Remove device "' + escapeHtml(deviceName) + '" from your family?\n\n' +
            'This will:\n' +
            '- Remove the device from the server\n' +
            '- The device will no longer appear in the dashboard\n' +
            '- The device will need to be re-added if it joins again\n\n' +
            'Are you sure you want to continue?'
        );
        
        if (!confirmed) {
            return;
        }
        
        // Show loading state
        showAlert('Removing device...', 'warning');
        
        try {
            const result = await removeDevice(deviceId);
            
            if (result.status === 'ok') {
                showAlert('Device removed successfully', 'success');
                // Refresh devices list
                await loadDevices();
            } else if (result.error === 'Parent password hash not set. Please enter it in the session settings.') {
                showAlert('Parent password hash is required. Please enter it in the session settings first.', 'warning');
            } else {
                showAlert('Failed to remove device: ' + (result.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            console.error('Failed to remove device:', error);
            showAlert('Failed to remove device: ' + error.message, 'error');
        }
    }
    
    // Expose functions globally for HTML onclick handlers
    window.refreshUsers = refreshUsers;
    window.refreshDevices = refreshDevices;
    window.refreshConnectedDevices = refreshConnectedDevices;
    window.loadUsers = loadUsers;
    window.loadDevices = loadDevices;
    window.loadConnectedDevices = loadConnectedDevices;
    window.triggerSync = triggerSync;
    window.connectSSE = connectSSE;
    window.checkAuthentication = checkAuthentication;
    window.selectServer = selectServer;
    window.refreshData = refreshData;
    window.clearSession = clearSession;
    window.clearAllData = clearAllData;
    window.confirmClearAllData = confirmClearAllData;
    window.apiRequest = apiRequest;
    window.refreshAll = refreshAll;
    window.updateSessionOverview = updateSessionOverview;
    window.updateLoginStatusBanner = updateLoginStatusBanner;
    window.showAlert = showAlert;
    window.getProtectionLevelLabel = getProtectionLevelLabel;
    window.removeDevice = removeDevice;
    window.confirmRemoveDevice = confirmRemoveDevice;
    window.createBackup = createBackup;
    window.restoreBackup = restoreBackup;
    window.clearBackup = clearBackup;
    window.toggleMenu = toggleMenu;
    window.closeMenu = closeMenu;
    window.checkAdminVisibility = checkAdminVisibility;
    window.updateAdminOnlyElements = updateAdminOnlyElements;
    window.updateAdminSectionVisibility = updateAdminSectionVisibility;
    window.renderFamilyOverview = renderFamilyOverview;
    window.loadFamilyOverview = loadFamilyOverview;
    window.toggleCollapsible = toggleCollapsible;
    window.renderUnifiedView = renderUnifiedView;
    window.refreshUnifiedView = refreshUnifiedView;
    window.showAddUserModal = showAddUserModal;
    window.submitAddUserForm = submitAddUserForm;
    window.hideAddUserModal = hideAddUserModal;
    window.showRuleForm = showRuleForm;
    window.submitRuleForm = submitRuleForm;
    window.hideRuleForm = hideRuleForm;
    window.editUserRule = editUserRule;
    window.deleteUserRule = deleteUserRule;
    
    // Also expose on dashboardV2 object for programmatic access
    window.dashboardV2 = {
        selectServer: selectServer,
        refreshData: refreshData,
        clearSession: clearSession,
        clearAllData: clearAllData,
        confirmClearAllData: confirmClearAllData,
        checkAuthentication: checkAuthentication,
        apiRequest: apiRequest,
        loadUsers: loadUsers,
        loadDevices: loadDevices,
        loadConnectedDevices: loadConnectedDevices,
        loadFamilyOverview: loadFamilyOverview,
        refreshUsers: refreshUsers,
        refreshDevices: refreshDevices,
        refreshConnectedDevices: refreshConnectedDevices,
        refreshAll: refreshAll,
        triggerSync: triggerSync,
        connectSSE: connectSSE,
        updateSessionOverview: updateSessionOverview,
        updateLoginStatusBanner: updateLoginStatusBanner,
        showAlert: showAlert,
        getProtectionLevelLabel: getProtectionLevelLabel,
        removeDevice: removeDevice,
        confirmRemoveDevice: confirmRemoveDevice,
        createBackup: createBackup,
        restoreBackup: restoreBackup,
        clearBackup: clearBackup,
        toggleMenu: toggleMenu,
        closeMenu: closeMenu,
        checkAdminVisibility: checkAdminVisibility,
        updateAdminOnlyElements: updateAdminOnlyElements,
        updateAdminSectionVisibility: updateAdminSectionVisibility,
        renderFamilyOverview: renderFamilyOverview,
        toggleCollapsible: toggleCollapsible,
        renderUnifiedView: renderUnifiedView,
        refreshUnifiedView: refreshUnifiedView,
        showAddUserModal: showAddUserModal,
        submitAddUserForm: submitAddUserForm,
        hideAddUserModal: hideAddUserModal,
        showRuleForm: showRuleForm,
        submitRuleForm: submitRuleForm,
        hideRuleForm: hideRuleForm,
        editUserRule: editUserRule,
        deleteUserRule: deleteUserRule
    };

    // Close modal on Escape key
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            // Close sidebar if open
            const sidebar = document.getElementById('sidebar');
            if (sidebar && sidebar.classList.contains('active')) {
                closeMenu();
                return;
            }
            
            // Close add user modal
            const addUserModal = document.getElementById('add-user-modal');
            if (addUserModal && addUserModal.style.display === 'block') {
                hideAddUserModal();
            }
            
            // Close rule form modal
            const ruleFormModal = document.getElementById('rule-form-modal');
            if (ruleFormModal && ruleFormModal.style.display === 'block') {
                hideRuleForm();
            }
        }
    });

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', async function() {
        // Check if we're on the dashboard page by verifying required elements exist
        // The landing page doesn't have these elements, so we skip dashboard initialization
        const dashboardContainer = document.getElementById('unified-view-container');
        const statusIndicator = document.getElementById('status-indicator');
        
        if (!dashboardContainer && !statusIndicator) {
            return;
        }
        
        // Check authentication status first and get session data
        const sessionData = await checkAuthentication();
        
        // Update login status banner and session overview with session data
        updateLoginStatusBanner(sessionData);
        updateSessionOverview(sessionData);
        
        if (isAuthenticated) {
            // Load family overview data
            loadFamilyOverview();
            
            // Load initial data only if authenticated
            loadUsers();
            loadDevices();
            loadConnectedDevices();
            
            // Connect to SSE for real-time updates
            connectSSE();
        }
    });

})();