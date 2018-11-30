#orm.py

#coding:utf-8
#day3:ORM 对象关系映射：通俗说就是将一个数据库表映射为一个类

import sys,random
import asyncio
#一步异步，处处使用异步
import aiomysql
import logging
logging.basicConfig(level=logging.INFO)#日志记录

#日志打印函数：打印出使用的sql语句
def log(sql,args=()):
    logging.info('SQL:%s'%sql)

#异步协程：创建数据库连接池
@asyncio.coroutine
# @asyncio.coroutine把一个generator标记为coroutine类型，然后，我们就把这个coroutine扔到EventLoop中执行。
def create_pool(loop,**kw):
    logging.info('start creating database connection pool')
    #全局私有变量，尽内部可以访问
    global __pool 
    #yield from 调用协程函数并返回结果
    __pool = yield from aiomysql.create_pool(
        #kw.get(key,default)：通过key在kw中查找对应的value，如果没有则返回默认值default
        host = kw.get('host','localhost'),#主机ip，默认本机
        port = kw.get('port',3306), #端口，默认3306
        user = kw['user'],#用户
        password = kw['password'],#用户口令
        db = kw['db'],#选择数据库
        charset = kw.get('charset','utf8'), #设置数据库编码，默认utf8
        autocommit = kw.get('autocommit',True), #设置自动提交事务，默认打开
        maxsize = kw.get('maxsize',10),#设置最大连接数，默认10
        minsize = kw.get('minsize',1),#设置最少连接数，默认1
        loop = loop #需要传递一个事件循环实例，若无特别声明，默认使用asyncio.get_event_loop()
        )

#协程：销毁所有的数据库连接池
async def destory_pool():
    global  __pool
    if __pool is not None:
        __pool.close()
        await __pool.wait_closed()

#协程：面向sql的查询操作:size指定返回的查询结果数
@asyncio.coroutine 
def select(sql,args,size=None):
    # ' 实现SQL语句：SELECT。传入参数分别为SQL语句、SQL语句中占位符对应的参数集、返回记录行数 '
    log(sql,args)
    global __pool #使用全局变量__pool
    #yield from从连接池返回一个连接，使用完后自动释放
    with (yield from __pool) as conn:
        #查询需要返回查询的结果，返回由dict组成的list，使用完后自动释放所以游标cursor中传入了参数aiomysql.DictCursor
        cur = yield from conn.cursor(aiomysql.DictCursor)
        #执行sql语句前，先将sql语句中的占位符？换成mysql中采用的占位符%s
        yield from cur.execute(sql.replace('?','%s'),args or ())
        if size:
            # 只接收size条返回结果行。如果size的值大于返回的结果行的数量，则会返回cursor.arraysize条数据。返回的结果是一个元组，元组的元素也是元组，由每行数据组成；
            rs = yield from cur.fetchmany(size)
        else:
            # 接收全部的返回结果行。返回的结果是一个元组，元组的元素也是元组，由每行数据组成；#返回的rs是一个list，每个元素是一个dict，一个dict代表一行记录
            rs = yield from cur.fetchall()
        yield from cur.close()
        logging.info('%s rows have returned' % len(rs))
    return rs

# 要执行INSERT、UPDATE、DELETE语句，可以定义一个通用的execute()函数，因为这3种SQL的执行都需要相同的参数，以及返回一个整数表示影响的行数：
# 传入参数分别为SQL语句、SQL语句中占位符对应的参数集、默认打开MySQL的自动提交事务 '
#将面向mysql的增insert、删delete、改update封装成一个协程
#语句操作参数一样，直接封装成一个通用的执行函数
#返回受影响的行数
@asyncio.coroutine
def execute(sql,args,autocommit = True):
    log(sql,args)
    global __pool
    with (yield from __pool) as conn:
        try:
            #同理，execute操作只返回行数，故不需要dict
            cur = yield from conn.cursor()
            yield from cur.execute(sql.replace('?','%s'),args) #创建一个字典游标，返回字典类型为元素的list
            yield from conn.commit()  #提交事务
            affected_line = cur.rowcount #获得影响的行数
            yield from cur.close()
            print('execute:',affected_line)
        except BaseException as e:
            raise
        return affected_line

#查询字段计数：替换成sql识别的'？'
#根据输入的字段生成占位符列表
def create_args_string(num):
    # ' 按参数个数制作占位符字符串，用于生成SQL语句 '
    L = []
    for i in range(num):#SQL的占位符是？，num是多少就插入多少个占位符
        L.append('?')
    #用，将占位符？拼接起来
    return (','.join(L)) #将L拼接成字符串返回，例如num=3时："?, ?, ?"

#定义Field类，保存数据库中表的字段名和字段类型，用于衍生 各种在ORM中 对应 数据库的数据类型 的类 '
class Field(object):
    #表的字段包括：名字、类型、是否为主键、默认值
    def __init__(self,name,column_type,primary_key,default):
        # ' 传入参数对应列名、数据类型、主键、默认值 '
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default
    #打印数据库中的表时，输出表的信息：类名、字段名、字段类型
    def __str__(self):
        return ('<%s,%s,%s>' %(self.__class__.__name__,self.name,self.column_type))

