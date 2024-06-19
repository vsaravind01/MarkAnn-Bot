Alembic Migrations for MarkAnn backend

## How to use

### Create a new migration

```bash
alembic revision --autogenerate -m "migration message"
```

### Apply migrations

> Note: SQLite does not support `ALTER COLUMN` so you need to manually update the schema in `migrations/versions/` file
> after running the `alembic revision` command.

```bash
alembic upgrade head
```

### Downgrade migrations

```bash
alembic downgrade -1
```

### Show the current revision

```bash
alembic current
```