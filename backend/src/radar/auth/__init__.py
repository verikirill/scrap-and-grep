"""Accounts: password hashing, browser sessions, guests and the administrator role."""

# Owner of the example profiles that every guest account starts with. Created
# by the schema migration; nobody signs in to it.
DEMO_EMAIL = "demo@radar.local"
# Guest accounts get made-up addresses in this domain; registration refuses it.
GUEST_DOMAIN = "guest.radar.local"
