# File Cache
缓存访问过的文件，防失效

## chatgpt
### 问题 1
我需要一个服务，咱们先讨论一下方案

有的文件链接刚开始能访问，过一段时间可能会因为不明原因而失效，这个服务的目的就是让访问过的文件都不再失效

两个接口:
- 一个用来接收文件原网址，放入到任务队列中
- 一个用来对外提供缓存文件

任务队列: 把文件缓存到本地

这个缓存有一个文件数量限制，达到了就先移除最早的文件

这个方案完整吗? 是否是通用常用的做法? 两个接口都用文件原网址做参数可好? 这个服务起什么名字?

### 问题 2
第一个接口接收文件原网址，(如果缓存中没有这个文件，则)放入到任务队列，(不管缓存中有没有这个文件，都)返回这个文件的第二个接口的代理访问地址(base_url/file/{url_hash})
接口不用加并发限制，下载任务并发进行，加限制，加失败重试
需要区别文件是否下载完整，第二个接口访问不完整的文件时返回错误信息
服务名我打算用 FileCache
用py aiohttp

### 问题 3
如果以时间戳命名文件，在enforce_cache_limit时会不会快一些，减少文件读取属性操作?

### 问题 4
关于 ClientTimeout 的参数，因为文件有大有小，用统一的total不合适，应该只计量多久没有下载到新增内容(connect阶段其实也算是没有下载到新增内容)，下载到新增内容就重置一次计时器。只设置connect和sock_connect和sock_read，而不设置total，是不是就能达到这样的目的?

## API
```
http(s)://service.domain/path?url=&token=
```
- url : 文件原地址，需要转码
- 这既是获取缓存文件的接口，也是添加任务的接口
- 获取文件不需要token，添加任务需要

## 环境变量(.env)
```python
# 可在.env文件中设置的项和其默认值
CACHE_DIR = os.getenv('CACHE_DIR', './cache')
MAX_FILES = int(os.getenv('MAX_FILES', 2000))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 2))
DOWNLOAD_TIMEOUT = int(os.getenv('DOWNLOAD_TIMEOUT', 10))
CONCURRENT_DOWNLOADS = int(os.getenv('CONCURRENT_DOWNLOADS', 3))
TOKEN = os.getenv('TOKEN', None)
APP_PATH = os.getenv('APP_PATH', '')
PORT = int(os.getenv('PORT', 8000))
HOST = os.getenv('HOST', '127.0.0.1')
```
