from django.db import migrations

from config.rls import enable_rls_on_public_tables


class Migration(migrations.Migration):
    # Depend on the last migration of every built-in app so that all of
    # Django's own tables already exist when RLS is enabled.
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("admin", "0003_logentry_add_action_flag_choices"),
        ("sessions", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(enable_rls_on_public_tables, migrations.RunPython.noop),
    ]
