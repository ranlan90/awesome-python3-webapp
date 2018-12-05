#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# 导入异步工具包
import asyncio, os, inspect, logging, functools
# 导入网页处理工具包
from urllib import parse
# 导入底层web框架
from aiohttp import web

from apis import APIError

# 将函数映射为URL处理函数，使得get函数附带URL信息
def get(path):
    '''
    Define decorator @get('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
        # functools.wraps 的作用是将原函数对象的指定属性复制给包装函数对象, 默认有 module、name、doc,或者通过参数选择
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator

# 将函数映射为URL处理函数，使得post函数附带URL信息
def post(path):
    '''
    Define decorator @post('/path')
    '''
    def decorator(func):
        @functools.wraps(func)
         # functools.wraps 的作用是将原函数对象的指定属性复制给包装函数对象, 默认有 module、name、doc,或者通过参数选择
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST' # 存储方法信息
        wrapper.__route__ = path # 存储路径信息
        return wrapper
    return decorator

# 运用inspect模块，创建几个函数用以获取URL处理函数与request参数之间的关系
def get_required_kw_args(fn): # 收集没有默认值的命名关键字参数
    args = []
    params = inspect.signature(fn).parameters # inspect模块是用来分析模块，函数(提取fn所有参数)https://blog.csdn.net/weixin_35955795/article/details/53053762
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

def get_named_kw_args(fn): # 获取命名关键字参数
    args = []
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)

def has_named_kw_args(fn): # 判断有没有命名关键字参数
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True

def has_var_kw_arg(fn): # 判断有没有关键字参数
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

def has_request_arg(fn): # 判断是否含有名字叫做'request'参数，且该参数是否为最后一个参数
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
            continue
        if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
#             分别是POSITIONAL_ONLY、VAR_POSITIONAL、KEYWORD_ONLY、VAR_KEYWORD、POSITIONAL_OR_KEYWORD
# 分别对应廖老师教程中的位置参数、可变参数、命名关键字参数、关键字参数，最后一个是位置参数或命名关键字参数https://www.liaoxuefeng.com/discuss/001409195742008d822b26cf3de46aea14f2b7378a1ba91000/00146232548240136b7590e87fb4765b88197275b42a5fd000
            raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
    return found

# 使用RequestHandler函数封装一个URL处理函数，向request参数获取URL处理函数所需要的参数
class RequestHandler(object):

    def __init__(self, app, fn): # 接收Web服务器实例app参数 app作用是处理URL、HTTP协议
        self._app = app
        self._func = fn
        self._has_request_arg = has_request_arg(fn)# 检查函数是否有request参数
        self._has_var_kw_arg = has_var_kw_arg(fn)# 检查函数是否有关键字参数集
        self._has_named_kw_args = has_named_kw_args(fn)# 检查函数是否有命名关键字参数
        self._named_kw_args = get_named_kw_args(fn)# 将函数所有的 命名关键字参数名 作为一个tuple返回
        self._required_kw_args = get_required_kw_args(fn) # 将函数所有 没默认值的 命名关键字参数名 作为一个tuple返回

	# RequestHandler本身是一个类，由于定义了__call__方法，因此将其实例视为函数
    # 该函数从request中获取必要参数，之后调用URL函数
	# 最后将结果转换为web.Response对象。上述比较符合aiohttp框架
    async def __call__(self, request):
     # 构造协程' 分析请求，request handler,must be a coroutine that accepts a request instance as its only argument and returns a streamresponse derived instance '
        kw = None
        if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:# 当传入的处理函数具有 关键字参数集 或 命名关键字参数 或 request参数
            if request.method == 'POST': # 判断客户端发来的方法是否是POST
                if not request.content_type: # 查询有没提交数据的格式（EncType）
                    return web.HTTPBadRequest(text='Missing Content-Type.')
                ct = request.content_type.lower()
                if ct.startswith('application/json'):
                    # startswith() 方法用于检查字符串是否是以指定子字符串开头，如果是则返回 True，否则返回 False。application/json    ： JSON数据格式
                    params = await request.json() # 读取请求的body代码作为json文件，传入参数字典中
                    if not isinstance(params, dict):
                        return web.HTTPBadRequest(text='JSON body must be object.')
                    kw = params
                elif ct.startswith('application/x-www-form-urlencoded') or ct.startswith('multipart/form-data'):
                    # Content-Type 被指定为 application/x-www-form-urlencoded；其次，提交的数据按照 key1=val1&key2=val2 的方式进行编码，key 和 val 都进行了 URL 转码
                    # multipart/form-data 是一个常见的 POST 数据提交的方式。我们使用表单上传文件时，必须让 form 的 enctyped 等于这个值https://www.cnblogs.com/wushifeng/p/6707248.html
                    params = await request.post()
                    # 处理表单类型的数据，传入参数字典中
                    kw = dict(**params)
                    # ** 的作用则是把字典 kwargs 变成关键字参数传递
                else:
                    return web.HTTPBadRequest('Unsupported Content-Type: %s' % request.content_type)
                    # 暂不支持处理其他正文类型的数据
            if request.method == 'GET': # 判断客户端发来的方法是否是GET
                qs = request.query_string
                # request.query_string它得到的是，url中？后面所有的值
                if qs:
                    kw = dict()
                    for k, v in parse.parse_qs(qs, True).items():
                        kw[k] = v[0]
                        # parse_qs解释
                        # >>> from urllib import parse
                        # >>> url = r'https://docs.python.org/3.5/search.html?q=parse&check_keywords=yes&area=default'
                        # >>> parseResult = parse.urlparse(url)
                        # >>> parseResult
                        # ParseResult(scheme='https', netloc='docs.python.org', path='/3.5/search.html', params='', query='q=parse&check_keywords=yes&area=default', fragment='')
                        # >>> param_dict = parse.parse_qs(parseResult.query)
                        # >>> param_dict
                        # {'q': ['parse'], 'check_keywords': ['yes'], 'area': ['default']}
                        # >>> q = param_dict['q'][0]
                        # >>> q
        if kw is None:
            # 请求无请求参数时
            kw = dict(**request.match_info)          #request.match_info（获取@get('/api/{table}')装饰器里面的参数）
        else:
			# 当函数参数没有关键字参数时，移去request除命名关键字参数外所有的参数信息
            if not self._has_var_kw_arg and self._named_kw_args:
                # remove all unamed kw:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            # check named arg:
            for k, v in request.match_info.items():
                if k in kw:
                    logging.warning('Duplicate arg name in named arg and kw args: %s' % k)
                kw[k] = v
        if self._has_request_arg:# 检查函数是否有request参数
            kw['request'] = request
        # check required kw:即加入命名关键字参数(没有附加默认值),request没有提供相应的数值，报错
        if self._required_kw_args:# 收集无默认值的关键字参数
            for name in self._required_kw_args:
                if not name in kw:
                    return web.HTTPBadRequest('Missing argument: %s' % name)
        logging.info('call with args: %s' % str(kw))
        try:
            r = await self._func(**kw)
            # 最后调用处理函数，并传入请求参数，进行请求处理
            return r
        except APIError as e: # APIError另外创建这个APIError又是什么来的呢，其实它的作用是用来返回诸如账号登录信息的错误
            return dict(error=e.error, data=e.data, message=e.message)

# 添加静态文件夹的路径
def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    # import os
    # a=os.path.abspath(__file__)
    # b=os.path.dirname(os.path.abspath(__file__))
    # c = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    # print(a,'\n',b,'\n',c)

    #输出 C:\Users\moon\Desktop\cs2.py 
    #    C:\Users\moon\Desktop 
    #    C:\Users\moon\Desktop\static
# os.path.abspath(__file__)返回的是.py文件的绝对路径。    
    #获得包含'static'的绝对路径
    app.router.add_static('/static/', path) # 添加静态资源路径
    logging.info('add static %s => %s' % ('/static/', path))

# 用来注册一个URL处理函数，主要起验证函数是否包含URL的相应方法与路径信息，并将其函数变为协程
def add_route(app, fn):
    method = getattr(fn, '__method__', None)# 获取 fn 的 __method__ 属性的值，无则为None
    path = getattr(fn, '__route__', None)#获取 fn 的 __route__ 属性的值，无则为None
    if path is None or method is None:
        raise ValueError('@get or @post not defined in %s.' % str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):# 当处理函数不是协程时，封装为协程函数 inspect.isgeneratorfunction(object)：是否为python生成器函数iscoroutinefunction来判断是否coroutine函数
        fn = asyncio.coroutine(fn)
    logging.info('add route %s %s => %s(%s)' % (method, path, fn.__name__, ', '.join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method, path, RequestHandler(app, fn))#该方法将处理函数（其参数名为Requesthandler）与对应的URL（HTTP方法metho，URL路径path）绑定，浏览器敲击URL时返回处理函数的内容

# 自动将module_name模块中所有符合条件的函数进行注册
# 只需要向这个函数提供要批量注册函数的文件路径，新编写的函数就会筛选，注册文件内所有符合注册条件的函数
def add_routes(app, module_name):
    # 返回'.'最后出现的位置
    # 如果为-1，说明是 module_name中不带'.',例如(只是举个例子) handles 、 models
    # 如果不为-1,说明 module_name中带'.',例如(只是举个例子) aiohttp.web 、 urlib.parse()    n分别为 7 和 5 
    # 我们在app中调用的时候传入的module_name为handles,不含'.',if成立, 动态加载module

    n = module_name.rfind('.') #Python rfind() 返回字符串最后一次出现的位置(从右向左查询)，如果没有匹配项则返回-1。
    if n == (-1):
        mod = __import__(module_name, globals(), locals())
        # import一个模块，获取模块名 __name__
    else:
        #  比如 aaa.bbb 类型,我们需要从aaa中加载bbb
        # n = 3
        # name = module_name[n+1:] 为bbb
        # module_name[:n] 为aaa    
        # mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)，动态加载aaa.bbb
        # 上边三句其实相当于：
        #     aaa = __import__(module_name[:n], globals(), locals(), ['bbb'])
        #     mod = aaa.bbb
        # 还不明白的话看官方文档,讲的特别清楚：
        #     https://docs.python.org/3/library/functions.html?highlight=__import__#__import__

        name = module_name[n+1:]
        mod = getattr(__import__(module_name[:n], globals(), locals(), [name]), name)
        # 添加模块属性 name，并赋值给mod
    for attr in dir(mod):
        # dir(mod) 获取模块所有属性
        if attr.startswith('_'):
            # 略过所有私有属性
            continue
        fn = getattr(mod, attr)
        # 获取属性的值，可以是一个method
        if callable(fn):
            method = getattr(fn, '__method__', None)
            path = getattr(fn, '__route__', None)
            if method and path: # 此处查询path以及method是否存在而不是等待add_route函数查询# 对已经修饰过的URL处理函数注册到web服务的路由中
                add_route(app, fn)