import json

from django.http import HttpResponse
from django.shortcuts import render


def test_cors(request):
    #127.0.0.1:8000 发ajax
    return render(request, 'index.html')

def test_cors_server(request):
    #接收跨域的ajax请求
    print(111111111111)
    print(request.body)

    ds = json.dumps({'msg': 'hahahaha'})
    return HttpResponse(ds, content_type='application/json')



