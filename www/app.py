import logging;logging.basicConfig(level=logging.INFO)
# logging模块是Python内置的标准模块，主要用于输出运行日志，
# 可以设置输出日志的等级、日志保存路径、日志文件回滚等
# DEBUG：详细的信息,通常只出现在诊断问题上
# INFO：确认一切按预期运行
# WARNING：一个迹象表明,一些意想不到的事情发生了,或表明一些问题在不久的将来(例如。磁盘空间低”)。这个软件还能按预期工作。
# ERROR：更严重的问题,软件没能执行一些功能
# CRITICAL：一个严重的错误,这表明程序本身可能无法继续运行
import asyncio, os, json, time
# asyncio 协程模块，服务器的构建需要监听多个URL，所以需要协程模块

# os模块，系统接口

# json模块，json编码模块，用于数据传输，是一种轻量级的数据交换格式，将python的数据编码成json，减小数据量。

# time模块，系统时间模块

# datatime，日期模块

# from aiohttp import web，导入aiohttp模块，用于构建http服务器。


from aiohttp import web

def index(requset):
	return web.Response(body='<h1>Awesome</h1>'.encode(), content_type='text/html')
# 1.函数名随意取。该函数的作用是处理URL，之后将与具体URL绑定

# 　　2.参数，aiohttp.web.request实例，包含了所有浏览器发送过来的 HTTP 协议里面的信息，一般不用自己构造

# 　　   具体文档参见 http://aiohttp.readthedocs.org/en/stable/web_reference.html

# 　　3.返回值，aiohttp.web.response实例，由web.Response(body='')构造，继承自StreamResponse，功能为构造一个HTTP响应

# 　　   类声明 class aiohttp.web.Response(*, status=200, headers=None, content_type=None, body=None, text=None)

# 　　4.HTTP 协议格式为： POST /PATH /1.1 /r/n Header1:Value  /r/n .. /r/n HenderN:Valule /r/n Body:Data 该实例构建了一个HTTP响应。
@asyncio.coroutine
def init(loop):
	app = web.Application(loop=loop)
	app.router.add_route('get','/',index)
# 定义init函数，标记为协程，传入loop协程参数，app为web服务器的实例，服务器的作用是处理URL，HTTP协议。

# .add_route作用是将URL注册进route（也就是之前处理多个URL时也是注册到route属性），将URL和index处理函数绑定，绑定的作用是当浏览器敲击URL时，返回处理函数的内容，也就是返回一个HTTP响应。

# loop.create_server是创建一个监听服务，后面的参数传入监听服务器的IP、端口、HTTP协议簇。然后init函数返回的就是这个监听服务。aiohttp.RequestHandlerFactory 可以用 make_handle() 创建，用来处理 HTTP 协议

# get_event_loop创建一个事件循环，然后使用run_until_complete将协程注册到事件循环，并启动事件循环。实际也是一个协程。创建事件循环的目的是因为协程对象开始运行需要在一个已经运作的协程中。

# run_until_complete()是一个阻塞调用，将协程注册到事件循环，并启动事件循环，直到返回结果。因为协程对象开始运行需要在一个已经运作的协程中，所以这个函数实际就是将传入的协程对象，用ensure_future函数包装成一个future。应该就是将协程注册到事件循环中了，然后函数再启动这个循环。

# run_forever()指一直运行协程，直到调用stop()函数。保证服务器一直开启监听状态。如果不一直将loop.run_forever则在运行一次init之后，返回监听服务，run_until_complete就结束了。

	srv = yield from loop.create_server(app.make_handler(),'127.0.0.1',9000)
# 	三，用协程创建监听服务，并使用aiohttp中的HTTP协议簇(protocol_factory)
# 	　　1.用协程创建监听服务，其中loop为传入函数的协程，调用其类方法创建一个监听服务，声明如下

# 　　 coroutine BaseEventLoop.create_server(protocol_factory, host=None, port=None, *, family=socket.AF_UNSPEC, flags=socket.AI_PASSIVE, sock=None, backlog=100, ssl=None, reuse_address=None, reuse_port=None)

# 　　2.yield from 返回一个创建好的，绑定IP、端口、HTTP协议簇的监听服务的协程。yield from的作用是使srv的行为模式和 loop.create_server()一致
	logging.info('server started at http://127.0.0.1:9000...')
	return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
# 创建协程，初始化协程，返回监听服务，进入协程执行
# 　　1.创建协程，loop = asyncio.get_event_loop()，为asyncio.BaseEventLoop的对象，协程的基本单位。

# 　　2.运行协程，直到完成，BaseEventLoop.run_until_complete(future)

# 　　3.运行协程，直到调用 stop()，BaseEventLoop.run_forever()