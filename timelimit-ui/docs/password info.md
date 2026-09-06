Password: 12345678
RemoveHash: $2a$12$XQTd1w7ux40Edo/5KVmDwu2jBzgiPX6gwbQOwnWwMUDX86s4Npqka

Family creation
hash: $2a$12$q1SQJsScNydtLN9Krc1WSumObCMa8rXJzuEr5n69jrVgY34QXtMae
secondHash: $2a$12$RDkpyVVnbodje9vwHg1V3OXIT4IFt7fRwXeJGeysKgB.xkoeJd2Ke
secondSalt: $2a$12$RDkpyVVnbodje9vwHg1V3O

Password: "12345678"
    │
    ├─── Salt1 (random 29 chars) ──→ Hash1 (60 chars)
    │                                   │
    │                                   └── Used for primary authentication
    │
    └─── Salt2 (random 29 chars) ──→ Hash2 (60 chars)
                                      │
                                      └── Used for HMAC signing (secondSalt)
