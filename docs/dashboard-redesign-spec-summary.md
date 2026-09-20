# Dashboard Redesign Specification Summary

This document summarizes the key specifications from `plans/dashboard-redesign-mockup.md`.

---

## 1. Color Palette (Section 12 - CSS Custom Properties)

### Light Theme Colors

| Variable | Hex Value | Usage |
|----------|-----------|-------|
| `--color-bg` | `#f5f7fa` | Page background |
| `--color-card` | `#ffffff` | Content cards, modal content |
| `--color-border` | `#e9ecef` | Card borders, dividers |
| `--color-text-primary` | `#212529` | Main body text |
| `--color-text-secondary` | `#6c757d` | Secondary text, labels |
| `--color-text-muted` | `#9aa0a6` | Placeholder, disabled text |
| `--color-primary` | `#667eea` | Primary buttons, links, accents |
| `--color-primary-hover` | `#5a6fd8` | Hover state for primary |
| `--color-success` | `#28a745` | Success badges, indicators |
| `--color-success-light` | `#d4edda` | Success background |
| `--color-warning` | `#ffc107` | Warning badges, indicators |
| `--color-warning-light` | `#fff3cd` | Warning background |
| `--color-error` | `#dc3545` | Error badges, indicators |
| `--color-error-light` | `#f8d7da` | Error background |
| `--color-info` | `#17a2b8` | Info badges, indicators |
| `--color-overlay` | `rgba(0, 0, 0, 0.5)` | Sidebar backdrop |
| `--color-shadow` | `rgba(0, 0, 0, 0.08)` | Card shadows |

### Status Indicator Colors

| Status | Color | Background |
|--------|-------|------------|
| Online / Active | `#28a745` | `#d4edda` |
| Warning | `#ffc107` | `#fff3cd` |
| Error / Offline | `#dc3545` | `#f8d7da` |
| Info | `#17a2b8` | `#d1ecf1` |

### Spacing Variables

| Variable | Value |
|----------|-------|
| `--spacing-xs` | `4px` |
| `--spacing-sm` | `8px` |
| `--spacing-md` | `16px` |
| `--spacing-lg` | `24px` |
| `--spacing-xl` | `32px` |

### Border Radius Variables

| Variable | Value |
|----------|-------|
| `--radius-sm` | `4px` |
| `--radius-md` | `8px` |
| `--radius-lg` | `12px` |
| `--radius-xl` | `16px` |

### Transition Variables

| Variable | Value |
|----------|-------|
| `--transition-fast` | `0.15s ease` |
| `--transition-normal` | `0.2s ease` |
| `--transition-slow` | `0.3s ease` |

---

## 2. Typography Scale (Section 4)

### Font Stack

```
-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif
```

### Typography Scale

| Element | Size | Weight | Line Height | Letter Spacing | Color |
|---------|------|--------|-------------|----------------|-------|
| Page Title (H1) | 24px | 600 | 1.2 | -0.5px | `--color-text-primary` |
| Section Heading (H2) | 18px | 600 | 1.3 | -0.25px | `--color-text-primary` |
| Card Title (H3) | 16px | 600 | 1.3 | 0 | `--color-text-primary` |
| Body Text | 14px | 400 | 1.6 | 0.1px | `--color-text-primary` |
| Secondary Text | 14px | 400 | 1.6 | 0.1px | `--color-text-secondary` |
| Caption / Label | 12px | 500 | 1.4 | 0.3px | `--color-text-secondary` |
| Badge / Tag | 12px | 600 | 1.2 | 0.3px | Varies by type |
| Monospace (tokens, IDs) | 12px | 400 | 1.4 | 0 | `--color-text-muted` |

---

## 3. Component Class Names (Section 10)

### New Components

| Component | Description | CSS Class |
|-----------|-------------|-----------|
| `.menu-toggle` | Hamburger button in header | `.menu-toggle` |
| `.sidebar` | Slide-in menu panel | `.dashboard-sidebar` |
| `.sidebar-overlay` | Backdrop for sidebar | `.sidebar-overlay` |
| `.user-card` | Card displaying user with associated rules and devices | `.user-card` |
| `.family-overview-card` | Summary card with family stats | `.family-overview-card` |
| `.stat-badge` | Small stat display (count + label) | `.stat-badge` |
| `.user-type-badge` | Badge showing parent/child type | `.user-type-badge` |
| `.rule-item` | Individual rule display in user card | `.rule-item` |
| `.device-item` | Individual device display in user card | `.device-item` |
| `.collapsible-section` | Expandable/collapsible section | `.collapsible-section` |
| `.connected-devices-table` | Table for connected devices | `.connected-devices-table` |

