from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tcf_website", "0030_labreview_supabase_id"),
    ]

    operations = [
        # Rename work_life → independence
        migrations.RenameField(
            model_name="labreview",
            old_name="work_life",
            new_name="independence",
        ),
        # Rename friendliness → lab_culture
        migrations.RenameField(
            model_name="labreview",
            old_name="friendliness",
            new_name="lab_culture",
        ),
        # Drop inclusivity
        migrations.RemoveField(
            model_name="labreview",
            name="inclusivity",
        ),
        # Add entry_selectivity (default=3 for existing seed rows)
        migrations.AddField(
            model_name="labreview",
            name="entry_selectivity",
            field=models.PositiveSmallIntegerField(
                choices=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)],
                default=3,
            ),
            preserve_default=False,
        ),
    ]
