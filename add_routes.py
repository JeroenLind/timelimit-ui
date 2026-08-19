#!/usr/bin/env python
"""Script to add login_as_parent routes to app.py"""

import re

# Read the current file
with open('timelimit-ui/rootfs/usr/bin/dashboardV2/app.py', 'r') as f:
    content = f.read()

# Find the position to insert the new routes (before the Health Check section)
pattern = r'# =+ #\n# Health Check\n# =+ #'
match = re.search(pattern, content)
if match:
    insert_pos = match.start()
    
    # The new routes to add
    new_routes = '''# ============================================================================
# Login as Parent Routes
# ============================================================================

@app.route('/login-as-parent', methods=['GET'])
def get_login_as_parent():
    """Render the login as parent page.
    
    Shows appropriate step based on session state:
    - Step 1: Email form (no session)
    - Step 2: Verification code form (mail_login_token in session)
    - Step 3: Device info form (mail_auth_token in session)
    - Redirect to dashboard (device_auth_token in session)
    
    Returns:
        Rendered template or redirect.
    """
    # Check if already authenticated
    if session.get('device_auth_token'):
        return redirect('/dashboardV2')
    
    # Determine which step to show
    if session.get('mail_auth_token'):
        step = '3'
    elif session.get('mail_login_token'):
        step = '2'
    else:
        step = '1'
    
    # Get error message if any
    error = session.pop('login_as_parent_error', None)
    
    return render_template('login_as_parent.html', step=step, error=error)


@app.route('/login-as-parent', methods=['POST'])
def post_login_as_parent():
    """Process parent login form submission.
    
    Handles all three steps of the login flow:
    - Step 1: Send mail login code
    - Step 2: Sign in by mail code
    - Step 3: Sign in to family
    
    Returns:
        Redirect to next step or dashboard on success.
    """
    start_time = time.time()
    request_id = get_request_id()
    step = request.form.get('step', '1')
    
    server_url = get_current_server_url()
    
    if step == '1':
        # Step 1: Send mail login code
        mail = request.form.get('mail', '').strip()
        
        if not mail:
            session['login_as_parent_error'] = 'Email is required'
            logger.warning("Login as parent step 1 failed: missing email", request_id=request_id)
            return redirect('/login-as-parent')
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, mail):
            session['login_as_parent_error'] = 'Invalid email format'
            logger.warning("Login as parent step 1 failed: invalid email", request_id=request_id)
            return redirect('/login-as-parent')
        
        locale = 'en'  # Default locale
        logger.info("Login as parent step 1: sending mail login code", server_url=server_url, mail=mail, locale=locale, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.send_mail_login_code(mail=mail, locale=locale)
        
        if response.success:
            session['mail_login_token'] = response.data.get('mailLoginToken')
            logger.info("Login as parent step 1 successful", request_id=request_id)
            return redirect('/login-as-parent')
        else:
            session['login_as_parent_error'] = response.error_message or 'Failed to send verification code'
            logger.error("Login as parent step 1 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/login-as-parent')
    
    elif step == '2':
        # Step 2: Sign in by mail code
        mail_login_token = session.get('mail_login_token')
        received_code = request.form.get('receivedCode', '').strip()
        
        if not mail_login_token:
            session['login_as_parent_error'] = 'Session expired. Please start again.'
            logger.warning("Login as parent step 2 failed: missing mail_login_token", request_id=request_id)
            return redirect('/login-as-parent')
        
        if not received_code:
            session['login_as_parent_error'] = 'Verification code is required'
            logger.warning("Login as parent step 2 failed: missing code", request_id=request_id)
            return redirect('/login-as-parent')
        
        # Validate code format (3-word passphrase)
        code_words = received_code.split()
        if len(code_words) != 3:
            session['login_as_parent_error'] = 'Invalid verification code format (expected 3 words)'
            logger.warning("Login as parent step 2 failed: invalid code format", request_id=request_id)
            return redirect('/login-as-parent')
        
        logger.info("Login as parent step 2: verifying code", server_url=server_url, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.sign_in_by_mail_code(
            mail_login_token=mail_login_token,
            received_code=received_code
        )
        
        if response.success:
            session['mail_auth_token'] = response.data.get('mailAuthToken')
            logger.info("Login as parent step 2 successful", request_id=request_id)
            return redirect('/login-as-parent')
        else:
            session['login_as_parent_error'] = response.error_message or 'Invalid verification code'
            logger.error("Login as parent step 2 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/login-as-parent')
    
    elif step == '3':
        # Step 3: Sign in to family
        mail_auth_token = session.get('mail_auth_token')
        device_model = request.form.get('deviceModel', '').strip()
        device_name = request.form.get('deviceName', '').strip()
        
        if not mail_auth_token:
            session['login_as_parent_error'] = 'Session expired. Please start again.'
            logger.warning("Login as parent step 3 failed: missing mail_auth_token", request_id=request_id)
            return redirect('/login-as-parent')
        
        if not device_model:
            session['login_as_parent_error'] = 'Device model is required'
            logger.warning("Login as parent step 3 failed: missing device model", request_id=request_id)
            return redirect('/login-as-parent')
        
        if not device_name:
            session['login_as_parent_error'] = 'Device name is required'
            logger.warning("Login as parent step 3 failed: missing device name", request_id=request_id)
            return redirect('/login-as-parent')
        
        logger.info("Login as parent step 3: signing in to family", server_url=server_url, device_model=device_model, device_name=device_name, request_id=request_id)
        
        client = AuthClient(base_url=server_url)
        response = client.sign_in_into_family(
            mail_auth_token=mail_auth_token,
            device_name=device_name,
            device_model=device_model,
            client_level=7  # Matches Android app's ClientDataStatus.CLIENT_LEVEL_VALUE
        )
        
        if response.success:
            # Store device auth token in session
            device_auth_token = response.data.get('deviceAuthToken')
            session['device_auth_token'] = device_auth_token
            session['own_device_id'] = response.data.get('ownDeviceId')
            
            # Extract and store family_id from initialData or data if present
            # The server may return familyId in either initialData (create family) or data (sign in)
            initial_data = response.data.get('initialData', {})
            family_id = initial_data.get('familyId')
            
            # Also check in 'data' field (used by sign-in-into-family endpoint)
            if not family_id:
                data_field = response.data.get('data', {})
                family_id = data_field.get('familyId')
            
            if family_id:
                session['family_id'] = family_id
                logger.info(
                    "Family ID extracted from response",
                    family_id=family_id,
                    request_id=request_id
                )
            else:
                # Family ID not in response - need to get it from pull_status
                logger.info(
                    "Family ID not in sign-in response, performing sync to retrieve",
                    request_id=request_id
                )
                try:
                    client = AuthClient(base_url=server_url)
                    pull_response = client.pull_status(device_auth_token)
                    client.close()
                    
                    if pull_response.success:
                        # Try to get family_id from the pull response data
                        pull_data = pull_response.data
                        if isinstance(pull_data, dict):
                            # Check various possible locations for family_id
                            for key in ['familyId', 'family_id', 'family']:
                                if key in pull_data:
                                    family_id = pull_data[key]
                                    session['family_id'] = family_id
                                    logger.info(
                                        "Family ID extracted from pull response",
                                        family_id=family_id,
                                        request_id=request_id
                                    )
                                    break
                except Exception as e:
                    logger.warning(
                        "Failed to retrieve family ID via sync",
                        error=str(e),
                        request_id=request_id
                    )
            
            # Store auth token in database for later lookup
            if family_id and device_auth_token:
                db = get_database()
                store_auth_token(
                    db=db,
                    token_type='device_auth_token',
                    token_value=device_auth_token,
                    device_id=response.data.get('ownDeviceId'),
                    family_id=family_id,
                    mail=response.data.get('mail')
                )
                logger.info(
                    "Auth token stored in database",
                    family_id=family_id,
                    request_id=request_id
                )
            
            # Clear temporary session data
            session.pop('mail_login_token', None)
            session.pop('mail_auth_token', None)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("Login as parent successful", server_url=server_url, duration_ms=duration_ms, request_id=request_id)
            return redirect('/dashboardV2')
        else:
            session['login_as_parent_error'] = response.error_message or 'Failed to sign in to family'
            logger.error("Login as parent step 3 failed", server_url=server_url, error_code=response.error_code, request_id=request_id)
            return redirect('/login-as-parent')
    
    else:
        session['login_as_parent_error'] = 'Invalid step'
        return redirect('/login-as-parent')


@app.route('/login-as-parent/cancel', methods=['POST'])
def cancel_login_as_parent():
    """Cancel login as parent flow and clear session.
    
    Returns:
        Redirect to dashboard.
    """
    request_id = get_request_id()
    
    # Clear all login session data
    session.pop('mail_login_token', None)
    session.pop('mail_auth_token', None)
    session.pop('device_auth_token', None)
    session.pop('own_device_id', None)
    session.pop('family_id', None)
    session.pop('login_as_parent_error', None)
    
    logger.info("Login as parent cancelled", request_id=request_id)
    return redirect('/dashboardV2')


'''
    
    # Insert the new routes
    new_content = content[:insert_pos] + new_routes + content[insert_pos:]
    
    # Write the updated content back to the file
    with open('timelimit-ui/rootfs/usr/bin/dashboardV2/app.py', 'w') as f:
        f.write(new_content)
    
    print('Routes added successfully')
else:
    print('Pattern not found')