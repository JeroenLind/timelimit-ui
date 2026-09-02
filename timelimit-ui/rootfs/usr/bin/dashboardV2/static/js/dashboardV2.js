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
     * @returns {Promise<boolean>} True if authenticated
     */
    async function checkAuthentication() {
        try {
            const response = await fetch('/api/session/status');
            const data = await response.json();
            isAuthenticated = data.authenticated || false;
            return isAuthenticated;
        } catch (error) {
            console.error('Failed to check authentication status:', error);
            isAuthenticated = false;
            return false;
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
        
        if (!banner || !indicator || !message) return;
        
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
        const signoutLink = document.getElementById('signout-link');
        if (createFamilyLink && loginExistingFamilyLink) {
            if (data.authenticated) {
                createFamilyLink.style.display = 'none';
                loginExistingFamilyLink.style.display = 'none';
                if (signoutLink) {
                    signoutLink.style.display = 'block';
                }
            } else {
                createFamilyLink.style.display = 'block';
                loginExistingFamilyLink.style.display = 'block';
                if (signoutLink) {
                    signoutLink.style.display = 'none';
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
            // Clear stored password hash
            parentPasswordHash = null;
            location.reload();
        } catch (error) {
            console.error('Failed to clear session:', error);
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
        const tbody = document.getElementById('users-body');
        if (!tbody) return;
        
        // Check authentication first
        if (!isAuthenticated) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #666;">Please log in to view users</td></tr>';
            return;
        }
        
        try {
            const response = await fetch('/api/dashboard/users');
            const data = await response.json();
            
            if (data.status === 'ok') {
                renderUsersTable(data.users);
            } else if (data.error) {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #f44336;">' + escapeHtml(data.error) + '</td></tr>';
            } else {
                tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #f44336;">Failed to load users - API endpoint not available</td></tr>';
            }
        } catch (error) {
            console.error('Failed to load users:', error);
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #f44336;">Error loading users: ' + escapeHtml(error.message) + '</td></tr>';
        }
    }
    
    /**
     * Render users table
     * @param {Array} users - Array of user objects
     */
    function renderUsersTable(users) {
        const tbody = document.getElementById('users-body');
        if (!tbody) return;
        
        if (!users || users.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; color: #666;">No users found</td></tr>';
            return;
        }
        
        tbody.innerHTML = users.map(user => {
            const typeLabel = user.type === 'parent' ? '👤 Parent' : '👶 Child';
            const limitsDisabled = user.disable_limits_until && user.disable_limits_until > 0 ? 'Yes' : 'No';
            
            return `
                <tr>
                    <td>${escapeHtml(user.name)}</td>
                    <td>${typeLabel}</td>
                    <td>${escapeHtml(user.mail)}</td>
                    <td>${escapeHtml(user.current_device)}</td>
                    <td>${escapeHtml(user.time_zone)}</td>
                    <td>${limitsDisabled}</td>
                </tr>
            `;
        }).join('');
    }
    
    /**
     * Refresh users data
     */
    async function refreshUsers() {
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
     * Load devices from the API
     */
    async function loadDevices() {
        const tbody = document.getElementById('devices-body');
        if (!tbody) return;
        
        // Check authentication first
        if (!isAuthenticated) {
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #666;">Please log in to view devices</td></tr>';
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
            tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #666;">No devices found</td></tr>';
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
                deleteButton = '<span style="color: #666; cursor: not-allowed;" title="Set parent password hash first to enable device removal">🗑️</span>';
            } else if (canDelete) {
                deleteButton = `<button class="delete-btn" onclick="confirmRemoveDevice('${device.id}', '${escapeHtml(device.name)}')">🗑️</button>`;
            } else {
                deleteButton = '<span style="color: #666;">-</span>';
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
            tbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: #666;">Please log in to view connected devices</td></tr>';
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
            tbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: #666;">No connected devices</td></tr>';
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
            console.error('Cannot sync: not authenticated');
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
                console.log('Sync completed:', data);
                showAlert('Sync completed successfully', 'success');
                // Reload all data after sync
                await Promise.all([
                    loadUsers(),
                    loadDevices(),
                    loadConnectedDevices()
                ]);
            } else {
                console.error('Sync failed:', data);
                showAlert('Sync failed: ' + (data.error || 'Unknown error'), 'error');
            }
        } catch (error) {
            console.error('Failed to trigger sync:', error);
            showAlert('Failed to trigger sync: ' + error.message, 'error');
        }
    }
    
    /**
     * Connect to SSE endpoint for real-time updates
     */
    function connectSSE() {
        // Only connect SSE if authenticated
        if (!isAuthenticated) {
            console.log('SSE connection skipped: not authenticated');
            return;
        }
        
        const eventSource = new EventSource('/api/dashboard/stream');
        
        eventSource.addEventListener('sync_complete', function(event) {
            console.log('Sync complete event received:', event.data);
            // Reload data after sync
            loadUsers();
            loadDevices();
            loadConnectedDevices();
        });
        
        eventSource.addEventListener('error', function(event) {
            console.error('SSE error:', event);
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
        clearBackup: clearBackup
    };

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', async function() {
        console.log('DashboardV2 initialized');
        
        // Check authentication status first
        await checkAuthentication();
        
        if (isAuthenticated) {
            // Load initial data only if authenticated
            loadUsers();
            loadDevices();
            loadConnectedDevices();
            
            // Connect to SSE for real-time updates
            connectSSE();
        } else {
            console.log('User not authenticated - dashboard data will not be loaded');
        }
    });

})();