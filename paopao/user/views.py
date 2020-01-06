import base64
import json
import requests
from urllib.parse import urlencode

from django.core.mail import send_mail
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.generic.base import View

from .models import UserProfile,Address,WeiBoUser
#获取settings中的配置
from django.conf import settings
from django_redis import get_redis_connection

from ntoken.views import make_token
from .tasks import send_active_email
from tools.logging_check import logging_check

#本模块下 响应异常状态码 10101 - 10199

# Create your views here.
def user_view(request):
    #/v1/users

    if request.method == 'POST':
        #创建资源
        #前端json串{"uname":"guoxiao","password":"123456","phone":"13488873110","email":"213@qq.com"}
        # request.body
        json_str = request.body
        json_obj = json.loads(json_str)
        username = json_obj.get('uname')
        password = json_obj.get('password')
        phone = json_obj.get('phone')
        email = json_obj.get('email')
        # 基础校验[数据给没给, 用户名是否可用]
        #TODO 检查不存在情况
        if not username:
            result = {'code':10101, 'error':'Please give me username~'}
            return JsonResponse(result)
        #检查用户名是否可用
        old_users = UserProfile.objects.filter(username=username)
        if old_users:
            #当前用户名已注册
            result = {'code':10102, 'error': 'The username is already registed~'}
            return JsonResponse(result)

        import hashlib
        m = hashlib.md5()
        m.update(password.encode())
        #创建用户数据
        try:
            #由于username字段有唯一索引,如果出现并发插入多个相同用户名的情况,mysql会抛错,故此处必须try
            UserProfile.objects.create(username=username,email=email,phone=phone, password=m.hexdigest())
        except Exception as e:
            print('---create user error')
            print(e)
            result = {'code':10103, 'error':'The username is already registed !'}
            return JsonResponse(result)
        #发出 认证激活的 邮件 ?

        #生成随机码
        import random, base64
        random_num = random.randint(1000, 9999)
        random_str = username + '_' + str(random_num)
        #最终链接上的code为
        code_str = base64.urlsafe_b64encode(random_str.encode())
        #随机码存入缓存, 用于激活时,后端进行校验
        r = get_redis_connection('verify_email')
        r.set('verify_email_%s'%(username), random_num)
        active_url = 'http://127.0.0.1:7000/dadashop/templates/active.html?code=%s'%(code_str.decode())
        print('----active_url is ----')
        print(active_url)
        #执行发邮件[同步]
        #send_active_email(email, active_url)
        #发邮件[异步]
        send_active_email.delay(email, active_url)

        #默认当前用户已登录[签发token-自定义/官方]
        token = make_token(username)
        result = {'code':200, 'username':username, 'data':{'token':token.decode()}}
        return JsonResponse(result)

    elif request.method == 'GET':
        #获取资源
        pass
    #return HttpResponse(json.dumps({'code':200}))
    return JsonResponse({'code':200})






def active_view(request):
    #用户激活操作
    if request.method != 'GET':
        result = {'code':10104, 'error': 'Please use GET'}
        return JsonResponse(result)
    code = request.GET.get('code')
    if not code:
        pass

    try:
        code_str = base64.urlsafe_b64decode(code.encode())
        last_code_str = code_str.decode()
        username, rcode = last_code_str.split('_')
    except Exception as e:
        print('---urlb64 decode error')
        print(e)
        result = {'code':10106, 'error':'Your code is wrong'}
        return JsonResponse(result)

    r = get_redis_connection('verify_email')
    old_code = r.get('verify_email_%s'%(username))

    if not old_code:
        result = {'code':10107, 'error': 'Your code is wrong!'}
        return JsonResponse(result)

    if rcode != old_code.decode():
        result = {'code':10108, 'error': 'Your code is wrong!!'}
        return JsonResponse(result)

    try:
       user = UserProfile.objects.get(username=username,isActive=False)
    except Exception as e:
        result = {'code':10109, 'error':'Your is already actived~'}
        return JsonResponse(result)

    user.isActive = True
    user.save()
    #redis缓存中 删除对应数据
    r.delete('verify_email_%s'%(username))

    return JsonResponse({'code':200, 'data':{'message':'激活成功'}})


