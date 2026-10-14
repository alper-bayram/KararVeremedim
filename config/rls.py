"""Row Level Security helper for Supabase.

Supabase exposes every table in the `public` schema through its REST API.
We never use that API, so RLS is enabled on every table without policies:
the API role can then read nothing, while Django's `postgres` role bypasses RLS.

Import `enable_rls_on_public_tables` in a migration and run it with
`migrations.RunPython(enable_rls_on_public_tables, migrations.RunPython.noop)`.
"""

ENABLE_RLS_SQL = """
DO $$
DECLARE
    t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE 'ALTER TABLE public.' || quote_ident(t.tablename) || ' ENABLE ROW LEVEL SECURITY';
    END LOOP;
END
$$;
"""


def enable_rls_on_public_tables(apps, schema_editor):
    # SQLite (local fallback) has no RLS; only PostgreSQL needs this.
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(ENABLE_RLS_SQL)
