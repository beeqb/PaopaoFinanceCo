from django.core.mail import send_mail
from paopao.celery import app

@app.task
def send_active_email(email, active_url):
    #发送激活邮件
    try:
        subject = '达达商城激活邮件'
        html_message = '''
        <p>尊敬的用户 您好</p>
        <p>激活链接为<a href='%s' target='blank'>点击激活</a></p>
        '''%(active_url)
        send_mail(subject=subject, html_message=html_message,from_email='1871721196@qq.com', recipient_list=[email],message='')
        print('----send mail ok-----')
        #b2b  连调时，需要在完成任务时，通知一下对方公司
    except Exception as e:
        print('--send email error--')
        print(e)
        #TODO 上线后添加 error response