class AddressView(View):
    #CBV  - class base view  基于类的视图
    #FBV  - function base view 基于函数的视图
    #    1, class继承View ; 2, urls中 关联视图类时,需要按如下绑定- url(r'^/(?P<username>\w{1,11})/address$', views.AddressView.as_view())
    @logging_check
    def get(self, request, username):
        user = request.myuser
        if user.username != username:
            result = {'code':10111,'error':'Your URL is error'}
            return JsonResponse(result)
        all_address = Address.objects.filter(user=user,isActive=True)
        all_address_list = []
        for add in all_address:
            d = {}
            d['id'] = add.id
            d['receiver'] = add.receiver
            d['address'] = add.address
            d['receiver_mobile'] = add.receiver_mobile
            d['tag'] = add.tag
            d['is_default'] = add.isDefault
            d['postcode'] = add.postcode
            all_address_list.append(d)

        return JsonResponse({'code':200,'addresslist':all_address_list})
    @logging_check
    def post(self, request, username):
        # http://127.0.0.1:8000/v1/users/guoxiao7/address
        user = request.myuser
        if user.username !=username:
            result = {'code':10110,'error':'Your url is error!'}
            return JsonResponse(result)
        json_str = request.body
        json_obj = json.loads(json_str)
        receiver = json_obj.get('receiver')
        address = json_obj.get('address')
        receiver_phone = json_obj.get('receiver_phone')
        postcode = json_obj.get('postcode')
        tag = json_obj.get('tag')

        # old_address = Address.objects.filter(user_id=user.id)外键取值
        old_address = Address.objects.filter(user=user)
        #判断是否是第一次取值，如果是第一次，设置当前地址是默认地址
        isFisrt = False
        if not old_address:
            isFisrt = True
        Address.objects.create(user=user,receiver=receiver,address=address,receiver_mobile=receiver_phone,
                               postcode=postcode,tag=tag,isDefault=isFisrt)
        return JsonResponse({'code':200,'data':'新增地址成功！'})

    @logging_check
    def put(self,request,username,id):
        #更新地址
        #将前端传来的修改值，同步到数据库
        #
        user = request.myuser
        if user.username != username:
            result = {'code': 10110, 'error': 'Your url is error!'}
            return JsonResponse(result)
        json_str = request.body
        json_obj = json.loads(json_str)
        post_id = json_obj.get('id')
        if int(post_id) != int(id):
            result = {'code':10112,'error':'Your url is error'}
            return JsonResponse(result)
        tag = json_obj.get('tag')
        receiver = json_obj.get('receiver')
        address1 = json_obj.get('address')
        receiver_mobile = json_obj.get('receiver_mobile')
        try:
            address = Address.objects.get(user=user,id=id,isActive=True)
        except Exception as e:
            print(e)
            result = {'code':10113,'error':'Your id is error'}
            return JsonResponse(result)
        #TODO 比对一下，传过来的数据是否更新，没更新，不执行save（），有效降低没必要的save操作
        address.receiver = receiver
        address.receiver_mobile = receiver_mobile
        address.tag = tag
        address.address = address1
        address.save()
        return JsonResponse({'code':200,'data':'修改成功'})
    @logging_check
    def delete(self,request,username,id):
        #删除地址
        #将对应地址数据中isActive = False
        try:
            address = Address.objects.get(user = request.myuser,id=id,isActive=True)
        except Exception as e:
            result = {'code':10114,'error':'The id is error'}
            return  JsonResponse(result)
        #默认地址  不可删除
        address.isActive = False
        address.save()

        return JsonResponse({'code':200,'data':'删除成功'})

def get_weibo_login_url():
    #生成微博授权登录页面地址
    #如果需要高级权限，需要再此申明 scope 详情见笔记
    params = {'response_code':'code',
              'client_id':settings.WEIBO_CLIENT_ID,
              'redirect_uri':settings.WEIBO_RETURN_URL}
    login_url = 'https://api.weibo.com/oauth2/authorize?'
    url = login_url + urlencode(params)
    return url