#定义不同类型的衍生Field
#表的不同列的字段的类型不同
class StringField(Field):
    # ' 从Field继承，定义一个字符类，在ORM中对应数据库的字符类型，默认‘变长100字节’ '
    def __init__(self,name=None,ddl='varchar(100)',primary_key=False,default=None):
        # ' 可传入参数列名、主键、默认值、数据类型 '
        super().__init__(name,ddl,primary_key,default) #对应列名、数据类型、主键、默认值
    #Boolean不能做主键
class BooleanField(Field):
    # ' 从Field继承，定义一个布尔类，在ORM中对应数据库的布尔类型 '
    def __init__(self,name=None,default=False):
        # ' 可传入参数列名、默认值 '
        super().__init__(name,'Boolean',False,default)#对应列名、数据类型、主键、默认值

class IntegerField(Field):
    # ' 从Field继承，定义一个整数类，在ORM中对应数据库的 BIGINT 整数类型，默认值为0 '
    def __init__(self,name=None,primary_key=False,default=0):
        super().__init__(name,'int',primary_key,default)#对应列名、数据类型、主键、默认值

class FloatField(Field):
    # ' 从Field继承，定义一个浮点数类，在ORM中对应数据库的浮点数类型 '
    def __init__(self,name=None,primary_key=False,default=0.0):
        super().__init__(name,'float',primary_key,default)

class TextField(Field):
    # ' 从Field继承，定义一个文本类，在ORM中对应数据库的 TEXT 长文本数类型 '
    def __init__(self,name=None,default=None):
        super().__init__(name,'text',False,default)

#定义Model的metaclass元类
#所有的元类都继承自type
#ModelMetaclass元类定义了所有Model基类（继承ModelMetaclass）的子类实现的操作

# -*-ModelMetaclass：为一个数据库表映射成一个封装的类做准备
# 读取具体子类(eg：user)的映射信息
#创造类的时候，排除对Model类的修改
#在当前类中查找所有的类属性(attrs),如果找到Field属性，就保存在__mappings__的dict里，
#同时从类属性中删除Field（防止实例属性覆盖类的同名属性）
#__table__保存数据库表名