### Modified Components

| Component | Changes |
|-----------|---------|
| `.dashboard-header` | Add hamburger button, change to light theme |
| `.dashboard-content` | Change background to white, add shadow, light text colors |
| `.dashboard-table` | Light theme: dark text, light borders, white background |
| `.refresh-btn` | Light theme: adjust colors for light background |
| `.alert` | Light theme: dark text, appropriate background colors |
| `.status-indicator` | Use new status colors (green/orange/red) |

### Removed Components

| Component | Reason |
|-----------|--------|
| Inline session action links | Replaced by hamburger menu navigation |
| `.server-info` in header | Moved to sidebar "Server Status" section |
| Standalone Time Limit Rules table | Rules now displayed within user cards |

---

## 4. Role-Based Visibility Rules (Section 7)

### Role Detection Logic

The `has_parent_password_second_hash` field from the `/api/session/status` endpoint determines user role:

- **True** → Role: Parent/Admin
- **False** → Role: Standard User

### Menu Item Visibility Matrix

| Menu Item | Parent/Admin | Standard User | Unauthenticated |
|-----------|-------------|---------------|-----------------|
| Overview | ✅ | ✅ | ❌ |
| Users & Devices | ✅ | ✅ | ❌ |
| Time Limit Rules | ✅ | ✅ | ❌ |
| Connected Devices | ✅ | ✅ | ❌ |
| Server Status | ✅ | ✅ | ✅ |
| Sync Now | ✅ | ✅ | ❌ |
| Session Details | ✅ | ✅ | ❌ |
| Sign Out | ✅ | ✅ | ❌ |
| **Create New Family** | ✅ | ❌ | ❌ |
| **View Database Content** | ✅ | ❌ | ❌ |
| **Set Parent Password** | ✅ | ❌ | ❌ |
| **Clear All Data** | ✅ | ❌ | ❌ |
| Documentation | ✅ | ✅ | ✅ |
| Keyboard Shortcuts | ✅ | ✅ | ✅ |

### Implementation Notes

- The `has_parent_password_second_hash` field is returned by the `/api/session/status` endpoint
- Frontend JavaScript checks this field and conditionally renders admin menu items
- Server-side routes (`/debug/database`, `/create-family`) check for `device_auth_token` in session
- Additional server-side check: verify `has_parent_password_second_hash` before rendering admin-only pages
- Hamburger menu is visible to all users, but admin items within it are conditionally rendered

---

## 5. Layout Structure (Section 2)

### Overall Page Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HEADER (fixed, full-width)                                            │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  ⏱️ TimeLimit Dashboard                           [☰ Menu]      │  │
│  │  Server: api.timelimit.io  •  v2.0.0                               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│  MAIN CONTENT AREA                                                      │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  FAMILY OVERVIEW CARD                                              │  │
│  │  ┌──────────────┬──────────────┬──────────────┐                   │  │
│  │  │  Family:     │  Devices: 3  │  Users: 4    │                   │  │
│  │  │  parent@…    │              │              │                   │  │
│  │  └──────────────┴──────────────┴──────────────┘                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  USERS & DEVICES (unified view)                                    │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │  USER CARD: "Alice" (👤 Parent)                               │  │  │
│  │  │  Email: alice@example.com  •  Time Zone: Europe/Amsterdam      │  │  │
│  │  │  Current Device: Living Room Tablet                            │  │  │
│  │  │  ┌───────────────────────────────────────────────────────────┐  │  │  │
│  │  │  │  ASSOCIATED RULES                                         │  │  │  │
│  │  │  │  • Games: 2h/day (Mon-Fri, 16:00-21:00)                   │  │  │  │
│  │  │  │  • Social: 1h/day (Every day, 08:00-22:00)                 │  │  │  │
│  │  │  └───────────────────────────────────────────────────────────┘  │  │  │
│  │  │  ┌───────────────────────────────────────────────────────────┐  │  │  │
│  │  │  │  ASSOCIATED DEVICES                                       │  │  │  │
│  │  │  │  • Living Room Tablet (Android v12, Owner)                 │  │  │  │
│  │  │  └───────────────────────────────────────────────────────────┘  │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │  USER CARD: "Bob" (👶 Child)                                  │  │  │
│  │  │  ...                                                           │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  CONNECTED DEVICES                                                  │  │
│  │  ┌───────────────────────────────────────────────────────────────┐  │  │
│  │  │  Device Name         │ Last Seen                             │  │  │
│  │  │  Living Room Tablet  │ 2026-09-14 18:15                      │  │  │
│  │  │  Parent Phone        │ 2026-09-14 18:10                      │  │  │
│  │  └───────────────────────────────────────────────────────────────┘  │  │
│  │  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
│  FOOTER                                                                   │
│  Dashboard v2.0.0 • Last synced: 2 min ago                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### Hamburger Menu Sidebar (slides in from right)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  HEADER                                                                 │
│  ⏱️ TimeLimit Dashboard                           [☰ Menu]              │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  [X] Close                                                        │  │
│  │                                                                   │  │
│  │  DASHBOARD                                                         │  │
│  │  • Overview                                                        │  │
│  │  • Users & Devices                                                 │  │
│  │  • Time Limit Rules                                                │  │
│  │  • Connected Devices                                               │  │
│  │                                                                   │  │
│  │  SERVER                                                            │  │
│  │  • Server Status                                                   │  │
│  │  • Sync Now                                                        │  │
│  │                                                                   │  │
│  │  SESSION                                                           │  │
│  │  • Session Details                                                 │  │
│  │  • Sign Out                                                        │  │
│  │                                                                   │  │
│  │  ─────────────────────────────────────────────────────────────   │  │
│  │  ADMINISTRATION  [visible only to parent/admin role]              │  │
│  │  • Create New Family                                               │  │
│  │  • View Database Content                                           │  │
│  │  • Set Parent Password                                             │  │
│  │  • Clear All Data                                                  │  │
│  │  ─────────────────────────────────────────────────────────────   │  │
│  │                                                                   │  │
│  │  HELP                                                              │  │
│  │  • Documentation                                                   │  │
│  │  • Keyboard Shortcuts                                              │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Accessibility Requirements (Section 8)

