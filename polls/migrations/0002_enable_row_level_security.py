from django.db import migrations

from config.rls import enable_rls_on_public_tables


class Migration(migrations.Migration):
    # New tables (polls_poll, polls_option, polls_vote) must also have RLS
    # enabled; the helper covers every table in the public schema.
    dependencies = [
        ("polls", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(enable_rls_on_public_tables, migrations.RunPython.noop),
    ]