class ModelMetaclass(type):
    #__new__控制__init__的执行，所以在其执行之前
     # __new__ 是在__init__之前被调用的特殊方法
    # __new__是用来创建对象并返回之的方法
    # 而__init__只是用来将传入的参数初始化给对象
    # 你很少用到__new__，除非你希望能够控制对象的创建
    # 这里，创建的对象是类，我们希望能够自定义它，所以我们这里改写__new__
    #cls：代表要__init__的类，此参数在实例化时由python解释器自动提供（eg：下文的User、Model)
    #bases:代表继承父类的集合
    #attrs:类的方法集合
    def __new__(cls,name,bases,attrs):
        # cls: 将要创建的类，类似与self，但是self指向的是instance，而这里cls指向的是class
        # name: 类的名字，也就是我们通常用类名.__name__获取的。

        # bases: 基类

        # attrs: 属性的dict。dict的内容可以是变量(类属性），也可以是函数（类方法）。
        #排除对Model的修改
        # ' 用metaclass=ModelMetaclass创建类时，通过这个方法生成类 '
        if name == 'Model': #定制Model类
            return type.__new__(cls,name,bases,attrs)#当前准备创建的类的对象、类的名字model、类继承的父类集合、类的方法集合

       #获取表名，默认为None，或为类名
        tableName = attrs.get('__table__',None) or name
        logging.info('found model:%s (table:%s)'%(name,tableName)) #类名、表名

        #获取Field和主键名
        mappings = dict()#用于存储列名和对应的数据类型
        fields = [] #保存非主键的属性名 
        primaryKey = None#用于主键查重，默认为None
        #k:类的属性(字段名)；v：数据库表中对应的Field属性
        for k,v in attrs.items():#遍历attrs方法集合
            #判断是否是Field属性
            if isinstance(v,Field):#提取数据类的列
                logging.info('found mapping %s===>%s' %(k,v))
                #保存在mappings
                mappings[k] = v #存储列名和数据类型
                if v.primary_key:
                    logging.info('found primary key %s'%k)
                    #主键只有一个，不能多次赋值
                    if primaryKey:
                        raise RuntimeError('duplicate primary key for the field:%s'%k)
                    #否则设为主键
                    primaryKey = k
                else:
                    #非主键，一律放在fields
                    fields.append(k)
        #end for
        if not primaryKey:
            raise RuntimeError('primary key is not found')
        #从类属性中删除Field属性
        for k in mappings.keys():
            attrs.pop(k)

        #保存非主键属性为字符串列表形式
        #将非主键属性变成`id`,`name`这种形式（带反引号）
        #repr函数和反引号：取得对象的规范字符串表示
        escaped_fields = list(map(lambda f:'`%s`' %f,fields)) #给非主键列加``（可执行命令）区别于''（字符串效果）
        #保存属性和列的映射关系
        attrs['__mappings__'] = mappings
        #保存表名
        attrs['__table__'] = tableName
        #保存主键属性名
        attrs['__primary_key__'] = primaryKey
        #保存主键外的属性名
        attrs['__fields__'] = fields
        #构造默认的增删改查语句
        attrs['__select__'] = 'select `%s`,%s from `%s` '%(primaryKey,','.join(escaped_fields),tableName)
        attrs['__insert__'] = 'insert into `%s` (%s,`%s`) values (%s)' %(tableName,','.join(escaped_fields),primaryKey,create_args_string(len(escaped_fields)+1))
        attrs['__update__'] = 'update `%s` set %s where `%s` = ?' %(tableName,','.join(map(lambda f:'`%s` = ?' %(mappings.get(f).name or f),fields)),primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s` = ?' %(tableName,primaryKey)
        return type.__new__(cls,name,bases,attrs)

#定义ORM所有映射的基类：Model
#Model类的任意子类可以映射一个数据库表
#Model类可以看做是对所有数据库表操作的基本定义的映射
#基于字典查询形式
#Model从dict继承，拥有字典的所有功能，同时实现特殊方法__getattr__和__setattr__,能够实现属性操作
#实现数据库操作的所有方法，定义为class方法，所有继承自Model都具有数据库操作方法



class Model(dict,metaclass=ModelMetaclass):
    # ' 定义一个对应 数据库数据类型 的模板类。通过继承，获得dict的特性和元类的类与数据库的映射关系 '
#     # 由模板类衍生其他类时，这个模板类没重新定义__new__()方法，因此会使用父类ModelMetaclass的__new__()来生成衍生类，从而实现ORM
    def __init__(self,**kw):
        super(Model,self).__init__(**kw)
    def __getattr__(self,key):
                # ' getattr、settattr实现属性动态绑定和获取 '
        try:
            return self[key]
        except KeyError:
            raise AttributeError("'model' object has no attribution:%s"%key)
    def __setattr__(self,key,value):
        self[key]=value
    def getValue(self,key):
        #内建函数getattr会自动处理  
        return getattr(self,key,None)

    def getValueOrDefault(self,key):
        # ' 返回属性值，空则返回默认值 '
        value=getattr(self,key,None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                # callable() 函数用于检查一个对象是否是可调用的
                logging.info('using default value for %s : %s'%(key,str(value)))
                setattr(self,key,value)
        return value

    @classmethod #添加类方法，对应查表，默认查整个表，可通过where limit设置查找条件 #申明是类方法：有类变量cls传入，cls可以做一些相关的处理 #有子类继承时，调用该方法，传入的类变量cls是子类，而非父类
    @asyncio.coroutine
    def findAll(cls,where=None,args=None,**kw):
        sql = [cls.__select__]#用一个列表存储select语句
        if where:#添加where条件
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy',None) #对查询结果排序排序
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)
        limit = kw.get('limit',None) #截取查询结果
        if limit is not None:
            sql.append('limit')
            if isinstance(limit,int): #截取前limit条记录
                sql.append('?')
                args.append(limit)
            elif isinstance(limit,tuple) and len(limit) == 2: #略过前limit[0]条记录，开始截取limit[1]条记录
                sql.append('?,?')
                args.append(limit) #将limit合并到args列表的末尾
            else:
                raise ValueError('invalid limit value:%s'%str(limit))
        #返回的rs是一个元素是tuple的list
        rs = yield from select(' '.join(sql),args)#构造更新后的select语句，并执行，返回属性值[{},{},{}]
        return [cls(**r) for r in rs]
        #**r 是关键字参数，构成了一个cls类的列表，其实就是每一条记录对应的类实例
        #返回一个列表。每个元素都是一个dict，相当于一行记录
        # 'select `%s`,%s from `%s` '%(primaryKey,','.join(escaped_fields),tableName)

    @classmethod # 类方法，根据主键查询一条记录
    @asyncio.coroutine
    def findNumber(cls,selectField,where=None,args=None):
        '''find number by select and where'''
        sql = ['select %s __num__ from `%s`'%(selectField,cls.__table__)]
        if where:
            sql.append('where')
            args.append(where)
        rs = yield from select(' '.join(sql),args,1)
        if len(rs) == 0:
            return None
        return rs[0]['__num__'] #将dict作为关键字参数传入当前类的对象

    @classmethod
    @asyncio.coroutine
    def find(cls,primaryKey):
        # ' 实例方法，映射插入记录 '
        '''find object by primary key'''
        #rs是一个list，里面是一个dict
        rs = yield from select('%s where `%s`=?'%(cls.__select__,cls.__primary_key__),[primaryKey],1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])
        #返回一条记录，以dict的形式返回，因为cls的父类继承了dict类




    @asyncio.coroutine
    def save(self):
        args = list(map(self.getValueOrDefault,self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = yield from execute(self.__insert__,args)
        if rows != 1:
            logging.info('failed to insert record:affected rows:%s'%rows)

    @asyncio.coroutine
    def update(self):
        args = list(map(self.getValue,self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = yield from execute(self.__update__,args)
        if rows != 1:
            logging.info('failed to update record:affected rows:%s'%rows)

    @asyncio.coroutine
    def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = yield from execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows: %s' % rows)