#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' url handlers '
import re, time, json, logging, hashlib, base64, asyncio



from aiohttp import web

from coroweb import get, post
from apis import Page,APIValueError, APIResourceNotFoundError

from models import User, Comment, Blog, next_id
from config import configs

COOKIE_NAME = 'awesession'#用来在set_cookie中命名
_COOKIE_KEY = configs.session.secret#导入默认设置
# set_cookie的一个参数，生成cookie值，这个函数不设置为async，因为需要等待其执行完后才可执行下一步
#制作cookie的数值，即set_cookie的value
# 首先会由网页中的javascript取得对应的值，并按照如下组合方式，进行摘要算法计算出一个字符串(A)：

# `"email" + ":" + "passwd"`
# 1
# 然后字符串(A)被以密码的形式传递到API内，在API内，字符串(A)再一次按照如下组合方式，进行摘要算法计算出一个字符串(B)，并保存到服务器数据库上。

# `"用户id" + ":" + 字串符(A)`
# 1
# 到了最后制作cookie发送给浏览器时，又使用字符串(B)按照如下组合方式，进行摘要算法计算出一个字符串(C)：

# `"用户id" + 字串符(B) + "到期时间" + "密匙"`
# 1
# 最后再按照如下组合方式，生成一个字串符(D)发送给浏览器

# `"用户id" + "到期时间" + 字符串(C)`

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()

def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p


def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1（id-到期时间-摘要算法）
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)
# 编写解析cookie代码：
@asyncio.coroutine
def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-') #拆分字符串(D)
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = yield from User.find(uid)
        if user is None:
            return None
        #用数据库来生字符串(C)与cookie的比较
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None

@get('/')
def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
        Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
        Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
    ]
    return {
        '__template__': 'blogs.html',
        'blogs': blogs,
        


    }

def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)

@get('/blog/{id}')
def get_blog(id):
    blog = yield from Blog.find(id)
    comments = yield from Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }



#显示注册页面
@get('/register')
def register():#这个作用是用来显示登录页面
    return {
        '__template__': 'register.html'
    }

@get('/signin')
def signin():
    return {
        '__template__': 'signin.html'
    }


@get('/api/users')
def api_get_users():
    users = yield from User.findAll(orderBy='created_at desc')
    for u in users:
        u.passwd = '******'
    return dict(users=users)





@post('/api/authenticate')
def authenticate(*, email, passwd):
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password.')
    users = yield from User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # check passwd:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password.')
    # authenticate ok, set cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

@get('/manage/blogs')
def manage_blogs(*, page='1'):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }

@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs'
    }

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

# 用户注册api，用来post信息的
@post('/api/users')
def api_register_user(*, email, name, passwd):
	# 判断值是否正确
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError('passwd')
    users = yield from User.findAll('email=?', [email])#查询邮箱是否已注册，查看ORM框架源码
    if len(users) > 0:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    #接下来就是注册到数据库上,具体看会ORM框架中的models源码
    #这里用来注册数据库表id不是使用Use类中的默认id生成，而是调到外部来，原因是后面的密码存储摘要算法时，会把id使用上。   
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(), image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    yield from user.save()
    #制作cookie返回浏览器客户端
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    # max-age用秒来设置 cookie的生存期 user2cookie用于生成验证用户登录的cookie值
    user.passwd = '******'#掩盖passwd
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    # 返回r用于register.html网页的JavaScript部分继续执行 dumps将一个Python数据结构转换为JSON
    return r
#接口用于数据库返回日志,见manage_blogs.html
@get('/api/blogs')
def api_blogs(*, page='1'):
    page_index = get_page_index(page)
    num = yield from Blog.findNumber('count(id)')#查询日志总数
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = yield from Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)

@get('/api/blogs/{id}')
def api_get_blog(*, id):
    blog = yield from Blog.find(id)
    return blog

@post('/api/blogs')
def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
    yield from blog.save()
    return blog