### WCAG 2.1 AA Compliance

| Requirement | Implementation |
|-------------|----------------|
| **Color Contrast** | All text/background combinations meet 4.5:1 contrast ratio. Primary text `#212529` on `#ffffff` = 15.9:1. Secondary text `#6c757d` on `#ffffff` = 4.6:1. |
| **Keyboard Navigation** | All interactive elements are focusable via `Tab`. Hamburger menu, menu items, buttons, and table action buttons all support `Enter` and `Space` activation. |
| **ARIA Labels** | Hamburger button: `aria-label="Open menu"`, `aria-expanded`. Menu items have `role="menuitem"`. User type badges have `aria-label="Parent user"` / `aria-label="Child user"`. |
| **Focus Management** | When menu opens, focus moves to first menu item. When menu closes, focus returns to hamburger button. Modal dialogs trap focus. |
| **Screen Reader** | All icons have `aria-hidden="true"` with text alternatives in adjacent spans. Status indicators have `aria-label` with status text. |
| **Skip Links** | "Skip to main content" link at top of page, visible on focus only. |
| **Responsive Text** | Font sizes use `px` with `rem` fallbacks. No text smaller than 12px. |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `☰` button + `Enter`/`Space` | Open/close menu |
| `Escape` | Close menu, close modals |
| `Tab` | Navigate between focusable elements |
| `Ctrl/Cmd + K` | Focus search (future enhancement) |
| `Ctrl/Cmd + R` | Refresh data |

---

## 7. Responsive Breakpoints (Section 9)

### Breakpoints

| Breakpoint | Max Width | Changes |
|------------|-----------|---------|
| **Desktop** | 1200px+ | Full layout, sidebar 280px, 3-column stat cards |
| **Tablet** | 768px - 1199px | Sidebar 90% width, stat cards stack to 2-column, tables scrollable |
| **Mobile** | 480px - 767px | Sidebar full-width, stat cards single column, user cards compact, tables horizontal scroll |
| **Small Mobile** | < 480px | Font sizes reduced, padding reduced, hamburger icon larger |

### Mobile Adaptations

- **Header**: Server info moves below title, hamburger icon larger (28px)
- **Family Overview**: Stat cards stack vertically (1 column)
- **User Cards**: Avatar smaller, rules/devices sections collapsed by default
- **Tables**: Horizontal scroll container with `overflow-x: auto`
- **Menu Sidebar**: Full width (90vw), close button larger

---

## New JavaScript Functions (Section 13)

| Function | Purpose |
|----------|---------|
| `toggleMenu()` | Open/close hamburger menu sidebar |
| `closeMenu()` | Close sidebar (click outside, Escape) |
| `renderFamilyOverview(data)` | Render family overview card |
| `renderUserCards(users, devices, rules, categories)` | Render unified user cards with associated rules and devices |
| `renderConnectedDevicesTable(devices)` | Render connected devices table |
| `toggleCollapsible(sectionId)` | Expand/collapse sections within user cards |
| `checkAdminVisibility()` | Check session status and show/hide admin menu items |

