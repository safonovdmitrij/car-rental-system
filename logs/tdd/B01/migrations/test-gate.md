# Migration technical TEST-GATE
Deployment support for approved PostgreSQL/Alembic stack and REQ data persistence. Technical GO: one actual empty-schema upgrade, required tables/revision stamp and repeated upgrade preserving data. Expected RED explicit missing upgrade behavior, not import/dependency. No downgrade against working DB; schema UUID-isolated on test cluster only.
