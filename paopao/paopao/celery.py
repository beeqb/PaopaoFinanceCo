# celery配置文件
from celery import Celery
from django.conf import settings
import os
from celery import Celery
#告诉celery django配置文件位置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paopao.settings')

app = Celery('paopao')
app.conf.update(
    BROKER_URL='redis://:@127.0.0.1:6379/1',
)

#celery自动去该参数位置寻找 worker任务
app.autodiscover_tasks(settings.INSTALLED_APPS)