---

## 8. Implementation Status and Deviations

### 8.1 Implementation Status Summary

| Component | Specification Status | Implementation Status | Notes |
|-----------|---------------------|----------------------|-------|
| Light Theme Colors | ✅ Complete | ✅ Implemented | All CSS custom properties match specification |
| Hamburger Menu | ✅ Complete | ✅ Implemented | Position differs from mockup (left vs right) |
| Sidebar Navigation | ✅ Complete | ⚠️ Partial | Missing "Time Limit Rules" menu item |
| Family Overview Card | ✅ Complete | ✅ Implemented | Matches specification |
| Connected Devices Table | ✅ Complete | ✅ Implemented | Matches specification |
| Role-Based Visibility | ✅ Complete | ✅ Implemented | Uses CSS hiding rather than conditional rendering |
| Users & Devices View | ✅ Planned | ❌ Not Implemented | Still uses separate tables |
| Time Limit Rules Table | ❌ Should Remove | ❌ Not Removed | Should be removed per specification |

### 8.2 Key Deviations from Specification

#### 8.2.1 Sidebar Navigation Missing "Time Limit Rules"

**Specification (Section 5.2):** The Dashboard section should include:
- Overview
- Users & Devices
- Time Limit Rules
- Connected Devices

**Implementation:** The sidebar navigation includes:
- Overview
- Users & Devices
- Connected Devices

**Deviation:** "Time Limit Rules" menu item is missing from the sidebar navigation.

#### 8.2.2 Users & Devices View Not Unified

**Specification (Section 5.4):** Users & Devices should be displayed as a unified view with user cards containing associated rules and devices.

**Implementation:** Separate tables for Users, Devices, and Time Limit Rules are maintained.

**Deviation:** The unified user card view has not been implemented.

#### 8.2.3 Time Limit Rules Table Not Removed

**Specification (Section 5.6):** The standalone Time Limit Rules table should be removed and rules displayed within user cards.

**Implementation:** The Time Limit Rules table remains as a standalone section.

**Deviation:** The table was not removed as specified.

#### 8.2.4 Header Layout Position

**Specification (Section 5.1):** Hamburger menu button should be in the top-right corner.

**Implementation:** Hamburger menu button is in the top-left corner.

**Deviation:** Position differs from specification.

### 8.3 Technical Constraints

#### 8.3.1 Inline Styles in HTML Template

The HTML template uses extensive inline styles rather than CSS classes, which:
- Makes maintenance more difficult
- Does not fully leverage CSS custom properties
- Increases HTML file size
- Complicates responsive design implementation

#### 8.3.2 Backward Compatibility

The implementation must maintain backward compatibility with existing API endpoints and data structures, which:
- Prevents breaking changes to API endpoints
- Requires support for existing data models
- Limits some design changes that would require API modifications

#### 8.3.3 Data Structure Limitations

The current data model separates users, devices, and rules into distinct API endpoints, which:
- Makes implementing the unified user card view challenging
- Requires client-side joining of related data
- Limits the ability to show associated rules/devices within user cards

### 8.4 Compromises Made

#### 8.4.1 Role-Based Visibility Implementation

**Approach:** Admin section is rendered in HTML with `class="admin-section admin-only"` and visibility is controlled via JavaScript by adding/removing the `hidden` class.

**Alternative Considered:** Conditionally render admin menu items based on role.

**Reason for Compromise:** Simpler to implement while maintaining backward compatibility.

#### 8.4.2 Maintaining Separate Tables

**Approach:** Kept separate tables for Users, Devices, and Time Limit Rules.

**Alternative Considered:** Implemented unified user card view.

**Reason for Compromise:** Maintains existing workflow for users familiar with the current interface and avoids major UI changes.

### 8.5 Future Improvements Needed

See `docs/dashboard-redesign-deviations.md` for detailed future improvement recommendations.

---

## 9. File References

| File | Path |
|------|------|
| Design Specification | `plans/dashboard-redesign-mockup.md` |
| Implementation Analysis | `docs/dashboard-current-implementation-analysis.md` |
| Deviations Document | `docs/dashboard-redesign-deviations.md` |
| HTML Template | `timelimit-ui/rootfs/usr/bin/dashboardV2/templates/dashboardV2.html` |
| CSS Stylesheet | `timelimit-ui/rootfs/usr/bin/dashboardV2/static/css/dashboardV2.css` |
| JavaScript File | `timelimit-ui/rootfs/usr/bin/dashboardV2/static/js/dashboardV2.js` |

---

*Document updated as part of Step 10: Document Deviations and Limitations.*