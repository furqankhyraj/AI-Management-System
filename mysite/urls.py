"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
#urls.py
from django.contrib import admin
from django.urls import path
from home.views import *
from home.tasks import *

urlpatterns = [
    path('admin/', admin.site.urls),
    path("trello-webhook/", trello_webhook, name="trello_webhook"),
    path('', task_list, name='task_list'),
    path('assign-task/', assign_trello_task, name='assign_trello_task'),
    path('assign-task/<str:card_id>/', assign_trello_task, name='assign_trello_task'),
    path('delete-task/<str:card_id>/', delete_trello_task, name='delete_trello_task'),

]
