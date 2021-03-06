import sys,re,random,os,threading,time,_thread
sys.path.append('../../lib/')
import kl_http,kl_db,kl_reg,kl_progress,kl_log
from urllib.parse import urlparse

log=kl_log.kl_log('bokedaquan')
regex=kl_reg
http=kl_http.kl_http()
mylock = _thread.allocate_lock()#线程锁
#mylock.acquire() #Get the lock
#mylock.release()  #Release the lock.
progress=kl_progress.kl_progress('正在采集中')
progress.start()
#最大线程
maxthread=10
threadnum=0
#是否用代理
isproxy=False
http.setproxy('','','127.0.0.1:8087')
db=kl_db.mysql({
    'host':'localhost',
    'user':'root',
    'passwd':'adminrootkl',
    'db':'bokedaquan',
    'prefix':'kl_',
    'charset':'utf8'
})

f=open('../proxy/proxy.txt','r')
s=f.read()
f.close()
proxylist=s.splitlines()

#链接url正则
cjurl=[
    {
        'hostname':'http://lusongsong.com',
        'url':'http://lusongsong.com/daohang/',
        'shendu':2,
        'link_tezheng':'\/daohang\/webdir\-[^><\n]*?\.html',
        'mb_url_reg':'<a[^><\n]*?href=["|\']?([^><\n]*?(?:showurl_\d+?\.html)[^><\n]*?)["|\']?[^><\n]*?>.*?</a>',
        'mb_con_reg':'点此打开.*?【(.*?)】.*?网址.*?<a.*?href="(.*?)".*?>.*?</a>',
        'charset':'utf-8',
    }
]
class urlspider(object):
    """docstring for urlspider"""
    def __init__(self, arg):
        super(urlspider, self).__init__()
        self.arg = arg
        self.hostname=arg['hostname']
        self.linkreg='<a[^><\n]*?href=["|\']{0,1}([^><\n]*?(?:00_00)[^><\n]*?)["|\']{0,1}[^><\n]*?>.*?</a>'
        self.url=arg['url']
        self.charset=arg['charset']
        self.mb_url_reg=arg['mb_url_reg']
        self.mb_url_reg=arg['mb_url_reg']
        self.link_tezheng=arg['link_tezheng']
        self.shendu=int(arg['shendu'])

    def run(self):
        self.shenduurl(self.url)

    #随机取一个代理
    def get_proxy(self):
        proxylen=len(proxylist)
        if proxylen<=0:
            print('There is no available proxy server!')
            sys.exit()
        while True:
            pro=proxylist[random.randint(0,proxylen-1)]
            if pro!="":
                return pro

    def shenduurl(self,url,cur_shendu=1):
        global  threadnum
        global  maxthread
        global isproxy
        threadnum+=1
        print("collection page %s depth:%d"%(url,cur_shendu))
        ht=kl_http.kl_http()
        ht.autoUserAgent=True
        r=None
        while True:
            if isproxy:
                daili=self.get_proxy()
                print("using proxy:%s"%daili)
                http.resetsession()
                http.setproxy('','',daili)
            r=http.geturl(url)
            if http.lasterror==None:
                break
            else:
                print(http.lasterror)
        if r!=None:
            content=r.read().decode(self.charset)
            #查找目标url
            mburl_list=regex.findall(self.mb_url_reg,content, regex.I|regex.S)
            #去重
            mburl_list = list(set(mburl_list))
            mylock.acquire()
            self.adddata(mburl_list,url)
            mylock.release()
            #深度查找
            if cur_shendu<self.shendu:
                cur_shendu+=1
                xiangsereg=self.linkreg.replace('00_00',self.link_tezheng)
                sdurl_list=regex.findall(xiangsereg,content, regex.I|regex.S)
                sdurl_list = list(set(sdurl_list))
                for j in sdurl_list:
                    while True:
                        if threadnum<maxthread:
                            threading.Thread(target=self.shenduurl,args=(self.formaturl(url,j),cur_shendu,)).start()
                            break
                        time.sleep(1)
                        #cur_shendu-=1
        threadnum-=1
    #格式化请求的路径
    def formaturl(self,requestpath,curpath):
        #请求的url目录
        urldir=os.path.dirname(requestpath)
        url=urlparse(requestpath)
        protocol=url[0]
        hostname=url[1]
        if curpath[0:1]=='/':
            return '%s://%s%s'%(protocol,hostname,curpath)
        else:
            return urldir+'/'+curpath
    #添加数据到数据库
    def adddata(self,urllist,src_url):
        for i in urllist:
            result=db.table('url').where({
                'hostname':self.hostname,
                'url':i
            }).count()
            if result<=0:
                res=db.table('url').add({
                    'url':i,
                    'hostname':self.hostname,
                    'status':0,
                    'update_time':time.time(),
                    'src_url':src_url
                })
                if res<=0:
                    log.write('add %s error:%s'%(i,db.lasterror))
                    log.write('lastsql:%s'%db.getlastsql())
                else:
                    print("add url：%s"%i)
for i in cjurl:
    urlspider(i).run()


while True:
    if threadnum==0:
        progress.stop()
        break
    time.sleep(1)



input('it is conllected,please press any key to continue...')
