"""Role to permission map. Seeded into the database; the database is the source of truth at runtime."""

PERMISSIONS: dict[str, str] = {
    "users.read": "View customers and providers",
    "users.manage": "Suspend or reactivate accounts",
    "providers.review": "Review provider documents and approve providers",
    "catalogue.manage": "Edit services, prices and categories",
    "bookings.read": "View all bookings",
    "bookings.manage": "Assign, reschedule and cancel bookings",
    "refunds.manage": "Approve refunds and refund requests",
    "complaints.manage": "Handle complaints and support tickets",
    "payouts.read": "View payouts",
    "payouts.manage": "Hold, release and configure payouts",
    "coverage.manage": "Manage service areas",
    "promotions.manage": "Manage promotions",
    "finance.read": "View financial and growth reports",
    "finance.manage": "Enter business costs",
    "settings.manage": "Change business configuration and feature flags",
    "audit.read": "View audit logs",
    "staff.manage": "Create staff accounts and assign roles",
}

ROLES: dict[str, tuple[str, bool, list[str]]] = {
    "customer": ("Customer", False, []),
    "provider": ("Service professional", False, []),
    "super_admin": ("Super administrator", True, list(PERMISSIONS)),
    "operations": (
        "Operations",
        True,
        ["users.read", "users.manage", "providers.review", "bookings.read", "bookings.manage", "complaints.manage", "coverage.manage", "payouts.read"],
    ),
    "support": ("Customer support", True, ["users.read", "bookings.read", "complaints.manage", "refunds.manage"]),
    "finance": ("Finance", True, ["bookings.read", "refunds.manage", "payouts.read", "payouts.manage", "finance.read", "finance.manage"]),
}
