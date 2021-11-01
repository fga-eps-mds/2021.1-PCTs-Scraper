"""pcts_crawlers URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
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
from django.contrib import admin
from django.urls import path

from django.urls import include, path
from crawlers import views

from crawlers import urls as crawler_routes
from keywords import urls as keywords_routes
from rest_framework import routers

urls = [
    path('', include('crawlers.urls', namespace="crawlers")),
    path('', include('keywords.urls', namespace="keywords")),
]

router = routers.DefaultRouter()
router.registry.extend(crawler_routes.router.registry)
router.registry.extend(keywords_routes.router.registry)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api/', include(router.urls)),
    path('api/', include(urls)),
]
