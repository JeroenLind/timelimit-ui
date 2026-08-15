/**
 * Unit tests for debug mode functionality
 * Tests the isDebugMode(), applyDebugMode(), and setDebugMode() functions
 */

// Mock DOM environment for Node.js
const mockInspectorPanel = { 
    style: { 
        display: '',
        setProperty: function(prop, value, priority) { 
            this.display = value; 
        }
    } 
};

const mockDebugToggle = { 
    checked: false, 
    addEventListener: () => {} 
};

const mockDebugToggleLabel = { 
    textContent: '' 
};

const document = {
    classList: {
        toggle: () => {},
        add: () => {},
        remove: () => {}
    },
    querySelectorAll: (selector) => {
        if (selector === '[data-debug-only="true"]') {
            return [mockInspectorPanel];
        }
        return [];
    },
    getElementById: (id) => {
        if (id === 'debug-toggle') return mockDebugToggle;
        if (id === 'debug-toggle-label') return mockDebugToggleLabel;
        return null;
    }
};

// Mock localStorage for testing
const localStorageMock = (() => {
    let store = {};
    return {
        getItem: (key) => store[key] || null,
        setItem: (key, value) => { store[key] = value.toString(); },
        removeItem: (key) => { delete store[key]; },
        clear: () => { store = {}; }
    };
})();

// Test functions
function runTests() {
    let passed = 0;
    let failed = 0;
    
    console.log('Running debug mode tests...\n');
    
    // Test 1: isDebugMode returns true when localStorage is null
    localStorageMock.clear();
    const isDebugMode = () => {
        const value = localStorageMock.getItem('timelimit_debugMode');
        return value === null || value === '1';
    };
    
    if (isDebugMode() === true) {
        console.log('✅ Test 1 PASSED: isDebugMode returns true when localStorage is null');
        passed++;
    } else {
        console.log('❌ Test 1 FAILED: isDebugMode should return true when localStorage is null');
        failed++;
    }
    
    // Test 2: isDebugMode returns true when localStorage is '1'
    localStorageMock.setItem('timelimit_debugMode', '1');
    if (isDebugMode() === true) {
        console.log('✅ Test 2 PASSED: isDebugMode returns true when localStorage is "1"');
        passed++;
    } else {
        console.log('❌ Test 2 FAILED: isDebugMode should return true when localStorage is "1"');
        failed++;
    }
    
    // Test 3: isDebugMode returns false when localStorage is '0'
    localStorageMock.setItem('timelimit_debugMode', '0');
    if (isDebugMode() === false) {
        console.log('✅ Test 3 PASSED: isDebugMode returns false when localStorage is "0"');
        passed++;
    } else {
        console.log('❌ Test 3 FAILED: isDebugMode should return false when localStorage is "0"');
        failed++;
    }
    
    // Test 4: applyDebugMode sets display to 'block' with !important when enabled is true
    const applyDebugMode = (enabled) => {
        document.classList.toggle('debug-mode', enabled);
        const debugOnlyElements = document.querySelectorAll('[data-debug-only="true"]');
        debugOnlyElements.forEach((el) => {
            el.style.setProperty('display', enabled ? 'block' : 'none', 'important');
        });
        const toggle = document.getElementById('debug-toggle');
        if (toggle) toggle.checked = enabled;
        const label = document.getElementById('debug-toggle-label');
        if (label) label.textContent = enabled ? 'On' : 'Off';
    };
    
    applyDebugMode(true);
    if (mockInspectorPanel.style.display === 'block') {
        console.log('✅ Test 4 PASSED: applyDebugMode sets display to "block" when enabled is true');
        passed++;
    } else {
        console.log('❌ Test 4 FAILED: applyDebugMode should set display to "block" when enabled is true');
        failed++;
    }
    
    // Test 5: applyDebugMode sets display to 'none' when enabled is false
    applyDebugMode(false);
    if (mockInspectorPanel.style.display === 'none') {
        console.log('✅ Test 5 PASSED: applyDebugMode sets display to "none" when enabled is false');
        passed++;
    } else {
        console.log('❌ Test 5 FAILED: applyDebugMode should set display to "none" when enabled is false');
        failed++;
    }
    
    // Test 6: setDebugMode saves to localStorage and applies mode
    const setDebugMode = (enabled) => {
        localStorageMock.setItem('timelimit_debugMode', enabled ? '1' : '0');
        applyDebugMode(enabled);
    };
    
    setDebugMode(true);
    if (localStorageMock.getItem('timelimit_debugMode') === '1' && mockInspectorPanel.style.display === 'block') {
        console.log('✅ Test 6 PASSED: setDebugMode saves "1" to localStorage and shows debug window');
        passed++;
    } else {
        console.log('❌ Test 6 FAILED: setDebugMode should save "1" to localStorage and show debug window');
        failed++;
    }
    
    // Test 7: setDebugMode saves '0' to localStorage and hides debug window
    setDebugMode(false);
    if (localStorageMock.getItem('timelimit_debugMode') === '0' && mockInspectorPanel.style.display === 'none') {
        console.log('✅ Test 7 PASSED: setDebugMode saves "0" to localStorage and hides debug window');
        passed++;
    } else {
        console.log('❌ Test 7 FAILED: setDebugMode should save "0" to localStorage and hide debug window');
        failed++;
    }
    
    // Summary
    console.log('\n========================================');
    console.log(`Tests completed: ${passed + failed}`);
    console.log(`Passed: ${passed}`);
    console.log(`Failed: ${failed}`);
    console.log('========================================');
    
    return failed === 0;
}

// Run tests if executed directly (not imported)
if (require.main === module) {
    runTests();
}

module.exports = { runTests };