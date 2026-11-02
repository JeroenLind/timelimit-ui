# Time Limit Rules User Guide

This guide explains how to use the Time Limit Rules feature in the TimeLimit Dashboard V2 to manage time-based restrictions for child users.

---

## Table of Contents

1. [Introduction](#introduction)
2. [How to Create Time Limit Rules](#how-to-create-time-limit-rules)
3. [Adding Users to Family](#adding-users-to-family)
4. [Understanding Rule Types](#understanding-rule-types)
5. [Best Practices for Setting Limits](#best-practices-for-setting-limits)
6. [Troubleshooting Common Issues](#troubleshooting-common-issues)
7. [FAQ](#faq)

---

## Introduction

Time Limit Rules allow you to control when and how long children can use specific apps or categories of apps. Each rule defines:

- **Which user** the rule applies to
- **Which category** of apps the rule affects
- **When** the rule is active (days and time range)
- **How long** the limit lasts (in minutes)

---

## How to Create Time Limit Rules

### Step 1: Access the Time Limit Rules Page

1. Log in to the TimeLimit Dashboard V2
2. Navigate to the dashboard main page
3. Click on the "Time Limit Rules" tab in the navigation menu

### Step 2: Create a New Rule

1. Click the "+ Add New Rule" button
2. Fill in the following fields:

   **User Selection**
   - Select the child user from the dropdown list
   - The user must be a child account (not the parent)
   
   **Category Name**
   - Enter a free-format category name (e.g., "Games", "Social Media", "Education")
   - The category name can be any descriptive string
   - If a category with the same name already exists, it will be reused
   - If the category doesn't exist, it will be created automatically
   
   **Time Limit**
   - Enter the duration in minutes (e.g., 60 for 1 hour, 120 for 2 hours)
   - Maximum recommended: 1440 minutes (24 hours)

   **Days Selection**
   - Check the days the rule should apply to
   - By default, all days are selected
   - Uncheck days when the limit should not apply (e.g., weekends)

   **Time Range**
   - Set the start time (when the limit period begins)
   - Set the end time (when the limit period ends)
   - Times are in 24-hour format (e.g., 09:00 to 17:00)

3. Click "Save Rule" to create the rule

### Step 3: Verify the Rule

After saving, the rule will appear in the rules list. The rule will:
- Sync to the TimeLimit server automatically
- Apply to the selected user's device(s)
- Show in the user's device usage reports

---

## Adding Users to Family

This section explains how to add a new child user to your family from the TimeLimit Dashboard V2.

---

### Workflow

#### Step 1: Click "Add User" Button

1. Log in to the TimeLimit Dashboard V2 as a parent
2. Navigate to the dashboard main page
3. In the **Family Users** section, locate the "Add User" button
4. Click the **+ Add User** button to open the add user modal

#### Step 2: Fill in User Information

In the modal dialog, fill in the following fields:

| Field | Required | Description |
|-------|----------|-------------|
| User Name | Yes | The child's name (max 100 characters) |
| Device Name | No | A friendly name for the child's device (max 100 characters) |
| Device Model | No | The device model/type (max 100 characters) |

#### Step 3: Click "Add" Button

1. Review the entered information
2. Click the **Add** button to submit the form
3. The system will validate the input and send the request to the server

#### Step 4: Verify Success Notification

After successful submission, you will see:
- A green success toast notification: "User added successfully"
- The modal will automatically close
- The users table will refresh to show the new user

#### Step 5: Verify New User in Table

The new user will appear in the **Family Users** table with:
- The entered name
- Type: "child"
- The device information you provided
- Current device status

---

### UI Descriptions

#### "Add User" Button

- **Location:** Family Users section, next to the "Refresh Users" button
- **Icon:** Plus symbol (+)
- **Color:** Purple/blue theme (`rgba(102, 126, 234, 0.2)` background, `#667eea` text)
- **Behavior:** Opens the "Add User to Family" modal dialog

#### Modal Dialog

- **Overlay:** Dark semi-transparent background (`rgba(0, 0, 0, 0.8)`)
- **Content Container:** White background with rounded corners
- **Title:** "Add User to Family"
- **Position:** Centered on screen
- **Size:** Responsive - up to 500px wide on desktop, 90% of screen on mobile

#### Form Fields

| Field | Type | Placeholder | Validation |
|-------|------|-------------|------------|
| User Name | Text | "Child's name" | Required, max 100 chars |
| Device Name | Text | "Device name (optional)" | Optional, max 100 chars |
| Device Model | Text | "Device model (optional)" | Optional, max 100 chars |

#### Action Buttons

| Button | Type | Style | Function |
|--------|------|-------|----------|
| Cancel | Button | Secondary (purple) | Closes modal, resets form |
| Add | Submit | Primary (green) | Submits form, validates, calls API |

---

### Troubleshooting

#### Issue: Parent Password Not Set

**Symptoms:**
- Warning message appears in the modal
- User is added but device removal operations may not work

**Solution:**
1. Navigate to the "Set Parent Password" page
2. Set a parent password
3. This enables full device management capabilities for the new user

#### Issue: Server API Failure

**Symptoms:**
- Error message: "Failed to add user: [error details]"
- User does not appear in the users table

**Solutions:**
1. Check your internet connection
2. Verify the TimeLimit server is accessible
3. Try clicking "Refresh Users" and retry
4. Wait a few moments and try again
5. If the issue persists, check server status or contact support

#### Issue: Sync Failure

**Symptoms:**
- Success notification appears but user doesn't show in table
- User appears with incomplete information

**Solutions:**
1. Click "Refresh Users" to force a sync
2. Check that the device is connected to the internet
3. Verify the user was created correctly on the server
4. If the issue persists, try adding the user again

#### Issue: Invalid User Name

**Symptoms:**
- Validation error: "User name is required"
- Add button is disabled or shows error

**Solutions:**
1. Ensure the User Name field is not empty
2. Remove any leading/trailing whitespace
3. Check that the name is not more than 100 characters
4. Use a valid name (letters, numbers, spaces, and common punctuation)

---

## Understanding Rule Types

### Rule Type 0: TIME_LIMIT (Standard)

This is the default rule type. It sets a time limit for a specific category during a specific time window.

**Example:**
- User: Child
- Category: Games
- Time: 16:00 - 18:00 (4:00 PM - 6:00 PM)
- Limit: 60 minutes
- Days: Monday-Friday

This means the child can play games for up to 60 minutes between 4:00 PM and 6:00 PM on weekdays.

### Rule Type 1: TIME_LIMIT_EXCEPTIONS

Exception rules modify the behavior of standard time limits. These are typically used for special cases.

**Example:**
- User: Child
- Category: All Apps
- Time: 00:00 - 23:59 (all day)
- Limit: 0 minutes
- Days: Saturday, Sunday

This creates a weekend exception where all app limits are suspended.

---

## Days Bitmask Explained

The days field uses a bitmask system. Each day has a numeric value:

| Day | Bit | Value |
|-----|-----|-------|
| Monday | 0 | 1 |
| Tuesday | 1 | 2 |
| Wednesday | 2 | 4 |
| Thursday | 3 | 8 |
| Friday | 4 | 16 |
| Saturday | 5 | 32 |
| Sunday | 6 | 64 |

**Common Combinations:**

| Value | Days | Description |
|-------|------|-------------|
| 127 | All days | Rule applies every day |
| 63 | Weekdays | Monday through Friday only |
| 96 | Weekends | Saturday and Sunday only |
| 31 | Mon-Fri | Monday through Friday |
| 95 | Weekdays + Sunday | Monday through Friday plus Sunday |

---

## Best Practices for Setting Limits

### 1. Start Conservative

Begin with reasonable limits and adjust based on your child's behavior:
- Start with 30-60 minutes for recreational apps
- Allow more time for educational apps
- Gradually adjust based on usage patterns

### 2. Use Time Windows Strategically

- **Weekday limits:** Set during homework hours and early evening
- **Weekend limits:** Consider longer limits or no limits for recreational time
- **Bedtime:** Always include a "no apps" window before bedtime

### 3. Create Category-Based Rules

Different categories need different approaches:
- **Games:** 30-60 minutes per day
- **Social Media:** 30-45 minutes per day
- **Educational Apps:** Unlimited or extended time
- **Video Streaming:** 60-90 minutes per day

### 4. Use Overlapping Rules Wisely

Multiple rules can apply to the same user:
- Rules are applied in order of specificity
- More specific rules (single category) override general rules
- Test rules before relying on them

### 5. Consider Device-Specific Needs

- Different devices may need different limits
- Shared family devices might need stricter controls
- Consider the child's age and maturity level

### 6. Review and Adjust Regularly

- Check usage reports weekly
- Adjust limits based on behavior and needs
- Communicate changes to your child

### 7. Use the "All Categories" Option Sparingly

Setting a rule for "All Categories" with a 0-minute limit effectively blocks all apps during that time. Use this for:
- Bedtime hours
- Homework time
- Family time

---

## Troubleshooting Common Issues

### Issue: Rule Not Syncing to Server

**Symptoms:**
- Rule appears in dashboard but not on child's device
- Rule doesn't affect device usage

**Solutions:**
1. Check that the parent password hash is set (required for sync)
2. Verify the device is connected to the internet
3. Force a sync by clicking the refresh button
4. Check that the child's device has the latest TimeLimit app version
5. Ensure the device is properly registered to the family

### Issue: Rule Not Applying Correctly

**Symptoms:**
- Child can access apps outside the allowed time
- Time limits don't seem to be enforced

**Solutions:**
1. Verify the rule days and time range are correct
2. Check that the rule is enabled (not deleted)
3. Ensure the child's device is online and syncing
4. Verify the rule applies to the correct user and category
5. Check for conflicting rules that might override this one

### Issue: Cannot Create/Edit Rules

**Symptoms:**
- Save button is disabled
- Error message appears when saving

**Solutions:**
1. Ensure you're logged in as a parent account
2. Verify all required fields are filled (user, category, rule data)
3. Check that time format is correct (HH:MM, 24-hour)
4. Verify days value is between 0 and 127
5. Ensure limitMinutes is a non-negative integer

### Issue: Rule Shows "Not Synced" Status

**Symptoms:**
- Rule has a warning icon
- Sync status shows "pending"

**Solutions:**
1. Set the parent password hash via the "Set Parent Password" page
2. This is required for write operations to the server
3. After setting, the rule will sync automatically

### Issue: Time Zone Issues

**Symptoms:**
- Rules activate at unexpected times
- Time limits seem off by hours

**Solutions:**
1. Verify the server time zone matches your location
2. Check that device time zones are correct
3. Rules are based on server time, not device time

---

## FAQ

### Q: Why can't I see time limit rules?

**A:** You may not be logged in as a parent account. Log in using the email verification flow to access the dashboard as a parent.

### Q: Why is my rule not syncing?

**A:** The parent password hash must be set for write operations. Go to the "Set Parent Password" page to configure this.

### Q: How do I edit an existing rule?

**A:** Click the "Edit" button next to the rule in the list, make your changes, and click "Save Rule".

### Q: Can I set a rule for multiple users?

**A:** Each rule applies to a single user. Create separate rules for each user who needs limits.

### Q: What happens if I delete a rule?

**A:** The rule is removed from the dashboard and the server. The child will no longer have that time limit applied.

### Q: Can I set a rule that blocks all apps?

**A:** Yes, create a rule with:
- Category: "All Categories" (if available)
- Limit Minutes: 0
- Time: When you want to block all apps

### Q: How do I know if a rule is working?

**A:** Check the child's device for:
- Usage reports showing time limits
- App blocking notifications
- The TimeLimit app's activity log

### Q: What if I need to change a rule quickly?

**A:** You can edit or delete rules at any time. Changes sync to the server within minutes.

### Q: Are rules applied immediately?

**A:** Rules sync to the server and propagate to devices. This typically takes 1-5 minutes depending on device connectivity.

### Q: Can I set different limits for different days?

**A:** Yes, create separate rules for different day combinations. For example:
- Rule 1: Weekdays, 1 hour limit
- Rule 2: Weekends, 2 hour limit

---

## Additional Resources

- [Server API Documentation](ServerAPI.md) - Technical API reference
- [TimeLimit Dashboard V2 Documentation](../) - General dashboard documentation
- [TimeLimit App Support](https://support.timelimit.io) - Official support site

---

*Last updated: September 2026*