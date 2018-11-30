import logging;logging.basicConfig(level=logging.INFO)
# logging模块是Python内置的标准模块，主要用于输出运行日志，
# 可以设置输出日志的等级、日志保存路径、日志文件回滚等
# DEBUG：详细的信息,通常只出现在诊断问题上
# INFO：确认一切按预期运行
# WARNING：一个迹象表明,一些意想不到的事情发生了,或表明一些问题在不久的将来(例如。磁盘空间低”)。这个软件还能按预期工作。
# ERROR：更严重的问题,软件没能执行一些功能
# CRITICAL：一个严重的错误,这表明程序本身可能无法继续运行
import asyncio, os, json, time
from datetime import datetime
# asyncio 协程模块，服务器的构建需要监听多个URL，所以需要协程模块

# os模块，系统接口

# json模块，json编码模块，用于数据传输，是一种轻量级的数据交换格式，将python的数据编码成json，减小数据量。

# time模块，系统时间模块

# datatime，日期模块

# from aiohttp import web，导入aiohttp模块，用于构建http服务器。


from aiohttp import web
from jinja2 import Environment,FileSystemLoader
# jinja2模块中有一个名为Enviroment的类，这个类的实例用于存储配置和全局对象，然后从文件系统或其他位置中加载模板。FileSystemLoader文件系统加载器，不需要模板文件存在某个Python包下，可以直接访问系统中的文件。

import orm
from coroweb import add_routes,add_static

# 中jinja2模板的初始化也需要我们在app.py中实现
def init_jinja2(app, **kw):
    logging.info('init jinja2...')
    options = dict(
        autoescape = kw.get('autoescape', True),
        block_start_string = kw.get('block_start_string', '{%'),
        block_end_string = kw.get('block_end_string', '%}'),
        variable_start_string = kw.get('variable_start_string', '{{'),
        variable_end_string = kw.get('variable_end_string', '}}'),
        auto_reload = kw.get('auto_reload', True)
    )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        # templates/         <-- 存放模板文件
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env

# middleware
# 上面的RequestHandler对于URL做了一系列的处理，但是aiohttp框架最终需要的是返回web.Response对象，实现这一步，这里引入aiohttp框架的web.Application()中的middleware参数。 
# 简介：middleware是一种拦截器，一个URL在被某个函数处理前，可以经过一系列的middleware的处理。一个middleware可以改变URL的输入、输出，甚至可以决定不继续处理而直接返回。middleware的用处就在于把通用的功能从每个URL处理函数中拿出来，集中放到一个地方。 
# 当创建web.appliction的时候，可以设置middleware参数，而middleware的设置是通过创建一些middleware factory(协程函数)。这些middleware factory接受一个app实例，一个handler两个参数，并返回一个新的handler。
# 一个记录URL日志的logger可以简单定义如下：
async def logger_factory(app, handler):
    async def logger(request):
        logging.info('Request: %s %s' % (request.method, request.path))
        # await asyncio.sleep(0.3)
        return (await handler(request))
    return logger

async def data_factory(app, handler):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data
# response这个middleware把返回值转换为web.Response对象再返回，以保证满足aiohttp的要求：
async def response_factory(app, handler):
    async def response(request):
        logging.info('Response handler...')
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))
        # default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response
# 其参数中用到的datetime_filter()函数实质是一个拦截器，具体作用在day8中会提及 
# 先给出代码：
def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

async def init(loop):
    await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='www-data', password='www-data', db='awesome')
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory
    ])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, 'handlers')
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
# 创建协程，初始化协程，返回监听服务，进入协程执行
# 　　1.创建协程，loop = asyncio.get_event_loop()，为asyncio.BaseEventLoop的对象，协程的基本单位。

# 　　2.运行协程，直到完成，BaseEventLoop.run_until_complete(future)

# 　　3.运行协程，直到调用 stop()，BaseEventLoop.run_forever()