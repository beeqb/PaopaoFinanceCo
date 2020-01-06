import json

from django.http import JsonResponse
from django.shortcuts import render
from user.models import UserProfile
from django.conf import settings
# 该应用下 状态码  10201 - 10299

# Create your views here.
def token_view(request):
    #login.html
    if request.method != 'POST':
        result = {'code':10201, 'error':'Please use POST'}
        return JsonResponse(result)

    json_str = request.body
    if not json_str:
        result = {'code':10202, 'error': 'Please give me data'}
        return JsonResponse(result)

    json_obj = json.loads(json_str)
    username = json_obj.get('username')
    password = json_obj.get('password')
    #TODO
    #获取用户
    users = UserProfile.objects.filter(username=username)
    if not users:
        result = {'code':10203, 'error':'The username or password is wrong'}
        return JsonResponse(result)
    user = users[0]
    #比对密码
    import hashlib
    m = hashlib.md5()
    m.update(password.encode())
    if m.hexdigest() != user.password:
        result = {'code':10204, 'error': 'The username or password is wrong !!'}
        return JsonResponse(result)
    #make token
    token = make_token(username)
    result = {'code':200, 'username':username, 'data':{'token':token.decode()}}
    return JsonResponse(result)

def make_token(username, exp=3600*24):

    import jwt, time
    payload = {'username':username, 'exp': time.time()+exp}
    key = settings.JWT_TOKEN_KEY
    return jwt.encode(payload, key, algorithm='HS256')

