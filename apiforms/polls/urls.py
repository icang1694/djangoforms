from django.urls import path
from . import views
from .views import HomeView, ArticleView, UpdatePostView,DeletePostView


urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('update/',HomeView.updatestatus, name='updatejobstatus'),
    path('pause/<int:pk>',HomeView.pauseschjob, name='pause'),
    path('resume/<int:pk>',HomeView.resumeschjob, name='resume'),
    path('run/<int:pk>',HomeView.runschjob, name='run'),
    # path('data/<int:pk>',views.indexdataedit, name='detail'),
    path('data/<int:pk>',ArticleView.as_view(), name='detail'),
    path('data/', views.indexdata, name='indexdata'),
    path('data/edit/<int:pk>',UpdatePostView.as_view(), name='update_post'),
    # path('data/edit/<int:pk>',UpdatePostView.as_view(), name='update_post'),
    path('data/<int:pk>/remove',DeletePostView.as_view(), name='delete_post'),
    path('data/<int:pk>/remove/job',DeletePostView.deleteschjob, name='delete_job')
    # path('data/checkschedule/',views.checkschedule, name='indexsch')
]