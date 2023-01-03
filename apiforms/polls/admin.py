from django.contrib import admin

# Register your models here.
from polls.models import DataEmail,Post

admin.site.register(Post)
admin.site.register(DataEmail)

