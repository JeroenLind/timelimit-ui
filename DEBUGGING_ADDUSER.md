# Debuggen van ADD_USER Failures

## Probleem
- ADD_USER acties retourneren `shouldDoFullSync: true`
- Server logs tonen geen foutmeldingen
- Kan niet zien wat er mis gaat

## Oplossing: Enhanced Server Logging

Ik heb logging toegevoegd aan:
1. **adduser.ts** - Details van ADD_USER verzoek en database errors
2. **apply-actions/index.ts** - Catch-block logging voor alle action errors

### Hoe te rebuild

Je kunt dit op 2 manieren doen:

#### Optie A: Rebuild Docker image (Recommended)
```bash
cd C:\git\timelimit-ha\timelimitserver
docker build -t timelimitserver .
docker-compose up -d timelimitserver
```

#### Optie B: Rebuild in Home Assistant terminal
```bash
cd /app
npm install
npm run build
```

Daarna dan `docker restart timelimitserver` of herstart Home Assistant add-on.

#### Optie C: Lokaal Node.js installeren (als je lokaal test)
```bash
# Voeg Node.js toe aan PATH of installeer via nvm
cd C:\git\timelimit-server
npm install
npm run build
# Nu werkt de server met nieuwe logging
```

## Wat de logging toont

### Bij succes:
```
[ADD-USER] Processing action: {userId: 'vID4jr', userType: 'child', ...}
[ADD-USER] Creating user in database...
[ADD-USER] ✅ User created successfully: vID4jr
```

### Bij fout (bijv. duplicate userId):
```
[ADD-USER] Processing action: {userId: 'vID4jr', userType: 'child', ...}
[ADD-USER] Creating user in database...
[ADD-USER] ❌ FAILED to create user: {
  userId: 'vID4jr',
  error: 'Unique constraint ... on familyId, userId failed',
  code: 'ER_DUP_ENTRY',
  ...
}
[APPLY-ACTIONS] ❌ Error processing action: {
  actionType: 'parent',
  errorMessage: 'Unique constraint violated',
  ...
}
```

## Waar docker logs te vinden

### Home Assistant terminal:
```bash
docker logs timelimitserver -f
```

### Via Home Assistant UI:
Settings → Devices & Services → 
TimeLimit Server → Logs ("View Logs" button)

## Vervolg stappen

1. Rebuild server met enhanced logging ↑
2. Probeer opnieuw kind toe te voegen
3. Check docker logs - je zult nu EXACT zien wat fout gaat
4. Deel die logs, dan kunnen we het echte probleem fixsen

## Mogelijke fouten die we gaan zien

- **ER_DUP_ENTRY**: userId bestaat al (duplicate)
- **ER_NO_REFERENCED_ROW**: familyId niet gevonden
- **Validation error**: timeZone niet geldig
- **Syntax error**: JSON parse fout in action