def weibo_login(request):
    url = get_weibo_login_url()
    return JsonResponse({'code':200,'oauth_url':url})

class WeiBoView(View):
    def get(self,request):
        code = request.GET.get('code')
        #向微博服务器发送请求，用code交换token
        result = get_access_token(code)
        print('---exchange token result is---')
        print(result)
        # return JsonResponse({'code':209})
#{'access_token': '2.00x2cMkFq4R5VC8b3b1311a3J6ZZIB', 'remind_in': '157679999', 'expires_in': 157679999, 'uid': '5263382985', 'isRealName': 'true'}
    # 微博表中，是否有这个数据
    # 如果没有数据，第一次访问---》创建WeiboUser数据
    # 有的话，1）绑定注册过【uid】有值--->签发自己的token  ---同普通登录一样，
    # 2） 没有绑定【uid】为空 ---》 给前端返回200code，触发绑定邮箱
        wuid = result.get('uid')
        access_token = result.get('access_token')
        # 查询微博用户表，判断是否是第一次光临
        try:
            weibo_user = WeiBoUser.objects.get(wuid=wuid)
        except Exception as e:
            # 没有数据  -- 该微博账号第一次登录
            WeiBoUser.objects.create(wuid=wuid, access_token=access_token)
            result = {'code': 201, 'uid': wuid}
            return JsonResponse(result)
        else:
            #非第一次登录 WeiboUser有当前wuid对应的数据
            uid = weibo_user.uid
            if uid:
                #之前已经绑定注册过我们网站的用户
                username  = uid.username
                token = make_token(username)
                result = {'code':200,'username':username,'data':{'token':token.decode()}}
                return JsonResponse(result)
            else:
                #之前用当前微博登录过，但是没有完成后续额绑定注册流程
                result = {'code':201,'uid':wuid}
                return JsonResponse(result)

    def post(self,request):
        #绑定注册
        json_str = request.body
        json_obj = json.loads(json_str)
        wuid = json_obj.get('uid')
        email = json_obj.get('email')
        phone = json_obj.get('phone')
        password = json_obj.get('password')
        username = json_obj.get('username')
        #TODO 检查数据是否存在
        import hashlib
        m = hashlib.md5()
        m.update(password.encode())
        password_m = m.hexdigest()
        #创建userProfile 以及绑定WeiBoUser数据
        #有多个数据进行更新插入时，要考虑是否使用事务
        try:
            with transaction.atomic():
            #创建UserProfile用户数据
                user = UserProfile.objects.create(email=email,username=username,
                                                phone=phone,password=password_m)
                weibo_user = WeiBoUser.objects.get(wuid=wuid)
                #绑定外键
                weibo_user.uid = user
                weibo_user.save()
        except Exception as e:
            print(e)
            print('------FOUND foreign key is error, bind user weibouser-------')
            result = {'code':10113,'error':'The username is already existed'}
            return JsonResponse(result)
        #签发token
        token = make_token(user.username)
        #注册流程
        #将前端传递过来的uid，对应的weibo表的外键绑定到新注册的一个用户数据上
        result = {'code':200,'username':username,'data':{'token':token.decode()}}
        return JsonResponse(result)


def get_access_token(code):
    #向第三方认证服务器发送code 交换token
    token_url = 'https://api.weibo.com/oauth2/access_token'
    #post 请求
    post_data = {
        'client_id':settings.WEIBO_CLIENT_ID,
        'client_secret':settings.WEIBO_CLIENT_SECRET,
        'grant_type':'authorization_code',
        'redirect_uri':settings.WEIBO_RETURN_URL,
        'code':code
    }
    try:
        res = requests.post(token_url,data=post_data)
    except Exception as e:
        print(e)
        print('--weibo login is wrong--')
        return None

    if res.status_code == 200:
        return json.loads(res.text)
    return None

