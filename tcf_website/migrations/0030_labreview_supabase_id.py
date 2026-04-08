from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tcf_website", "0029_lab_labreview_labvote"),
    ]

    operations = [
        migrations.AddField(
            model_name="labreview",
            name="supabase_id",
            field=models.UUIDField(blank=True, db_index=True, null=True, unique=True),
        ),
    ]
